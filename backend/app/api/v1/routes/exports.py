from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db
from app.core.storage import LocalDirStorage
from app.schemas.domain import ExportRead
from app.services import exports

router = APIRouter(tags=["exports"])
User = Annotated[CurrentUser, Depends(get_current_user)]
Db = Annotated[Session, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]


@router.post("/papers/{paper_id}/export", response_model=ExportRead)
def export_paper(
    paper_id: UUID,
    current_user: User,
    db: Db,
    settings: Config,
    format: Literal["docx", "pdf"] = Query(),
) -> ExportRead:
    return ExportRead.model_validate(
        exports.create_export(
            db,
            paper_id,
            current_user,
            format,
            LocalDirStorage(settings.storage_local_dir),
            settings,
        )
    )


@router.get("/exports/{export_id}", response_model=ExportRead)
def export_get(export_id: UUID, current_user: User, db: Db) -> ExportRead:
    return ExportRead.model_validate(exports.get_export(db, export_id, current_user))


@router.get("/exports/{export_id}/download")
def export_download(export_id: UUID, current_user: User, db: Db, settings: Config) -> Response:
    item = exports.get_export(db, export_id, current_user)
    if item.status != "succeeded" or item.storage_key is None:
        raise HTTPException(409, "Export is not available")
    media = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if item.format == "docx"
        else "application/pdf"
    )
    return Response(
        LocalDirStorage(settings.storage_local_dir).get(item.storage_key),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="paper-{item.id}.{item.format}"'},
    )
