from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workspace import Workspace

STUB_USER_NAMESPACE = UUID("22493a4d-a6f0-45cd-a319-908f18ad6fb7")


@dataclass(frozen=True)
class CurrentUser:
    user_id: UUID
    workspace_id: UUID


class AuthBackend(Protocol):
    """Interface retained for a future real authentication adapter."""

    def verify_token(self, token: str) -> CurrentUser | None: ...


class StubAuthBackend:
    """Development-only auth; this does not verify Supabase JWTs."""

    def __init__(self, email: str, db: Session) -> None:
        self.email = email
        self.db = db

    def verify_token(self, token: str) -> CurrentUser | None:
        if not token.strip():
            return None
        workspace = self.db.scalar(
            select(Workspace).where(Workspace.owner_user_id == self.email)
        )
        if workspace is None:
            return None
        return CurrentUser(
            user_id=uuid5(STUB_USER_NAMESPACE, self.email.casefold()),
            workspace_id=workspace.id,
        )
