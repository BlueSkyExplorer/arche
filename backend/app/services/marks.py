"""Pure leaf-mark aggregation over structured question content.

Only a leaf node carries an authoritative mark; a node with children is always
the sum of its descendant leaf marks (see ADR-0002). The content schema already
rejects a non-leaf node that also holds a mark, so aggregation never needs to
decide between a parent mark and its descendants.
"""

from decimal import Decimal

from app.schemas.content import BlockNode, DocNode, SubQuestionNode


def _leaf_total(marks: Decimal | None, content: list[BlockNode]) -> Decimal:
    subs = [block for block in content if isinstance(block, SubQuestionNode)]
    if subs:
        return sum(
            (_leaf_total(sub.attrs.marks, sub.content) for sub in subs), Decimal("0")
        )
    return marks if marks is not None else Decimal("0")


def computed_marks(doc: DocNode) -> Decimal:
    """Return the computed score of a question: the sum of its leaf marks."""
    return _leaf_total(doc.marks, doc.content)