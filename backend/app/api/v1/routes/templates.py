from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.deps import get_current_user, get_db
from app.schemas.template_profile import TemplateProfileRead
from app.services.templates import get_template_profile

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/{template_id}", response_model=TemplateProfileRead)
def template_detail(
    template_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TemplateProfileRead:
    return TemplateProfileRead.model_validate(
        get_template_profile(db, template_id, current_user)
    )
