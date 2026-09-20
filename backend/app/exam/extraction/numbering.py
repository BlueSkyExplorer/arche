"""Numbering candidate detection.

Detects *possible* question/sub-question labels at the start of a text block.
Detection only answers "what label/token does this look like" — it never decides
parent/child (that is the extractor's hierarchy reconciliation, and the parser's
numbers/values are 1-based ordinals decoded here).

Supported forms (see ADR-0001 for the pattern model): ``1.``, ``1)``, ``1、``,
``1`` (bare), ``Q1``, ``Q1.``, ``(a)``, ``a)``, ``A.``, ``(i)``, ``(ii)``,
``(1)``. CJK numeral systems are reserved but not rendered (ADR-0001).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Only the roman range actually used for sub-sub numbering in exams (i..x).
_ROMAN = {
    "i": 1,
    "ii": 2,
    "iii": 3,
    "iv": 4,
    "v": 5,
    "vi": 6,
    "vii": 7,
    "viii": 8,
    "ix": 9,
    "x": 10,
}


def _classify(content: str) -> tuple[str, int] | None:
    """Return ``(system, value)`` for a numbering token, or ``None`` if it is
    not a number. Roman is checked before alpha so ``i``/``v``/``x`` decode as
    roman (the exam convention), while ``a``..``z`` decode as alpha."""
    if content.isdigit():
        return ("arabic", int(content))
    roman = _ROMAN.get(content.lower())
    if roman is not None:
        return ("roman_lower" if content.islower() else "roman_upper", roman)
    if len(content) == 1 and content.isalpha():
        return (
            "alpha_lower" if content.islower() else "alpha_upper",
            ord(content.lower()) - 96,
        )
    return None


_PAREN = re.compile(r"^(\s*)\(\s*([A-Za-z0-9]+)\s*\)\s*([.)、．]?)")
_Q = re.compile(r"^(\s*)[Qq]\s*(\d+)\s*([.)、．]?)")
_SUFFIXED = re.compile(r"^(\s*)([A-Za-z0-9]+)\s*([.)、．])(?=\s|$)")
_BARE = re.compile(r"^(\s*)(\d{1,3})(?!\s*marks?\b|\s*分\b)(?=\s|$)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class NumberingCandidate:
    """A decoded numbering token with its source span."""

    system: str  # arabic / alpha_lower / alpha_upper / roman_lower / roman_upper
    value: int
    token: str  # normalized label, e.g. "3", "(b)", "(ii)", "Q1", "(1)"
    prefix: str
    suffix: str
    start: int  # span start in the source text
    end: int  # span end in the source text (stem begins here)


@dataclass(frozen=True, slots=True)
class NumberingPattern:
    """A numbering style observation (ADR-0001): system + affix."""

    system: str
    prefix: str
    suffix: str

    def as_dict(self) -> dict[str, str]:
        return {"system": self.system, "prefix": self.prefix, "suffix": self.suffix}


def detect_numbering(text: str) -> NumberingCandidate | None:
    if not text:
        return None
    m = _PAREN.match(text)
    if m:
        classified = _classify(m.group(2))
        if classified is not None:
            system, value = classified
            suffix = ")" + (m.group(3) or "")
            token = f"({m.group(2)}){m.group(3) or ''}"
            return NumberingCandidate(system, value, token, "(", suffix, m.start(), m.end())
    m = _Q.match(text)
    if m:
        suffix = m.group(3) or ""
        token = f"Q{m.group(2)}{suffix}"
        return NumberingCandidate("arabic", int(m.group(2)), token, "Q", suffix, m.start(), m.end())
    m = _SUFFIXED.match(text)
    if m:
        classified = _classify(m.group(2))
        if classified is not None:
            system, value = classified
            return NumberingCandidate(
                system, value, f"{m.group(2)}{m.group(3)}", "", m.group(3), m.start(), m.end()
            )
    m = _BARE.match(text)
    if m:
        return NumberingCandidate("arabic", int(m.group(2)), m.group(2), "", "", m.start(), m.end())
    return None
