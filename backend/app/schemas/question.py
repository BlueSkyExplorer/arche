from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.schemas.content import DocNode
from app.services.marks import computed_marks

QuestionContent = DocNode


class QuestionCreate(BaseModel):
    internal_title: str = Field(min_length=1, max_length=255)
    subject: str = Field(min_length=1, max_length=100)
    level: str = Field(min_length=1, max_length=100)
    tags_json: list[str] = Field(default_factory=list)
    source_note: str | None = None
    content_json: DocNode
    status: str = Field(default="draft", pattern="^(draft|ready|archived)$")


class QuestionPatch(BaseModel):
    internal_title: str | None = Field(default=None, min_length=1, max_length=255)
    subject: str | None = Field(default=None, min_length=1, max_length=100)
    level: str | None = Field(default=None, min_length=1, max_length=100)
    tags_json: list[str] | None = None
    source_note: str | None = None
    content_json: DocNode | None = None
    status: str | None = Field(default=None, pattern="^(draft|ready|archived)$")


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    internal_title: str
    subject: str
    level: str
    tags_json: list[str]
    source_note: str | None
    content_json: DocNode
    status: str
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def marks(self) -> Decimal:
        """Computed from leaf marks in the content tree (single source of truth)."""
        return computed_marks(self.content_json)


class DeclaredMark(BaseModel):
    """A mark stated in source material, preserved as evidence (never scoring truth)."""

    value: Decimal = Field(ge=0)
    raw_text: str = ""
    location: str = ""


class QuestionIngestDraft(BaseModel):
    """A parsed-but-unsaved question, returned by POST /questions/ingest.

    Teachers review drafts before saving them via the normal POST /questions.
    ``marks`` is the authoritative value, left ``None`` when the parser could
    not detect any mark (never fabricated as zero); ``declared_marks`` holds
    the evidence the source actually stated, and ``needs_review`` is set when
    the parse was unreliable.
    """
    internal_title: str = Field(min_length=1, max_length=255)
    subject: str = Field(default="", max_length=100)
    level: str = Field(default="", max_length=100)
    tags_json: list[str] = Field(default_factory=list)
    source_note: str | None = None
    content_json: DocNode
    marks: Decimal | None = Field(default=None, ge=0)
    declared_marks: list[DeclaredMark] = Field(default_factory=list)
    needs_review: bool = False
    validation_issues: list[str] = Field(default_factory=list)
    status: str = Field(default="draft", pattern="^(draft|ready|archived)$")
