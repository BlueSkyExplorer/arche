from decimal import Decimal

from app.services.numbering import (
    NumberingConfig,
    QuestionForNumbering,
    SectionForNumbering,
    format_number,
    number_questions,
    total_marks,
)


def question(name: str, position: int, override: str | None = None) -> QuestionForNumbering:
    return QuestionForNumbering(
        question_id=name,
        position=position,
        marks=Decimal("2"),
        marks_override=Decimal(override) if override else None,
        sub_question_count=3,
    )


def test_renumbering_follows_section_and_question_positions() -> None:
    first = SectionForNumbering(2, [question("c", 1)])
    second = SectionForNumbering(1, [question("b", 2), question("a", 1)])
    assert [
        (item.question.question_id, item.label) for item in number_questions([first, second])
    ] == [("a", "1."), ("b", "2."), ("c", "3.")]
    assert [
        item.label for item in number_questions([SectionForNumbering(1, [question("c", 1)])])
    ] == ["1."]


def test_subpart_styles() -> None:
    assert format_number(27, "lower-alpha") == "(aa)"
    assert format_number(2, "upper-alpha") == "(B)"
    assert format_number(14, "roman") == "(xiv)"
    numbered = number_questions(
        [SectionForNumbering(1, [question("a", 1)])],
        NumberingConfig(sub_question_style="upper-alpha"),
    )
    assert numbered[0].sub_question_labels == ("(A)", "(B)", "(C)")


def test_total_marks_respects_override() -> None:
    questions = [question("a", 1), question("b", 2, "3.5")]
    assert total_marks(questions) == Decimal("5.5")
    assert total_marks(number_questions([SectionForNumbering(1, questions)])) == Decimal("5.5")
