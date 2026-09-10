from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db
from app.schemas.template_profile import (
    TemplateProfileCreate,
    TemplateProfilePatch,
    TemplateProfileRead,
)
from app.services import templates
from app.services.doc_convert import convert_doc_to_docx
from app.services.template_import import TemplateImportDraft, import_template_docx
from app.services.uploads import validate_document_upload

router = APIRouter(prefix="/templates", tags=["templates"])
User = Annotated[CurrentUser, Depends(get_current_user)]
Db = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


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
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
) -> TemplateImportDraft:
    """Best-effort: map an uploaded school-format .doc/.docx into a template draft.

    Nothing is persisted (teacher reviews the draft, then saves via POST
    /templates). Rejects .docm (macro-enabled) and oversized uploads.
    """
    filename = (file.filename or "").lower()
    data = await file.read()
    ext = validate_document_upload(filename, len(data))
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if ext == ".doc":
        data = convert_doc_to_docx(data, settings)
    try:
        return import_template_docx(data)
    except Exception as exc:  # noqa: BLE001 - controlled error
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