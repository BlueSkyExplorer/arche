"""Real-provider structured-output integration smoke (opt-in, ticket 04.1).

Verifies the full contract against a *real* provider:
    DocumentBlock[] -> LLMExamExtractor (real AIClient) -> ExamDocument
    -> validate_exam_document()

It is NOT part of the normal unit suite: it runs only when BOTH (a) the
``integration`` marker is selected (``pytest -m integration``) and (b) a real
API key is configured (``AI_ENABLED=true`` + ``AI_API_KEY``). Without a key it
skips.

No chain-of-thought or provider reasoning is recorded.
"""

from __future__ import annotations

import time
from decimal import Decimal

import pytest

from app.core.config import Settings
from app.exam.extraction import LLMExamExtractor
from app.exam.ir import QuestionNode
from app.exam.parsing.blocks import BlockKind, DocumentBlock, ParseResult, SourceReference
from app.exam.validation import validate_exam_document
from app.services.ai_client import AIClient

pytestmark = pytest.mark.integration


def _text(text: str, idx: int) -> DocumentBlock:
    return DocumentBlock(
        id=f"b{idx:04d}", kind=BlockKind.TEXT, text=text, order=idx,
        source=SourceReference(file_name="smoke.docx"),
    )


@pytest.fixture(scope="module")
def ai_client() -> AIClient:
    settings = Settings()
    if not (settings.ai_enabled and settings.ai_api_key):
        pytest.skip("AI_ENABLED=true and AI_API_KEY are required for the real-provider smoke")
    return AIClient(settings)


def test_real_provider_structured_output_contract(ai_client: AIClient) -> None:
    blocks = [
        _text("1. State one function of the cell membrane. (1 mark)", 0),
        _text("(a) Define diffusion. (1 mark)", 1),
    ]
    parsed = ParseResult(blocks=blocks, source_name="smoke.docx", format="docx")
    known_ids = {b.id for b in blocks}

    extractor = LLMExamExtractor(ai_client)
    started = time.monotonic()
    doc = extractor.extract(parsed)
    elapsed = time.monotonic() - started

    # 1. no fallback: the real provider accepted the strict schema and decoded
    assert doc.meta.get("fallback_occurred") is False, doc.meta.get("fallback_reason")

    # 2. at least one question was produced
    questions = [q for s in doc.sections for q in s.questions]
    assert questions, "no questions extracted"

    # 3. every evidence block id maps back to a source block (no fabricated ids)
    for q in questions:
        _assert_block_ids_in(q, known_ids)

    # 4. marks came from the deterministic detector, not the LLM: the fixture's
    #    "(1 mark)" tokens must surface as own_marks=1 on their leaves
    leaves = _leaf_marks(questions)
    assert Decimal("1") in leaves, f"expected a leaf mark of 1, got {leaves}"

    # 5. validator runs on the result
    report = validate_exam_document(doc)
    print(
        f"\n[smoke] provider={ai_client.name} model={ai_client.model} "
        f"latency={elapsed:.2f}s questions={len(questions)} "
        f"computed_total={report.computed_total} needs_review={report.needs_review}"
    )


def _assert_block_ids_in(node: QuestionNode, known_ids: set[str]) -> None:
    for block in node.content:
        if block.source.block_id is not None:
            assert block.source.block_id in known_ids, (
                f"fabricated block id {block.source.block_id!r}"
            )
    for child in node.children:
        _assert_block_ids_in(child, known_ids)


def _leaf_marks(questions: list[QuestionNode]) -> list[Decimal]:
    marks: list[Decimal] = []

    def walk(node: QuestionNode) -> None:
        if not node.children and node.own_marks is not None:
            marks.append(node.own_marks)
        for child in node.children:
            walk(child)

    for q in questions:
        walk(q)
    return marks
