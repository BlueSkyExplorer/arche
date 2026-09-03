import pytest
from pydantic import ValidationError

from app.schemas.content import DocNode, parse_content


def test_content_returns_typed_nodes() -> None:
    content = parse_content(
        {
            "type": "doc",
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "exact"}]}],
        }
    )
    assert isinstance(content, DocNode)
    assert content.content[0].type == "paragraph"


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "doc", "unexpected": True},
        {"type": "doc", "content": [{"type": "mystery"}]},
        {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "x", "marks": [{"type": "unknown"}]}],
                }
            ],
        },
        {
            "type": "doc",
            "content": [{"type": "answerSpace", "attrs": {"lines": 1, "blankHeightMm": 2}}],
        },
        {"type": "doc", "content": [{"type": "image", "attrs": {"asset_id": "not-a-uuid"}}]},
    ],
)
def test_invalid_content_is_a_controlled_validation_error(payload: object) -> None:
    with pytest.raises(ValidationError):
        parse_content(payload)
