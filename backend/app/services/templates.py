from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.models import Asset, TemplateProfile
from app.schemas.template_profile import TemplateProfileCreate, TemplateProfilePatch
from app.services.authorization import assert_workspace_access


def get_template_profile(db: Session, template_id: UUID, user: CurrentUser) -> TemplateProfile:
    template = db.get(TemplateProfile, template_id)
    if template is None:
        raise HTTPException(404, "Template not found")
    assert_workspace_access(template.workspace_id, user.workspace_id)
    return template


def list_templates(db: Session, user: CurrentUser) -> list[TemplateProfile]:
    return list(
        db.scalars(
            select(TemplateProfile)
            .where(TemplateProfile.workspace_id == user.workspace_id)
            .order_by(TemplateProfile.created_at.desc())
        )
    )


def _check_logo(db: Session, logo_id: UUID | None, user: CurrentUser) -> None:
    if logo_id is None:
        return
    asset = db.get(Asset, logo_id)
    if asset is None or asset.workspace_id != user.workspace_id or asset.kind != "logo":
        raise HTTPException(404, "Logo asset not found")


def create_template(db: Session, user: CurrentUser, data: TemplateProfileCreate) -> TemplateProfile:
    _check_logo(db, data.logo_asset_id, user)
    values = data.model_dump(mode="json")
    template = TemplateProfile(workspace_id=user.workspace_id, version=1, **values)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def patch_template(
    db: Session, template_id: UUID, user: CurrentUser, data: TemplateProfilePatch
) -> TemplateProfile:
    template = get_template_profile(db, template_id, user)
    changes = data.model_dump(exclude_unset=True, mode="json")
    if "logo_asset_id" in changes:
        _check_logo(db, data.logo_asset_id, user)
    material = any(getattr(template, key) != value for key, value in changes.items())
    for key, value in changes.items():
        setattr(template, key, value)
    if material:
        template.version += 1
    db.commit()
    db.refresh(template)
    return template
