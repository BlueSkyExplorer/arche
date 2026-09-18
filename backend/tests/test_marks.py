from decimal import Decimal

from app.schemas.content import parse_content
from app.services.marks import computed_marks


def _doc(*blocks, marks=None):
    payload: dict = {"type": "doc", "content": list(blocks)}
    if marks is not None:
        payload["marks"] = marks
    return parse_content(payload)


def _sub(label, marks=None, *blocks):
    attrs: dict = {"label": label}
    if marks is not None:
        attrs["marks"] = marks
    body = list(blocks) if blocks else [{"type": "paragraph"}]
    return {"type": "subQuestion", "attrs": attrs, "content": body}


def test_standalone_question_carries_its_own_mark():
    doc = _doc(
        {"type": "paragraph", "content": [{"type": "text", "text": "stem"}]},
        marks="4",
    )
    assert computed_marks(doc) == Decimal("4")


def test_question_total_is_sum_of_subpart_leaf_marks():
    doc = _doc(_sub("(a)", 2), _sub("(b)", 3))
    assert computed_marks(doc) == Decimal("5")


def test_nested_subparts_aggregate_deepest_leaves_only():
    doc = _doc(_sub("(a)", None, _sub("(i)", 1), _sub("(ii)", 2)))
    assert computed_marks(doc) == Decimal("3")


def test_leaf_without_a_mark_counts_as_zero():
    doc = _doc(_sub("(a)", None))
    assert computed_marks(doc) == Decimal("0")


def test_empty_question_counts_as_zero():
    doc = _doc()
    assert computed_marks(doc) == Decimal("0")


def test_deeply_nested_leaf_marks_sum_correctly():
    doc = _doc(
        _sub("(a)", None, _sub("(i)", "1.5"), _sub("(ii)", "0.5")),
        _sub("(b)", "2"),
    )
    assert computed_marks(doc) == Decimal("4")