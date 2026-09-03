from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.authorization import assert_workspace_access


def test_workspace_access_allows_matching_workspace() -> None:
    workspace_id = uuid4()
    assert_workspace_access(workspace_id, workspace_id)


def test_workspace_access_rejects_other_workspace() -> None:
    with pytest.raises(HTTPException) as exc_info:
        assert_workspace_access(uuid4(), uuid4())
    assert exc_info.value.status_code == 404
