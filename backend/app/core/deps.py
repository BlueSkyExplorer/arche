from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.auth import AuthBackend, CurrentUser, StubAuthBackend
from app.core.config import Settings, get_settings
from app.core.database import session_scope
from app.models.workspace import Workspace

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session]:
    yield from session_scope()


def get_auth_backend(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthBackend:
    return StubAuthBackend(settings.stub_auth_email, db)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    backend: Annotated[AuthBackend, Depends(get_auth_backend)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentUser:
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    current_user = backend.verify_token(credentials.credentials)
    if current_user is None or db.get(Workspace, current_user.workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return current_user
