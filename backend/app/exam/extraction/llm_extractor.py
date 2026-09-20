"""LLM semantic extractor: DocumentBlock[] -> ExamDocument via schema-constrained LLM.

The LLM decides structure only; the deterministic assembler maps references back
onto the original blocks; the deterministic validator enforces every invariant.
On any provider failure or schema violation it falls back to the rule-based
extractor, so it can never leave the pipeline with nothing.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.exam.extraction.assembler import assemble
from app.exam.extraction.extractor import RuleBasedExamExtractor
from app.exam.extraction.interface import ExamExtractor
from app.exam.extraction.providers import StructuredLLMClient, StructuredLLMError
from app.exam.extraction.semantic import (
    SCHEMA_VERSION,
    SemanticExtractionResult,
    build_messages,
    strict_json_schema,
)
from app.exam.ir import ExamDocument
from app.exam.parsing.blocks import ParseResult


class LLMExamExtractor:
    name = "llm"

    def __init__(
        self,
        client: StructuredLLMClient,
        *,
        fallback: ExamExtractor | None = None,
    ) -> None:
        self.client = client
        self.fallback = fallback if fallback is not None else RuleBasedExamExtractor()

    def extract(self, parsed: ParseResult) -> ExamDocument:
        try:
            schema = strict_json_schema(SemanticExtractionResult)
            messages = build_messages(parsed)
            raw = self.client.complete_structured(schema=schema, messages=messages)
            dto = SemanticExtractionResult.model_validate(raw)
        except (StructuredLLMError, ValidationError) as exc:
            doc = self.fallback.extract(parsed)
            doc.meta["fallback_occurred"] = True
            doc.meta["fallback_reason"] = str(exc)[:200]
            doc.meta["fallback_from"] = self.name
            return doc

        warnings: list[dict[str, Any]] = []
        doc = assemble(dto, parsed, warnings)
        doc.meta.update(
            {
                "extractor": self.name,
                "provider": self.client.name,
                "model": self.client.model,
                "schema_version": SCHEMA_VERSION,
                "input_blocks": len(parsed.blocks),
                "output_nodes": len(dto.nodes),
                "fallback_occurred": False,
                "extraction_warnings": warnings,
            }
        )
        return doc
