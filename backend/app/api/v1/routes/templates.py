from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.deps import get_current_user, get_db
from app.schemas.template_profile import (
    TemplateProfileCreate,
    TemplateProfilePatch,
    TemplateProfileRead,
)
from app.services import templates

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
