"""Synchronous service boundary for immutable answer-sheet render/export records."""

from __future__ import annotations

import hashlib
import logging
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.storage import StorageBackend
from app.document.renderer import RenderTemplateProfile
from app.document.renderer.answer_sheet import render_answer_sheet
from app.exam.extraction.answer_sheet import sheet_from_dict
from app.models import AnswerSheetExport, Asset, TemplateProfile
from app.schemas.answer_sheet_export import DocumentMetadata
from app.schemas.template_profile import TemplateProfileConfig
from app.services.authorization import assert_workspace_access
from app.services.exam_imports import get_import

logger = logging.getLogger(__name__)


def get_answer_sheet_export(
    db: Session, export_id: UUID, user: CurrentUser
) -> AnswerSheetExport:
    record = db.get(AnswerSheetExport, export_id)
    if record is None:
        raise HTTPException(404, "Answer-sheet export not found")
    assert_workspace_access(record.workspace_id, user.workspace_id)
    return record


def _template_snapshot(template: TemplateProfile) -> dict[str, object]:
    config = TemplateProfileConfig.model_validate(
        {
            "page_config_json": template.page_config_json,
            "typography_config_json": template.typography_config_json,
            "header_config_json": template.header_config_json,
            "footer_config_json": template.footer_config_json,
            "numbering_config_json": template.numbering_config_json,
            "section_style_config_json": template.section_style_config_json,
            "question_style_config_json": template.question_style_config_json,
            "answer_sheet_layout_json": template.answer_sheet_layout_json,
            "role_styles": template.role_styles,
        }
    )
    return {
        "name": template.name,
        "version": template.version,
        "logo_asset_id": str(template.logo_asset_id) if template.logo_asset_id else None,
        "source_docx_storage_key": template.source_docx_storage_key,
        "source_docx_sha256": template.source_docx_sha256,
        "ooxml_layout_blueprint_json": template.ooxml_layout_blueprint_json,
        "config": config.model_dump(mode="json"),
    }


def create_answer_sheet_export(
    db: Session,
    import_id: UUID,
    template_id: UUID,
    metadata: DocumentMetadata,
    purpose: Literal["preview", "export"],
    user: CurrentUser,
    storage: StorageBackend,
) -> AnswerSheetExport:
    imp = get_import(db, import_id, user)
    if imp.import_type != "answer_sheet" or imp.status != "completed":
        raise HTTPException(409, "Only completed answer-sheet imports can be formatted")
    if imp.reviewed_answer_sheet_json is None:
        raise HTTPException(409, "Completed import has no reviewed answer sheet")
    template = db.get(TemplateProfile, template_id)
    if template is None or template.workspace_id != user.workspace_id:
        raise HTTPException(404, "Template not found")

    sheet_snapshot = imp.reviewed_answer_sheet_json
    template_snapshot = _template_snapshot(template)
    record = AnswerSheetExport(
        workspace_id=user.workspace_id,
        exam_import_id=imp.id,
        template_profile_id=template.id,
        template_version=template.version,
        reviewed_answer_sheet_snapshot=sheet_snapshot,
        template_config_snapshot=template_snapshot,
        metadata_snapshot=metadata.model_dump(mode="json"),
        purpose=purpose,
        format="docx",
        status="failed",
        storage_key=None,
        error_message=None,
        validation_json={"valid": False, "issues": [], "stats": {}},
    )
    db.add(record)
    db.flush()

    answer_assets: dict[str, bytes] = {}
    for local_id, entry in imp.asset_manifest.items():
        if not isinstance(entry, dict) or not entry.get("storage_key"):
            continue
        try:
            answer_assets[str(local_id)] = storage.get(str(entry["storage_key"]))
        except FileNotFoundError:
            continue

    config = TemplateProfileConfig.model_validate(template_snapshot["config"])
    source_docx: bytes | None = None
    source_key = template_snapshot.get("source_docx_storage_key")
    source_digest = template_snapshot.get("source_docx_sha256")
    source_required = isinstance(source_key, str) or isinstance(source_digest, str)
    if isinstance(source_key, str) and isinstance(source_digest, str):
        try:
            candidate = storage.get(source_key)
        except FileNotFoundError:
            candidate = b""
        if hashlib.sha256(candidate).hexdigest() == source_digest:
            source_docx = candidate
    if source_required and source_docx is None:
        record.status = "blocked"
        record.error_message = "Immutable template source artifact is unavailable"
        record.validation_json = {
            "valid": False,
            "blocking_count": 1,
            "issues": [
                {
                    "code": "template_source_unavailable",
                    "severity": "blocking",
                    "message": "Immutable template source artifact is unavailable.",
                    "path": "template",
                }
            ],
            "stats": {},
        }
        db.commit()
        db.refresh(record)
        return record

    snapshot_blueprint = template_snapshot.get("ooxml_layout_blueprint_json", {})
    if not isinstance(snapshot_blueprint, dict):
        snapshot_blueprint = {}

    profile = RenderTemplateProfile(
        school_name="",
        logo_asset_id=template.logo_asset_id,
        config=config,
        layout_blueprint=snapshot_blueprint,
        source_docx=source_docx,
    )

    def resolve_logo(asset_id: UUID) -> bytes:
        asset = db.get(Asset, asset_id)
        if asset is None or asset.workspace_id != user.workspace_id:
            raise ValueError("Referenced template logo is unavailable")
        return storage.get(asset.storage_key)

    try:
        result = render_answer_sheet(
            sheet_from_dict(sheet_snapshot), profile, metadata, answer_assets, resolve_logo
        )
        record.validation_json = result.validation
        if result.docx is None:
            record.status = "blocked"
            record.error_message = "Render validation found content-loss risks"
        else:
            key = f"{user.workspace_id}/answer-sheet-exports/{record.id}.docx"
            storage.put(key, result.docx)
            record.storage_key = key
            record.status = "succeeded"
    except Exception:  # noqa: BLE001 - controlled record failure, no content in logs
        logger.exception(
            "Answer-sheet rendering failed import_id=%s export_id=%s", imp.id, record.id
        )
        record.status = "failed"
        record.error_message = "Document rendering failed"
    db.commit()
    db.refresh(record)
    return record
