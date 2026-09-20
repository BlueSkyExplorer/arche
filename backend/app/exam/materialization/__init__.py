"""Materialization layer: validated ExamDocument -> existing ingest DTOs."""

from app.exam.materialization.materializer import materialize_exam_document

__all__ = ["materialize_exam_document"]
