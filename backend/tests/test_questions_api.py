"""Question create/patch API round-trips leaf marks in the content tree."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.db
def test_leaf_marks_roundtrip_through_create(api_client: TestClient) -> None:
    # Standalone: leaf mark on the doc root.
    r = api_client.post(
        "/api/v1/questions",
        json={
            "internal_title": "Standalone",
            "subject": "Math",
            "level": "S1",
            "marks": "3",
            "status": "ready",
            "content_json": {"type": "doc", "marks": "3", "content": [{"type": "paragraph"}]},
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["content_json"]["marks"] == "3"

    # Multi-part: leaf marks on sub-questions.
    r = api_client.post(
        "/api/v1/questions",
        json={
            "internal_title": "Multi",
            "subject": "Math",
            "level": "S1",
            "marks": "5",
            "status": "ready",
            "content_json": {
                "type": "doc",
                "content": [
                    {
                        "type": "subQuestion",
                        "attrs": {"label": "(a)", "marks": "2"},
                        "content": [{"type": "paragraph"}],
                    },
                    {
                        "type": "subQuestion",
                        "attrs": {"label": "(b)", "marks": "3"},
                        "content": [{"type": "paragraph"}],
                    },
                ],
            },
        },
    )
    assert r.status_code == 201, r.text
    subs = r.json()["content_json"]["content"]
    assert [s["attrs"]["marks"] for s in subs] == ["2", "3"]

    # Non-leaf (sub-question with nested subs) carrying a mark must be rejected.
    r = api_client.post(
        "/api/v1/questions",
        json={
            "internal_title": "Bad",
            "subject": "Math",
            "level": "S1",
            "marks": "1",
            "status": "ready",
            "content_json": {
                "type": "doc",
                "content": [
                    {
                        "type": "subQuestion",
                        "attrs": {"label": "(a)", "marks": "5"},
                        "content": [
                            {
                                "type": "subQuestion",
                                "attrs": {"label": "(i)"},
                                "content": [{"type": "paragraph"}],
                            }
                        ],
                    }
                ],
            },
        },
    )
    assert r.status_code == 422


@pytest.mark.db
def test_patch_roundtrips_leaf_marks(api_client: TestClient) -> None:
    created = api_client.post(
        "/api/v1/questions",
        json={
            "internal_title": "Q",
            "subject": "Math",
            "level": "S1",
            "marks": "2",
            "status": "draft",
            "content_json": {"type": "doc", "marks": "2", "content": [{"type": "paragraph"}]},
        },
    ).json()
    r = api_client.patch(
        f"/api/v1/questions/{created['id']}",
        json={"content_json": {"type": "doc", "marks": "7", "content": [{"type": "paragraph"}]}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["content_json"]["marks"] == "7"


@pytest.mark.db
def test_zero_leaf_mark_is_preserved(api_client: TestClient) -> None:
    # A leaf mark of 0 must round-trip as 0, not be stripped to null/absent.
    r = api_client.post(
        "/api/v1/questions",
        json={
            "internal_title": "Zero",
            "subject": "Math",
            "level": "S1",
            "marks": "0",
            "status": "ready",
            "content_json": {
                "type": "doc",
                "content": [
                    {
                        "type": "subQuestion",
                        "attrs": {"label": "(a)", "marks": "0"},
                        "content": [{"type": "paragraph"}],
                    }
                ],
            },
        },
    )
    assert r.status_code == 201, r.text
    subs = r.json()["content_json"]["content"]
    assert subs[0]["attrs"]["marks"] == "0"