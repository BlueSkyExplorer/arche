"""Semantic extraction layer: DocumentBlock[] -> Exam IR (ExamDocument).

``RuleBasedExamExtractor`` is the deterministic baseline (ticket 03); the LLM
extractor (ticket 04) will implement the same ``ExamExtractor`` contract.
"""

from app.exam.extraction.extractor import (
    AMBIGUOUS_CONFIDENCE,
    RuleBasedExamExtractor,
)
from app.exam.extraction.interface import ExamExtractor
from app.exam.extraction.marks import MarkCandidate, detect_marks
from app.exam.extraction.numbering import (
    NumberingCandidate,
    NumberingPattern,
    detect_numbering,
)

__all__ = [
    "AMBIGUOUS_CONFIDENCE",
    "ExamExtractor",
    "MarkCandidate",
    "NumberingCandidate",
    "NumberingPattern",
    "RuleBasedExamExtractor",
    "detect_marks",
    "detect_numbering",
]
