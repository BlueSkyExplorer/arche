from unittest.mock import Mock
from uuid import uuid4

from app.core.auth import StubAuthBackend
from app.models.workspace import Workspace


def test_stub_auth_rejects_empty_token() -> None:
    db = Mock()
    backend = StubAuthBackend("teacher@example.com", db)

    assert backend.verify_token("") is None
    db.scalar.assert_not_called()


def test_stub_auth_resolves_configured_owner() -> None:
    workspace = Workspace(
        id=uuid4(), name="Demo", owner_user_id="teacher@example.com"
    )
    db = Mock()
    db.scalar.return_value = workspace
    backend = StubAuthBackend("teacher@example.com", db)

    current_user = backend.verify_token("opaque-dev-token")

    assert current_user is not None
    assert current_user.workspace_id == workspace.id
    another_user = backend.verify_token("another-token")
    assert another_user is not None
    assert current_user.user_id == another_user.user_id
