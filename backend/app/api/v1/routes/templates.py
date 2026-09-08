from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.deps import get_current_user, get_db
from app.schemas.template_profile import (
    TemplateProfileCreate,
    TemplateProfilePatch,
    TemplateProfileRead,
)
from app.services import templates
from app.services.template_import import TemplateImportDraft, import_template_docx

router = APIRouter(prefix="/templates", tags=["templates"])
User = Annotated[CurrentUser, Depends(get_current_user)]
Db = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[TemplateProfileRead])
def template_list(current_user: User, db: Db) -> list[TemplateProfileRead]:
    return [
        TemplateProfileRead.model_validate(x) for x in templates.list_templates(db, current_user)
    ]


@router.post("", response_model=TemplateProfileRead, status_code=201)
def template_create(data: TemplateProfileCreate, current_user: User, db: Db) -> TemplateProfileRead:
    return TemplateProfileRead.model_validate(templates.create_template(db, current_user, data))


@router.post("/import", response_model=TemplateImportDraft)
async def template_import(
    current_user: User,
    db: Db,
    file: Annotated[UploadFile, File()],
) -> TemplateImportDraft:
    """Best-effort: map an uploaded school-format .docx into a template draft.

    Nothing is persisted (teacher reviews the draft, then saves via POST
    /templates). Rejects .docm (macro-enabled) and oversized uploads.
    """
    filename = (file.filename or "").lower()
    if not filename.endswith(".docx"):
        raise HTTPException(status_code=415, detail="Only .docx format files are supported")
    if filename.endswith(".docm") or ".docm" in filename:
        raise HTTPException(status_code=415, detail="Macro-enabled documents are not supported")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        return import_template_docx(data)
    except Exception as exc:  # noqa: BLE001 - surface controlled error
        raise HTTPException(status_code=422, detail=f"Could not parse DOCX: {exc}") from exc


@router.get("/{template_id}", response_model=TemplateProfileRead)
def template_detail(template_id: UUID, current_user: User, db: Db) -> TemplateProfileRead:
    return TemplateProfileRead.model_validate(
        templates.get_template_profile(db, template_id, current_user)
    )


@router.patch("/{template_id}", response_model=TemplateProfileRead)
def template_patch(
    template_id: UUID, data: TemplateProfilePatch, current_user: User, db: Db
) -> TemplateProfileRead:
    return TemplateProfileRead.model_validate(
        templates.patch_template(db, template_id, current_user, data)
    )
