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


def test_tiptap_link_attrs_are_accepted() -> None:
    content = parse_content(
        {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "OpenAI",
                            "marks": [
                                {
                                    "type": "link",
                                    "attrs": {
                                        "href": "https://openai.com",
                                        "target": "_blank",
                                        "rel": "noopener noreferrer",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    assert content.content[0].content[0].marks[0].attrs.rel == "noopener noreferrer"  # type: ignore[union-attr]


def test_list_item_must_start_with_paragraph() -> None:
    with pytest.raises(ValidationError, match="listItem content must start with a paragraph"):
        parse_content(
            {
                "type": "doc",
                "content": [
                    {
                        "type": "bulletList",
                        "content": [
                            {
                                "type": "listItem",
                                "content": [
                                    {
                                        "type": "image",
                                        "attrs": {
                                            "assetId": "11111111-1111-1111-1111-111111111111"
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        )


def test_list_item_starting_with_paragraph_is_accepted() -> None:
    parse_content(
        {
            "type": "doc",
            "content": [
                {
                    "type": "bulletList",
                    "content": [{"type": "listItem", "content": [{"type": "paragraph"}]}],
                }
            ],
        }
    )


@pytest.mark.parametrize("attrs", [{"lines": 0}, {"blankHeightMm": 0}])
def test_answer_space_dimensions_must_be_positive(attrs: object) -> None:
    with pytest.raises(ValidationError):
        parse_content({"type": "doc", "content": [{"type": "answerSpace", "attrs": attrs}]})


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


def test_doc_with_subquestions_cannot_carry_a_mark() -> None:
    payload = {
        "type": "doc",
        "marks": 4,
        "content": [
            {"type": "subQuestion", "attrs": {"label": "(a)"}, "content": [{"type": "paragraph"}]},
            {
                "type": "subQuestion",
                "attrs": {"label": "(b)", "marks": 2},
                "content": [{"type": "paragraph"}],
            },
        ],
    }
    with pytest.raises(ValidationError, match="cannot carry"):
        parse_content(payload)


def test_subquestion_with_nested_subquestions_cannot_carry_a_mark() -> None:
    payload = {
        "type": "doc",
        "content": [
            {
                "type": "subQuestion",
                "attrs": {"label": "(a)", "marks": 5},
                "content": [
                    {
                        "type": "subQuestion",
                        "attrs": {"label": "(i)"},
                        "content": [{"type": "paragraph"}],
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValidationError, match="cannot carry"):
        parse_content(payload)


def test_standalone_and_leaf_marks_are_accepted() -> None:
    parse_content({"type": "doc", "marks": 4, "content": [{"type": "paragraph"}]})
    parse_content(
        {
            "type": "doc",
            "content": [
                {
                    "type": "subQuestion",
                    "attrs": {"label": "(a)", "marks": 2},
                    "content": [{"type": "paragraph"}],
                }
            ],
        }
    )
