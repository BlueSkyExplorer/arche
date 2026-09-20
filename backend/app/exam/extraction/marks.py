"""Mark candidate detection (value + raw text + span). Attachment is separate.

Detects common mark formats: ``(3 marks)``, ``(3 mark)``, ``[3 marks]``, bare
``3 marks``, and the Chinese ``(3分)`` / ``3分``. Each candidate carries only
*what was stated and where*; deciding whether it is a leaf ``own_marks`` or a
non-leaf ``declared_subtotal`` is the extractor's attachment step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

_NUM = r"\d+(?:\.\d+)?"


@dataclass(frozen=True, slots=True)
class MarkCandidate:
    value: Decimal
    raw_text: str
    start: int
    end: int


_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\(\s*(" + _NUM + r")\s*marks?\s*\)", re.IGNORECASE),
    re.compile(r"\[\s*(" + _NUM + r")\s*marks?\s*\]", re.IGNORECASE),
    re.compile(r"(?<![\w.])(" + _NUM + r")\s*marks?\b", re.IGNORECASE),
    re.compile(r"[（(]\s*(" + _NUM + r")\s*分\s*[）)]"),
    re.compile(r"(?<![\w.])(" + _NUM + r")\s*分\b"),
)


def detect_marks(text: str) -> list[MarkCandidate]:
    """Return all mark candidates in ``text``, deduplicated by value span."""
    found: list[MarkCandidate] = []
    seen: set[tuple[int, int]] = set()
    for pattern in _PATTERNS:
        for m in pattern.finditer(text):
            span = (m.start(1), m.end(1))
            if span in seen:
                continue
            seen.add(span)
            found.append(MarkCandidate(Decimal(m.group(1)), m.group(0), m.start(), m.end()))
    found.sort(key=lambda c: c.start)
    return found
