from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.deps import get_current_user, get_db
from app.main import app
from app.models import Question, TemplateProfile, Workspace


@pytest.mark.db
def test_question_and_template_are_isolated_via_api(db_session: Session) -> None:
    own_workspace = Workspace(name="Own", owner_user_id="own@example.com")
    other_workspace = Workspace(name="Other", owner_user_id="other@example.com")
    db_session.add_all([own_workspace, other_workspace])
    db_session.flush()
    question = Question(
        workspace_id=other_workspace.id,
        internal_title="Private question",
        subject="Math",
        level="S1",
        tags_json=[],
        source_note=None,
        content_json={"type": "doc", "content": []},
        status="ready",
    )
    template = TemplateProfile(
        workspace_id=other_workspace.id,
        name="Private template",
        version=1,
        school_name="Other School",
        logo_asset_id=None,
        page_config_json={},
        typography_config_json={},
        header_config_json={},
        footer_config_json={},
        numbering_config_json={},
        section_style_config_json={},
        question_style_config_json={},
        is_active=True,
    )
    db_session.add_all([question, template])
    db_session.commit()

    def override_db() -> Generator[Session]:
        yield db_session

    def override_user() -> CurrentUser:
        return CurrentUser(user_id=uuid4(), workspace_id=own_workspace.id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        client = TestClient(app)
        question_response = client.get(f"/api/v1/questions/{question.id}")
        template_response = client.get(f"/api/v1/templates/{template.id}")
    finally:
        app.dependency_overrides.clear()

    assert question_response.status_code == 404
    assert template_response.status_code == 404
