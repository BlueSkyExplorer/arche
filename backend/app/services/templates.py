from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.models.template_profile import TemplateProfile
from app.services.authorization import assert_workspace_access


def get_template_profile(
    db: Session, template_id: UUID, current_user: CurrentUser
) -> TemplateProfile:
    template = db.get(TemplateProfile, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    assert_workspace_access(template.workspace_id, current_user.workspace_id)
    return template
