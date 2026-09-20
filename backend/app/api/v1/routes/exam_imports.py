"""Exam import workflow routes: upload -> extract -> review -> approve."""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db
from app.core.storage import LocalDirStorage
from app.models import ExamImport
from app.schemas.exam_import import ExamImportDetail, ExamImportSummary
from app.services import exam_imports
from app.services.assets import sniff_mime

router = APIRouter(prefix="/exam-imports", tags=["exam-imports"])
User = Annotated[CurrentUser, Depends(get_current_user)]
Db = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _summary(imp: ExamImport) -> ExamImportSummary:
    return ExamImportSummary.model_validate(imp)


def _detail(imp: ExamImport) -> ExamImportDetail:
    return ExamImportDetail.model_validate(imp)


@router.post("", response_model=ExamImportDetail, status_code=201)
async def create_exam_import(
    file: Annotated[UploadFile, File()],
    current_user: User,
    db: Db,
    settings: SettingsDep,
    import_type: Annotated[Literal["question_paper", "answer_sheet"], Form()] = "question_paper",
) -> ExamImportDetail:
    """Upload a .docx / .pdf / .doc exam (question paper or answer sheet)."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")
    storage = LocalDirStorage(settings.storage_local_dir)
    imp = exam_imports.create_import(
        db,
        current_user,
        storage,
        settings,
        file.filename or "upload",
        data,
        import_type=import_type,
    )
    return _detail(imp)


@router.get("", response_model=list[ExamImportSummary])
def list_exam_imports(current_user: User, db: Db) -> list[ExamImportSummary]:
    return [_summary(imp) for imp in exam_imports.list_imports(db, current_user)]


@router.get("/{import_id}", response_model=ExamImportDetail)
def get_exam_import(import_id: UUID, current_user: User, db: Db) -> ExamImportDetail:
    return _detail(exam_imports.get_import(db, import_id, current_user))


@router.put("/{import_id}/reviewed", response_model=ExamImportDetail)
def update_reviewed(
    import_id: UUID, reviewed: dict[str, Any], current_user: User, db: Db
) -> ExamImportDetail:
    """Save a human-reviewed document / answer sheet (re-validated; never overwrites extracted)."""
    imp = exam_imports.save_reviewed(db, import_id, current_user, reviewed)
    return _detail(imp)


@router.post("/{import_id}/approve", response_model=ExamImportDetail)
def approve_import(
    import_id: UUID, current_user: User, db: Db, settings: SettingsDep
) -> ExamImportDetail:
    """Validate the reviewed document, materialize and persist Questions."""
    storage = LocalDirStorage(settings.storage_local_dir)
    imp = exam_imports.approve_import(db, import_id, current_user, storage)
    return _detail(imp)


@router.get("/{import_id}/assets/{local_id}")
def get_import_asset(
    import_id: UUID,
    local_id: str,
    current_user: User,
    db: Db,
    settings: SettingsDep,
) -> Response:
    """Serve a raster image extracted from this import (by local_id)."""
    imp = exam_imports.get_import(db, import_id, current_user)
    entry = imp.asset_manifest.get(local_id)
    if entry is None:
        raise HTTPException(404, "asset not found")
    blob = LocalDirStorage(settings.storage_local_dir).get(entry["storage_key"])
    mime = entry.get("mime_type") or sniff_mime(blob) or "application/octet-stream"
    return Response(blob, media_type=mime)
