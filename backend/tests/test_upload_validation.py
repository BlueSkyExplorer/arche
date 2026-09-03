import base64
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Workspace
from tests.conftest import switch_workspace

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABBQJ//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPwF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPyF//9oADAMBAAIAAwAAABD/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/EB//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/EB//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/EB//2Q=="
)


def upload(client: TestClient, name: str, data: bytes, mime: str):
    return client.post(
        "/api/v1/assets", data={"kind": "question_image"}, files={"file": (name, data, mime)}
    )


@pytest.mark.db
def test_upload_rejection_matrix(api_client: TestClient) -> None:
    assert upload(api_client, "macro.docm", PNG, "image/png").status_code == 415
    assert upload(api_client, "wrong.jpg", PNG, "image/jpeg").status_code == 415
    assert (
        upload(api_client, "large.png", b"x" * (5 * 1024 * 1024 + 1), "image/png").status_code
        == 413
    )
    assert upload(api_client, "vector.svg", b"<svg/>", "image/svg+xml").status_code == 415


@pytest.mark.db
@pytest.mark.parametrize(
    ("name", "data", "mime"), [("tiny.png", PNG, "image/png"), ("tiny.jpg", JPEG, "image/jpeg")]
)
def test_valid_images_have_dimensions_and_safe_storage_keys(
    api_client: TestClient, name: str, data: bytes, mime: str
) -> None:
    response = upload(api_client, f"../unsafe/學校 {name}", data, mime)
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["width"] == item["height"] == 1
    assert re.fullmatch(
        rf"{api_client.workspace_id}/[0-9a-f-]+\.{name.rsplit('.', 1)[1]}", item["storage_key"]
    )
    assert item["original_filename"] == f"__ {name}"


@pytest.mark.db
def test_cross_workspace_asset_read_is_404(api_client: TestClient, db_session: Session) -> None:
    asset = upload(api_client, "tiny.png", PNG, "image/png").json()
    other = Workspace(name="Other", owner_user_id="other@example.com")
    db_session.add(other)
    db_session.commit()
    switch_workspace(api_client, other.id)
    assert api_client.get(f"/api/v1/assets/{asset['id']}/content").status_code == 404
