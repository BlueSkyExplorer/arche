from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db
from app.core.storage import LocalDirStorage
from app.schemas.domain import AssetRead
from app.services import assets

router = APIRouter(prefix="/assets", tags=["assets"])
User = Annotated[CurrentUser, Depends(get_current_user)]
Db = Annotated[Session, Depends(get_db)]


@router.post("", response_model=AssetRead, status_code=201)
async def upload_asset(
    current_user: User,
    db: Db,
    settings: Annotated[Settings, Depends(get_settings)],
    kind: Annotated[Literal["logo", "question_image"], Form()],
    file: Annotated[UploadFile, File()],
) -> AssetRead:
    return AssetRead.model_validate(
        await assets.create_asset(
            db, current_user, LocalDirStorage(settings.storage_local_dir), kind, file
        )
    )


@router.get("/{asset_id}/content")
def asset_content(
    asset_id: UUID, current_user: User, db: Db, settings: Annotated[Settings, Depends(get_settings)]
) -> Response:
    asset = assets.get_asset(db, asset_id, current_user)
    return Response(
        LocalDirStorage(settings.storage_local_dir).get(asset.storage_key),
        media_type=asset.mime_type,
        headers={"Content-Disposition": f'inline; filename="{asset.original_filename}"'},
    )
