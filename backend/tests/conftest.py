import os
from collections.abc import Generator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db
from app.main import app
from app.models import Base, Workspace


@pytest.fixture
def db_engine() -> Generator[Engine]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is unset; PostgreSQL integration test skipped")
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        pytest.fail("TEST_DATABASE_URL must point to a PostgreSQL database")

    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session]:
    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    with factory() as session:
        yield session


@pytest.fixture
def api_client(db_session: Session, tmp_path: Path) -> Generator[TestClient]:
    workspace = Workspace(name="Test workspace", owner_user_id="test@example.com")
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)

    def override_db() -> Generator[Session]:
        yield db_session

    def override_user() -> CurrentUser:
        return CurrentUser(user_id=uuid4(), workspace_id=workspace.id)

    settings = Settings(
        DATABASE_URL=os.environ["TEST_DATABASE_URL"], STORAGE_LOCAL_DIR=tmp_path / "storage"
    )
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            client.workspace_id = workspace.id  # type: ignore[attr-defined]
            client.test_settings = settings  # type: ignore[attr-defined]
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def template_payload() -> dict[str, Any]:
    return {
        "name": "Default",
        "school_name": "Test School",
        "page_config_json": {
            "size": "A4",
            "margin_top_mm": 20,
            "margin_right_mm": 20,
            "margin_bottom_mm": 20,
            "margin_left_mm": 20,
        },
        "typography_config_json": {
            "chinese_font": "Noto Sans CJK TC",
            "latin_font": "Arial",
            "base_font_size_pt": 11,
            "line_spacing": 1.15,
        },
        "header_config_json": {"text": "Test header"},
        "footer_config_json": {"text": "Test footer", "page_numbering": True},
        "numbering_config_json": {"question_style": "1.", "sub_question_style": "(a)"},
        "section_style_config_json": {"spacing_before_pt": 6, "spacing_after_pt": 6},
        "question_style_config_json": {
            "spacing_before_pt": 3,
            "spacing_after_pt": 3,
            "marks_display": "right",
            "marks_format": "({marks} marks)",
            "default_answer_lines": 0,
        },
        "role_styles": {},
    }


def switch_workspace(client: TestClient, workspace_id: UUID) -> None:
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id=uuid4(), workspace_id=workspace_id
    )
