"""Exam-import workflow service: upload -> parse -> extract -> validate -> persist.

Runs the full pipeline synchronously on upload and stores the durable
``ExamImport`` (parsed blocks, extracted + reviewed documents, validation). The
review step re-validates a human-edited reviewed document; approval materializes
the reviewed document into Question Library questions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.config import Settings
from app.core.storage import StorageBackend
from app.exam.extraction import LLMExamExtractor, RuleBasedExamExtractor
from app.exam.extraction.interface import ExamExtractor
from app.exam.ir import ExamDocument, QuestionNode
from app.exam.materialization import materialize_exam_document
from app.exam.parsing import parse_document
from app.exam.validation import validate_exam_document
from app.models import ExamImport, Question
from app.models.exam_import import can_transition
from app.schemas.question import QuestionCreate, QuestionIngestDraft
from app.services.ai_client import AIClient
from app.services.assets import create_asset_from_bytes
from app.services.authorization import assert_workspace_access
from app.services.doc_convert import DocConversionError, convert_doc_to_docx


def _now() -> datetime:
    return datetime.now(UTC)


def _set_status(imp: ExamImport, new_status: str) -> None:
    if not can_transition(imp.status, new_status):
        raise HTTPException(
            status_code=409,
            detail=f"illegal import state transition: {imp.status} -> {new_status}",
        )
    imp.status = new_status


def _normalize_source(data: bytes, filename: str, settings: Settings) -> tuple[str, bytes]:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return "pdf", data
    if name.endswith(".doc"):
        try:
            return "docx", convert_doc_to_docx(data, settings)
        except DocConversionError as exc:
            raise HTTPException(status_code=422, detail=f"DOC conversion failed: {exc}") from exc
    if name.endswith(".docx"):
        return "docx", data
    raise HTTPException(status_code=415, detail="Only .docx, .pdf and .doc files are supported")


def _build_extractor(settings: Settings) -> ExamExtractor:
    client = AIClient(settings)
    if client.enabled:
        return LLMExamExtractor(client)  # falls back to rule-based on failure
    return RuleBasedExamExtractor()


def _extractor_meta(doc: ExamDocument) -> dict:
    meta = doc.meta or {}
    return {
        "extractor": meta.get("extractor"),
        "provider": meta.get("provider"),
        "model": meta.get("model"),
        "schema_version": meta.get("schema_version"),
        "fallback_occurred": bool(meta.get("fallback_occurred")),
    }


def get_import(db: Session, import_id: UUID, user: CurrentUser) -> ExamImport:
    imp = db.get(ExamImport, import_id)
    if imp is None:
        raise HTTPException(404, "Exam import not found")
    assert_workspace_access(imp.workspace_id, user.workspace_id)
    return imp


def list_imports(db: Session, user: CurrentUser) -> list[ExamImport]:
    return list(
        db.scalars(
            select(ExamImport)
            .where(ExamImport.workspace_id == user.workspace_id)
            .order_by(ExamImport.created_at.desc())
        )
    )


def create_import(
    db: Session,
    user: CurrentUser,
    storage: StorageBackend,
    settings: Settings,
    filename: str,
    data: bytes,
) -> ExamImport:
    source_type, data = _normalize_source(data, filename, settings)

    imp = ExamImport(
        workspace_id=user.workspace_id,
        source_filename=filename or "upload",
        source_type=source_type,
        status="uploaded",
    )
    db.add(imp)
    db.flush()  # assign id

    source_key = f"exam_imports/{user.workspace_id}/{imp.id}/source.{source_type}"
    storage.put(source_key, data)
    imp.storage_key = source_key

    try:
        _set_status(imp, "parsing")
        parsed = parse_document(data, filename=filename)

        _set_status(imp, "extracting")
        extractor = _build_extractor(settings)
        doc = extractor.extract(parsed)
        report = validate_exam_document(doc)

        # persist referenced image bytes (local_id -> storage key) for approve-time
        # resolution into Asset records.
        asset_manifest: dict[str, dict[str, str]] = {}
        for local_id, blob in parsed.assets.items():
            key = f"exam_imports/{user.workspace_id}/{imp.id}/assets/{local_id}"
            storage.put(key, blob)
            asset_manifest[local_id] = {"storage_key": key}

        meta = _extractor_meta(doc)
        imp.blocks_json = [b.model_dump(mode="json") for b in parsed.blocks]
        imp.parser_meta = {
            "page_count": parsed.page_count,
            "source_name": parsed.source_name,
            "format": parsed.format,
            "warnings": parsed.warnings,
        }
        imp.asset_manifest = asset_manifest
        imp.extracted_document_json = doc.model_dump(mode="json")
        imp.reviewed_document_json = doc.model_dump(mode="json")
        imp.validation_json = report.model_dump(mode="json")
        imp.extractor_name = meta["extractor"]
        imp.provider = meta["provider"]
        imp.model = meta["model"]
        imp.schema_version = meta["schema_version"]
        imp.fallback_occurred = meta["fallback_occurred"]
        imp.needs_review = report.needs_review
        _set_status(imp, "needs_review" if report.needs_review else "ready")
    except Exception as exc:  # noqa: BLE001 - record failure, never crash the import
        imp.failure_message = str(exc)[:2000]
        _set_status(imp, "failed")
    db.commit()
    db.refresh(imp)
    return imp


def save_reviewed(
    db: Session, import_id: UUID, user: CurrentUser, reviewed: ExamDocument
) -> ExamImport:
    imp = get_import(db, import_id, user)
    if imp.status not in ("needs_review", "ready"):
        raise HTTPException(409, f"import is not reviewable (status={imp.status})")
    report = validate_exam_document(reviewed)
    imp.reviewed_document_json = reviewed.model_dump(mode="json")
    imp.validation_json = report.model_dump(mode="json")
    imp.needs_review = report.needs_review
    imp.reviewed_at = _now()
    if imp.status == "needs_review" and not report.needs_review:
        _set_status(imp, "ready")
    db.commit()
    db.refresh(imp)
    return imp


def _referenced_local_ids(doc: ExamDocument) -> set[str]:
    ids: set[str] = set()

    def walk(node: QuestionNode) -> None:
        for block in node.content:
            if block.asset is not None:
                ids.add(block.asset.local_id)
        for child in node.children:
            walk(child)

    for section in doc.sections:
        for question in section.questions:
            walk(question)
    return ids


def _create_question(
    db: Session, user: CurrentUser, draft: QuestionIngestDraft
) -> Question:
    payload = QuestionCreate(
        internal_title=draft.internal_title,
        subject=draft.subject or "Imported",
        level=draft.level or "Imported",
        tags_json=draft.tags_json,
        source_note=draft.source_note,
        content_json=draft.content_json,
        status="ready",
    )
    question = Question(workspace_id=user.workspace_id, **payload.model_dump(mode="json"))
    db.add(question)
    return question


def approve_import(
    db: Session, import_id: UUID, user: CurrentUser, storage: StorageBackend
) -> ExamImport:
    imp = get_import(db, import_id, user)
    if imp.status not in ("needs_review", "ready"):
        raise HTTPException(409, f"import is not approvable (status={imp.status})")
    if imp.reviewed_document_json is None:
        raise HTTPException(409, "import has no reviewed document")

    reviewed = ExamDocument.model_validate(imp.reviewed_document_json)
    report = validate_exam_document(reviewed)
    blocking = [i for i in report.issues if i.severity == "blocking"]
    if blocking:
        raise HTTPException(
            409, f"cannot approve: {len(blocking)} blocking issue(s) remain"
        )

    _set_status(imp, "materializing")

    asset_map: dict[str, UUID] = {}
    for local_id in sorted(_referenced_local_ids(reviewed)):
        entry = imp.asset_manifest.get(local_id)
        if entry is None:
            raise HTTPException(409, f"missing asset source for {local_id!r}")
        blob = storage.get(entry["storage_key"])
        asset = create_asset_from_bytes(db, user, storage, "question_image", blob, local_id)
        asset_map[local_id] = asset.id

    drafts = materialize_exam_document(
        reviewed, asset_id_for=lambda lid: asset_map[lid]
    )
    question_ids: list[str] = []
    for draft in drafts:
        question = _create_question(db, user, draft)
        db.flush()  # assign id
        question_ids.append(str(question.id))

    imp.created_question_ids = question_ids
    imp.completed_at = _now()
    _set_status(imp, "completed")
    db.commit()
    db.refresh(imp)
    return imp
