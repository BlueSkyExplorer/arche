from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.deps import get_current_user, get_db
from app.schemas.workspace import WorkspaceRead
from app.services.workspaces import get_current_workspace

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("/me", response_model=WorkspaceRead)
def workspace_me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkspaceRead:
    return WorkspaceRead.model_validate(get_current_workspace(db, current_user))
