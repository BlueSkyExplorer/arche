from decimal import Decimal

from app.services.ai_schema import AIQuestion, AISubPart, ai_questions_to_drafts


def test_ai_questions_to_drafts_nested() -> None:
    sug = [
        AIQuestion(
            label="Q1.",
            marks=Decimal("3"),
            subparts=[
                AISubPart(label="(a)", text="花瓣細小", marks=Decimal("1")),
                AISubPart(
                    label="(b)", text="", marks=Decimal("2"),
                    children=[AISubPart(label="(i)", text="呈羽狀", marks=Decimal("1"))],
                ),
            ],
        )
    ]
    drafts = ai_questions_to_drafts(sug)
    assert len(drafts) == 1
    assert drafts[0].marks == Decimal("3")
    labels = [n.attrs.label for n in drafts[0].content_json.content if n.type == "subQuestion"]
    assert labels == ["(a)", "(b)"]
