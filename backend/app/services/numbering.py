"""Pure, persistence-independent paper numbering and mark calculations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal
from uuid import UUID

NumberingStyle = Literal["arabic-dot", "lower-alpha", "upper-alpha", "roman"]
QuestionStyle = Literal[
    "1", "1.", "(1)", "Q1", "Q1.", "arabic-dot", "lower-alpha", "upper-alpha", "roman"
]
SubQuestionStyle = Literal["a", "a.", "(a)", "arabic-dot", "lower-alpha", "upper-alpha", "roman"]


@dataclass(frozen=True, slots=True)
class NumberingConfig:
    question_style: QuestionStyle = "arabic-dot"
    sub_question_style: SubQuestionStyle = "lower-alpha"
    sub_sub_question_style: SubQuestionStyle = "roman"


@dataclass(frozen=True, slots=True)
class QuestionForNumbering:
    question_id: UUID | str
    position: int
    marks: Decimal
    marks_override: Decimal | None = None
    sub_question_count: int = 0


@dataclass(frozen=True, slots=True)
class SectionForNumbering:
    position: int
    questions: Sequence[QuestionForNumbering] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class NumberedQuestion:
    question: QuestionForNumbering
    ordinal: int
    label: str
    sub_question_labels: tuple[str, ...]

    @property
    def effective_marks(self) -> Decimal:
        override = self.question.marks_override
        return override if override is not None else self.question.marks


def _letters(value: int) -> str:
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(97 + remainder) + result
    return result


def _roman(value: int) -> str:
    numerals = (
        (1000, "m"),
        (900, "cm"),
        (500, "d"),
        (400, "cd"),
        (100, "c"),
        (90, "xc"),
        (50, "l"),
        (40, "xl"),
        (10, "x"),
        (9, "ix"),
        (5, "v"),
        (4, "iv"),
        (1, "i"),
    )
    result = ""
    for amount, symbol in numerals:
        count, value = divmod(value, amount)
        result += symbol * count
    return result


def format_number(value: int, style: NumberingStyle) -> str:
    if value < 1:
        raise ValueError("numbering values start at one")
    if style == "arabic-dot":
        return f"{value}."
    if style == "lower-alpha":
        return f"({_letters(value)})"
    if style == "upper-alpha":
        return f"({_letters(value).upper()})"
    return f"({_roman(value)})"


def format_question_label(value: int, style: QuestionStyle | SubQuestionStyle) -> str:
    """Format every template numbering enum without lossy style folding."""
    if style == "1":
        return str(value)
    if style == "Q1":
        return f"Q{value}"
    if style == "Q1.":
        return f"Q{value}."
    if style in {"1.", "arabic-dot"}:
        return format_number(value, "arabic-dot")
    if style == "(1)":
        return f"({value})"
    if style in {"a", "a.", "(a)"}:
        rendered = _letters(value)
        return {"a": rendered, "a.": f"{rendered}.", "(a)": f"({rendered})"}[style]
    if style == "lower-alpha":
        return format_number(value, "lower-alpha")
    if style == "upper-alpha":
        return format_number(value, "upper-alpha")
    return format_number(value, "roman")


def number_questions(
    sections: Sequence[SectionForNumbering],
    config: NumberingConfig | None = None,
) -> list[NumberedQuestion]:
    """Number questions continuously across position-ordered sections."""
    config = config or NumberingConfig()
    result: list[NumberedQuestion] = []
    ordinal = 0
    for section in sorted(sections, key=lambda item: item.position):
        for question in sorted(section.questions, key=lambda item: item.position):
            ordinal += 1
            sub_labels = tuple(
                format_question_label(index, config.sub_question_style)
                for index in range(1, question.sub_question_count + 1)
            )
            result.append(
                NumberedQuestion(
                    question=question,
                    ordinal=ordinal,
                    label=format_question_label(ordinal, config.question_style),
                    sub_question_labels=sub_labels,
                )
            )
    return result


def total_marks(questions: Sequence[QuestionForNumbering | NumberedQuestion]) -> Decimal:
    """Return effective marks, with each paper-question override taking precedence."""
    total = Decimal(0)
    for item in questions:
        question = item.question if isinstance(item, NumberedQuestion) else item
        total += question.marks_override if question.marks_override is not None else question.marks
    return total
