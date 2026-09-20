"""Semantic extraction layer: DocumentBlock[] -> Exam IR (ExamDocument).

``RuleBasedExamExtractor`` is the deterministic baseline (ticket 03);
``LLMExamExtractor`` is the schema-constrained LLM extractor (ticket 04). Both
implement the same ``ExamExtractor`` contract, so downstream validation and
materialization never change.
"""

from app.exam.extraction.assembler import assemble
from app.exam.extraction.extractor import RuleBasedExamExtractor
from app.exam.extraction.interface import ExamExtractor
from app.exam.extraction.llm_extractor import LLMExamExtractor
from app.exam.extraction.marks import MarkCandidate, detect_marks
from app.exam.extraction.numbering import (
    NumberingCandidate,
    NumberingPattern,
    detect_numbering,
)
from app.exam.extraction.providers import (
    FakeStructuredClient,
    StructuredLLMClient,
    StructuredLLMError,
)
from app.exam.extraction.semantic import (
    SCHEMA_VERSION,
    SemanticExtractionResult,
    SemanticNodeDTO,
    SemanticSectionDTO,
    build_messages,
    strict_json_schema,
)

__all__ = [
    "ExamExtractor",
    "FakeStructuredClient",
    "LLMExamExtractor",
    "MarkCandidate",
    "NumberingCandidate",
    "NumberingPattern",
    "RuleBasedExamExtractor",
    "SCHEMA_VERSION",
    "SemanticExtractionResult",
    "SemanticNodeDTO",
    "SemanticSectionDTO",
    "StructuredLLMClient",
    "StructuredLLMError",
    "assemble",
    "build_messages",
    "detect_marks",
    "detect_numbering",
    "strict_json_schema",
]
