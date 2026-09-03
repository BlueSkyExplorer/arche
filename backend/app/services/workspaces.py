from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.models.workspace import Workspace


def get_current_workspace(db: Session, current_user: CurrentUser) -> Workspace:
    workspace = db.get(Workspace, current_user.workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Workspace not found")
    return workspace
