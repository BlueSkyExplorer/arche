"""Extractor interface: ParseResult -> ExamDocument.

Both the deterministic baseline (``RuleBasedExamExtractor``, ticket 03) and the
LLM extractor (ticket 04) implement this same contract, so downstream validation
and materialization never change.
"""

from __future__ import annotations

from typing import Protocol

from app.exam.ir import ExamDocument
from app.exam.parsing.blocks import ParseResult


class ExamExtractor(Protocol):
    name: str

    def extract(self, parsed: ParseResult) -> ExamDocument: ...
