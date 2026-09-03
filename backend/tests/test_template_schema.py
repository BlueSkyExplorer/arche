import pytest
from pydantic import ValidationError

from app.schemas.template_profile import TemplateProfileConfig


def valid_config() -> dict[str, object]:
    return {
        "page_config_json": {
            "size": "A4",
            "margin_top_mm": 20,
            "margin_right_mm": 15,
            "margin_bottom_mm": 20,
            "margin_left_mm": 15,
        },
        "typography_config_json": {
            "chinese_font": "Noto Sans CJK HK",
            "latin_font": "Arial",
            "base_font_size_pt": 12,
            "line_spacing": 1.5,
        },
        "header_config_json": {"text": "Example School"},
        "footer_config_json": {"text": "", "page_numbering": True},
        "numbering_config_json": {"question_style": "1.", "sub_question_style": "(a)"},
        "section_style_config_json": {"spacing_before_pt": 12, "spacing_after_pt": 6},
        "question_style_config_json": {
            "spacing_before_pt": 6,
            "spacing_after_pt": 6,
            "marks_display": "right",
            "default_answer_lines": 3,
        },
    }


def test_template_profile_config_validates_nested_json() -> None:
    config = TemplateProfileConfig.model_validate(valid_config())
    assert config.page_config_json.size == "A4"
    assert config.typography_config_json.chinese_font == "Noto Sans CJK HK"


def test_template_profile_config_rejects_invalid_margin() -> None:
    payload = valid_config()
    page = payload["page_config_json"]
    assert isinstance(page, dict)
    page["margin_top_mm"] = -1
    with pytest.raises(ValidationError):
        TemplateProfileConfig.model_validate(payload)
