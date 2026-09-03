from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from app.document.renderer import PaperData, RenderQuestion, RenderSection, RenderTemplateProfile
from app.schemas.content import DocNode
from app.schemas.template_profile import TemplateProfileConfig

FIXTURES = Path(__file__).parents[1] / "fixtures"
IMAGE_ID = UUID("11111111-1111-1111-1111-111111111111")


def profile(variant: bool = False) -> RenderTemplateProfile:
    return RenderTemplateProfile(
        school_name="示例學校 Example School",
        config=TemplateProfileConfig.model_validate(
            {
                "page_config_json": {
                    "size": "A4",
                    "margin_top_mm": 25 if variant else 20,
                    "margin_right_mm": 22 if variant else 15,
                    "margin_bottom_mm": 25 if variant else 20,
                    "margin_left_mm": 22 if variant else 15,
                },
                "typography_config_json": {
                    "chinese_font": "PMingLiU" if variant else "Noto Sans CJK HK",
                    "latin_font": "Times New Roman" if variant else "Arial",
                    "base_font_size_pt": 11 if variant else 12,
                    "line_spacing": 1.25 if variant else 1.5,
                },
                "header_config_json": {"text": "Mock Examination"},
                "footer_config_json": {"text": "Confidential", "page_numbering": True},
                "numbering_config_json": {"question_style": "1.", "sub_question_style": "(a)"},
                "section_style_config_json": {"spacing_before_pt": 12, "spacing_after_pt": 6},
                "question_style_config_json": {
                    "spacing_before_pt": 6,
                    "spacing_after_pt": 6,
                    "marks_display": "right",
                    "marks_format": "({marks} marks)",
                    "default_answer_lines": 3,
                },
                "role_styles": {"PaperTitle": {"size_pt": 20 if variant else 18}},
            }
        ),
    )


def paper() -> PaperData:
    raw = json.loads((FIXTURES / "content.json").read_text())
    question = RenderQuestion(
        id=UUID("22222222-2222-2222-2222-222222222222"),
        position=1,
        content=DocNode.model_validate(raw),
        marks=Decimal("2"),
    )
    ten_mark_question = RenderQuestion(
        id=UUID("33333333-3333-3333-3333-333333333333"),
        position=2,
        content=DocNode.model_validate(
            {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Ten-mark question"}],
                    }
                ],
            }
        ),
        marks=Decimal("10"),
    )
    twenty_mark_question = RenderQuestion(
        id=UUID("44444444-4444-4444-4444-444444444444"),
        position=3,
        content=DocNode.model_validate(
            {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Twenty-mark question"}],
                    }
                ],
            }
        ),
        marks=Decimal("20"),
    )
    return PaperData(
        title="中英數學測驗 Bilingual Mathematics",
        subject="Mathematics",
        level="Form 2",
        instructions=("Answer all questions exactly as written.",),
        sections=(
            RenderSection(
                title="甲部 Section A",
                position=1,
                questions=(question, ten_mark_question, twenty_mark_question),
            ),
        ),
    )
