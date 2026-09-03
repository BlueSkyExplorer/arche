from uuid import UUID

from fastapi import HTTPException, status


def assert_workspace_access(object_workspace_id: UUID, user_workspace_id: UUID) -> None:
    if object_workspace_id != user_workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace access denied")
