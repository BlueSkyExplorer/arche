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


def test_editor_camel_case_attrs_parse_exactly() -> None:
    content = DocNode.model_validate(
        {
            "type": "doc",
            "content": [
                {
                    "type": "image",
                    "attrs": {
                        "assetId": "11111111-1111-1111-1111-111111111111",
                        "alt": None,
                        "widthMm": 35,
                    },
                },
                {
                    "type": "subQuestion",
                    "attrs": {"label": "(a)"},
                    "content": [{"type": "paragraph"}],
                },
                {"type": "answerSpace", "attrs": {"lines": 3}},
                {"type": "answerSpace", "attrs": {"blankHeightMm": 12.5}},
            ],
        }
    )
    image = content.content[0]
    assert image.type == "image"
    assert image.attrs.width_mm == 35
    assert image.attrs.alt is None


def test_nested_table_in_table_cell_is_rejected() -> None:
    nested = {
        "type": "table",
        "content": [
            {
                "type": "tableRow",
                "content": [{"type": "tableCell", "content": [{"type": "paragraph"}]}],
            }
        ],
    }
    outer = {
        "type": "table",
        "content": [{"type": "tableRow", "content": [{"type": "tableCell", "content": [nested]}]}],
    }
    with pytest.raises(ValidationError, match="tables may not be nested"):
        DocNode.model_validate({"type": "doc", "content": [outer]})


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
