import base64
import io
import os
import zipfile
from pathlib import Path
from typing import Any

import pytest
from docx import Document
from fastapi.testclient import TestClient

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
DEFAULT_LIBREOFFICE = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")


def create_exportable_paper(client: TestClient, template_payload: dict[str, Any]) -> str:
    template = client.post("/api/v1/templates", json=template_payload)
    assert template.status_code == 201, template.text
    asset_response = client.post(
        "/api/v1/assets",
        data={"kind": "question_image"},
        files={"file": ("diagram.png", PNG, "image/png")},
    )
    assert asset_response.status_code == 201, asset_response.text
    asset_id = asset_response.json()["id"]
    questions = [
        {
            "internal_title": "Image question",
            "subject": "Math",
            "level": "S1",
            "marks": "2",
            "status": "ready",
            "content_json": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Preserve this exact first wording."}],
                    },
                    {"type": "image", "attrs": {"asset_id": asset_id, "alt": "diagram"}},
                ],
            },
        },
        {
            "internal_title": "Bilingual table question",
            "subject": "Math",
            "level": "S1",
            "marks": "5",
            "status": "ready",
            "content_json": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "第二題 wording must remain unchanged."}
                        ],
                    },
                    {
                        "type": "subQuestion",
                        "attrs": {"label": "(a)"},
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "子題 Sub-question"}],
                            }
                        ],
                    },
                    {
                        "type": "table",
                        "content": [
                            {
                                "type": "tableRow",
                                "content": [
                                    {
                                        "type": "tableCell",
                                        "content": [
                                            {
                                                "type": "paragraph",
                                                "content": [{"type": "text", "text": "中文"}],
                                            }
                                        ],
                                    },
                                    {
                                        "type": "tableCell",
                                        "content": [
                                            {
                                                "type": "paragraph",
                                                "content": [{"type": "text", "text": "English"}],
                                            }
                                        ],
                                    },
                                ],
                            }
                        ],
                    },
                ],
            },
        },
    ]
    question_ids = []
    for payload in questions:
        response = client.post("/api/v1/questions", json=payload)
        assert response.status_code == 201, response.text
        question_ids.append(response.json()["id"])
    paper = client.post(
        "/api/v1/papers",
        json={
            "template_profile_id": template.json()["id"],
            "title": "Integrated Paper",
            "subject": "Math",
            "level": "S1",
            "instructions_json": [{"text": "Read carefully"}],
        },
    )
    assert paper.status_code == 201, paper.text
    paper_id = paper.json()["id"]
    section = client.post(
        f"/api/v1/papers/{paper_id}/sections", json={"title": "Section A", "position": 0}
    )
    assert section.status_code == 201, section.text
    ordered = client.put(
        f"/api/v1/papers/{paper_id}/sections/{section.json()['id']}/questions",
        json=[{"question_id": item} for item in question_ids],
    )
    assert ordered.status_code == 200, ordered.text
    return paper_id


def assert_docx(client: TestClient, paper_id: str) -> dict[str, Any]:
    response = client.post(f"/api/v1/papers/{paper_id}/export?format=docx")
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["status"] == "succeeded"
    download = client.get(f"/api/v1/exports/{item['id']}/download")
    assert download.status_code == 200
    assert download.content.startswith(b"PK")
    document = Document(io.BytesIO(download.content))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Preserve this exact first wording." in text
    assert "第二題 wording must remain unchanged." in text
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        relationships = archive.read("word/_rels/document.xml.rels")
        assert b"relationships/image" in relationships
        assert any(name.startswith("word/media/") for name in archive.namelist())
    return item


@pytest.mark.db
def test_docx_survives_failed_pdf_export(
    api_client: TestClient, template_payload: dict[str, Any], tmp_path: Path
) -> None:
    paper_id = create_exportable_paper(api_client, template_payload)
    docx_export = assert_docx(api_client, paper_id)
    broken = tmp_path / "broken-soffice"
    broken.write_text("#!/bin/sh\nexit 9\n")
    os.chmod(broken, 0o755)
    api_client.test_settings.libreoffice_bin = str(broken)  # type: ignore[attr-defined]
    failed = api_client.post(f"/api/v1/papers/{paper_id}/export?format=pdf")
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert failed.json()["format"] == "pdf"
    assert failed.json()["error_message"]
    previous = api_client.get(f"/api/v1/exports/{docx_export['id']}")
    assert previous.json()["status"] == "succeeded"
    assert api_client.get(f"/api/v1/exports/{docx_export['id']}/download").content.startswith(b"PK")


@pytest.mark.db
@pytest.mark.libreoffice
@pytest.mark.skipif(not DEFAULT_LIBREOFFICE.exists(), reason="real LibreOffice binary is absent")
def test_real_libreoffice_pdf_export(
    api_client: TestClient, template_payload: dict[str, Any]
) -> None:
    paper_id = create_exportable_paper(api_client, template_payload)
    api_client.test_settings.libreoffice_bin = str(DEFAULT_LIBREOFFICE)  # type: ignore[attr-defined]
    response = api_client.post(f"/api/v1/papers/{paper_id}/export?format=pdf")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "succeeded", response.text
    download = api_client.get(f"/api/v1/exports/{response.json()['id']}/download")
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")
