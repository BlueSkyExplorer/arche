"""Case F: paper snapshot immutability across the materializer path (DB)."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exam.ir import ContentBlock, ExamDocument, QuestionNode, Section
from app.exam.materialization import materialize_exam_document
from app.models import PaperQuestion


def _para(text: str) -> ContentBlock:
    return ContentBlock(kind="paragraph", text=text)


def _q(label=None, own_marks=None, content=(), children=()):
    return QuestionNode(
        label=label, own_marks=own_marks, content=list(content), children=list(children)
    )


def _exam() -> ExamDocument:
    return ExamDocument(
        subject="Biology",
        level="S1",
        sections=[
            Section(
                questions=[
                    _q(
                        "Q1",
                        children=[
                            _q("(a)", Decimal("2"), [_para("part a")]),
                            _q("(b)", Decimal("3"), [_para("part b")]),
                        ],
                    )
                ]
            )
        ],
    )


@pytest.mark.db
def test_materialized_question_snapshot_immutability(
    api_client: TestClient, db_session: Session, template_payload: dict
) -> None:
    draft = materialize_exam_document(_exam())[0]
    created = api_client.post(
        "/api/v1/questions",
        json={
            "internal_title": draft.internal_title,
            "subject": draft.subject,
            "level": draft.level,
            "tags_json": [],
            "source_note": draft.source_note,
            "content_json": draft.content_json.model_dump(mode="json", by_alias=True),
            "status": "ready",
        },
    )
    assert created.status_code in (200, 201), created.text
    question_id = created.json()["id"]

    template = api_client.post("/api/v1/templates", json=template_payload).json()
    paper = api_client.post(
        "/api/v1/papers",
        json={
            "template_profile_id": template["id"],
            "title": "Paper",
            "subject": "Biology",
            "level": "S1",
        },
    ).json()
    section = api_client.post(
        f"/api/v1/papers/{paper['id']}/sections", json={"title": "A", "position": 0}
    ).json()
    assert (
        api_client.put(
            f"/api/v1/papers/{paper['id']}/sections/{section['id']}/questions",
            json=[{"question_id": question_id}],
        ).status_code
        == 200
    )

    row = db_session.scalars(
        select(PaperQuestion).where(PaperQuestion.paper_section_id == section["id"])
    ).one()
    before = row.content_snapshot_json

    # edit the source question afterwards
    assert (
        api_client.patch(
            f"/api/v1/questions/{question_id}",
            json={
                "content_json": {
                    "type": "doc",
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "Changed"}]}
                    ],
                }
            },
        ).status_code
        == 200
    )
    db_session.expire_all()
    reloaded = db_session.get(PaperQuestion, row.id)
    assert reloaded is not None
    assert reloaded.content_snapshot_json == before
    # the snapshot still carries the original multipart marks, not the edit
    assert "part a" in str(before)
