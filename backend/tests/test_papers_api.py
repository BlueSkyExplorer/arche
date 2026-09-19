import copy
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PaperQuestion, Question, Workspace
from tests.conftest import switch_workspace


def question_payload(title: str, text: str, marks: str) -> dict[str, Any]:
    return {
        "internal_title": title,
        "subject": "Math",
        "level": "S1",
        "status": "ready",
        "content_json": {
            "type": "doc",
            "marks": marks,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
        },
    }


def create_paper_tree(client: TestClient, template_payload: dict[str, Any]):
    template = client.post("/api/v1/templates", json=template_payload).json()
    paper = client.post(
        "/api/v1/papers",
        json={
            "template_profile_id": template["id"],
            "title": "Draft",
            "subject": "Math",
            "level": "S1",
        },
    ).json()
    sections = [
        client.post(
            f"/api/v1/papers/{paper['id']}/sections", json={"title": title, "position": position}
        ).json()
        for position, title in enumerate(("A", "B"))
    ]
    questions = [
        client.post("/api/v1/questions", json=question_payload(f"Q{i}", text, marks)).json()
        for i, (text, marks) in enumerate((("First wording", "2.5"), ("Second wording", "4")), 1)
    ]
    return paper, sections, questions


@pytest.mark.db
def test_paper_edit_reorder_numbering_and_section_cascade(
    api_client: TestClient, db_session: Session, template_payload: dict[str, Any]
) -> None:
    paper, sections, questions = create_paper_tree(api_client, template_payload)
    patched = api_client.patch(
        f"/api/v1/papers/{paper['id']}",
        json={
            "title": "Final examination",
            "duration_minutes": 75,
            "instructions_json": [{"text": "Answer all questions"}],
        },
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Final examination"

    # Reorder sections through a vacant position to respect the uniqueness constraint.
    assert (
        api_client.patch(
            f"/api/v1/papers/{paper['id']}/sections/{sections[0]['id']}", json={"position": 2}
        ).status_code
        == 200
    )
    assert (
        api_client.patch(
            f"/api/v1/papers/{paper['id']}/sections/{sections[1]['id']}", json={"position": 0}
        ).status_code
        == 200
    )

    section_id = sections[0]["id"]
    first_order = [
        {"question_id": questions[0]["id"]},
        {"question_id": questions[1]["id"]},
    ]
    assert (
        api_client.put(
            f"/api/v1/papers/{paper['id']}/sections/{section_id}/questions", json=first_order
        ).status_code
        == 200
    )
    detail = api_client.get(f"/api/v1/papers/{paper['id']}").json()
    assert Decimal(detail["total_marks"]) == Decimal("6.5")
    selected = next(section for section in detail["sections"] if section["id"] == section_id)
    assert [row["label"] for row in selected["questions"]] == ["1.", "2."]
    # Paper detail must embed the reusable question payload (the paper builder renders from it).
    embedded = {row["question_id"]: row["question"] for row in selected["questions"]}
    assert set(embedded) == {questions[0]["id"], questions[1]["id"]}
    assert embedded[questions[0]["id"]]["internal_title"] == "Q1"
    assert embedded[questions[0]["id"]]["marks"] == "2.5"
    assert embedded[questions[0]["id"]]["content_json"]["type"] == "doc"

    originals = {}
    for item in questions:
        row = db_session.get(Question, item["id"])
        assert row is not None
        originals[item["id"]] = (copy.deepcopy(row.content_json), row.updated_at)
    reordered = api_client.put(
        f"/api/v1/papers/{paper['id']}/sections/{section_id}/questions",
        json=[
            {"question_id": questions[1]["id"]},
            {"question_id": questions[0]["id"]},
        ],
    )
    assert reordered.status_code == 200
    assert [row["question_id"] for row in reordered.json()] == [
        questions[1]["id"],
        questions[0]["id"],
    ]
    db_session.expire_all()
    for item in questions:
        row = db_session.get(Question, item["id"])
        assert row is not None
        assert (row.content_json, row.updated_at) == originals[item["id"]]

    assert (
        api_client.delete(f"/api/v1/papers/{paper['id']}/sections/{section_id}").status_code == 204
    )
    assert (
        db_session.scalars(
            select(PaperQuestion).where(PaperQuestion.paper_section_id == section_id)
        ).all()
        == []
    )


@pytest.mark.db
def test_question_delete_conflicts_when_active_paper_references_it(
    api_client: TestClient, template_payload: dict[str, Any]
) -> None:
    paper, sections, questions = create_paper_tree(api_client, template_payload)
    api_client.put(
        f"/api/v1/papers/{paper['id']}/sections/{sections[0]['id']}/questions",
        json=[{"question_id": questions[0]["id"]}],
    )
    response = api_client.delete(f"/api/v1/questions/{questions[0]['id']}")
    assert response.status_code == 409
    assert "non-archived paper" in response.json()["detail"]


@pytest.mark.db
def test_cross_workspace_paper_section_and_export_are_404(
    api_client: TestClient, db_session: Session, template_payload: dict[str, Any]
) -> None:
    paper, sections, _ = create_paper_tree(api_client, template_payload)
    export = api_client.post(f"/api/v1/papers/{paper['id']}/export?format=docx").json()
    other = Workspace(name="Other", owner_user_id=f"{uuid4()}@example.com")
    db_session.add(other)
    db_session.commit()
    switch_workspace(api_client, other.id)
    assert api_client.get(f"/api/v1/papers/{paper['id']}").status_code == 404
    assert (
        api_client.patch(
            f"/api/v1/papers/{paper['id']}/sections/{sections[0]['id']}", json={"title": "x"}
        ).status_code
        == 404
    )
    assert api_client.get(f"/api/v1/exports/{export['id']}/download").status_code == 404


def _snapshot_text(snapshot: dict[str, Any]) -> str:
    return snapshot["content"][0]["content"][0]["text"]


@pytest.mark.db
def test_paper_snapshots_question_content_on_add(
    api_client: TestClient, db_session: Session, template_payload: dict[str, Any]
) -> None:
    paper, sections, questions = create_paper_tree(api_client, template_payload)
    section_id = sections[0]["id"]
    assert (
        api_client.put(
            f"/api/v1/papers/{paper['id']}/sections/{section_id}/questions",
            json=[{"question_id": questions[0]["id"]}],
        ).status_code
        == 200
    )

    row = db_session.scalars(
        select(PaperQuestion).where(PaperQuestion.paper_section_id == section_id)
    ).one()
    # The snapshot is a frozen copy of the source content, with provenance.
    assert _snapshot_text(row.content_snapshot_json) == "First wording"
    assert str(row.question_id) == questions[0]["id"]

    # Editing the source question afterwards leaves the snapshot untouched.
    api_client.patch(
        f"/api/v1/questions/{questions[0]['id']}",
        json={
            "content_json": {
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Changed wording"}]}
                ],
            }
        },
    )
    db_session.expire_all()
    reloaded = db_session.get(PaperQuestion, row.id)
    assert reloaded is not None
    assert _snapshot_text(reloaded.content_snapshot_json) == "First wording"


@pytest.mark.db
def test_paper_total_is_sum_of_leaf_marks(
    api_client: TestClient, template_payload: dict[str, Any]
) -> None:
    content = {
        "type": "doc",
        "content": [
            {
                "type": "subQuestion",
                "attrs": {"label": "(a)", "marks": "2"},
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "a"}]}],
            },
            {
                "type": "subQuestion",
                "attrs": {"label": "(b)", "marks": "3"},
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "b"}]}],
            },
        ],
    }
    question = api_client.post(
        "/api/v1/questions",
        json={
            "internal_title": "Multi-part",
            "subject": "Math",
            "level": "S1",
            "status": "ready",
            "content_json": content,
        },
    ).json()
    paper, sections, _ = create_paper_tree(api_client, template_payload)
    section_id = sections[0]["id"]
    assert (
        api_client.put(
            f"/api/v1/papers/{paper['id']}/sections/{section_id}/questions",
            json=[{"question_id": question["id"]}],
        ).status_code
        == 200
    )
    detail = api_client.get(f"/api/v1/papers/{paper['id']}").json()
    assert Decimal(detail["total_marks"]) == Decimal("5")
