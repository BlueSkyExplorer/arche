from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db
from app.core.storage import LocalDirStorage
from app.schemas.answer_sheet_export import (
    AnswerSheetExportRead,
    AnswerSheetPreviewResponse,
    AnswerSheetRenderRequest,
)
from app.services import answer_sheet_exports

router = APIRouter(tags=["answer-sheet-exports"])
User = Annotated[CurrentUser, Depends(get_current_user)]
Db = Annotated[Session, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]


def _read(record: object) -> AnswerSheetExportRead:
    return AnswerSheetExportRead.model_validate(record)


@router.post(
    "/exam-imports/{import_id}/answer-sheet-preview",
    response_model=AnswerSheetPreviewResponse,
)
def preview_answer_sheet(
    import_id: UUID,
    data: AnswerSheetRenderRequest,
    current_user: User,
    db: Db,
    settings: Config,
) -> AnswerSheetPreviewResponse:
    record = answer_sheet_exports.create_answer_sheet_export(
        db,
        import_id,
        data.template_profile_id,
        data.metadata,
        "preview",
        current_user,
        LocalDirStorage(settings.storage_local_dir),
    )
    return AnswerSheetPreviewResponse(
        record=_read(record),
        preview={
            "metadata": record.metadata_snapshot,
            "answer_sheet": record.reviewed_answer_sheet_snapshot,
            "validation": record.validation_json,
            "template_version": record.template_version,
        },
    )


@router.post(
    "/exam-imports/{import_id}/answer-sheet-exports",
    response_model=AnswerSheetExportRead,
)
def export_answer_sheet(
    import_id: UUID,
    data: AnswerSheetRenderRequest,
    current_user: User,
    db: Db,
    settings: Config,
) -> AnswerSheetExportRead:
    return _read(
        answer_sheet_exports.create_answer_sheet_export(
            db,
            import_id,
            data.template_profile_id,
            data.metadata,
            "export",
            current_user,
            LocalDirStorage(settings.storage_local_dir),
        )
    )


@router.get("/answer-sheet-exports/{export_id}", response_model=AnswerSheetExportRead)
def answer_sheet_export_get(
    export_id: UUID, current_user: User, db: Db
) -> AnswerSheetExportRead:
    return _read(answer_sheet_exports.get_answer_sheet_export(db, export_id, current_user))


@router.get("/answer-sheet-exports/{export_id}/download")
def answer_sheet_export_download(
    export_id: UUID,
    current_user: User,
    db: Db,
    settings: Config,
) -> Response:
    record = answer_sheet_exports.get_answer_sheet_export(db, export_id, current_user)
    if record.status != "succeeded" or record.storage_key is None:
        raise HTTPException(409, "Answer-sheet export is not available")
    return Response(
        LocalDirStorage(settings.storage_local_dir).get(record.storage_key),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="answer-sheet-{record.id}.docx"'
        },
    )
