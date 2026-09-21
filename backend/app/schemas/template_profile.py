from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, field_validator

SemanticRole = Literal[
    "Normal",
    "PaperTitle",
    "PaperMetadata",
    "SectionHeading",
    "QuestionBody",
    "QuestionSubpart",
    "QuestionMarks",
    "AnswerSpace",
]


class StrictConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PageConfig(StrictConfigModel):
    size: Literal["A4", "Letter"] = "A4"
    margin_top_mm: PositiveFloat
    margin_right_mm: PositiveFloat
    margin_bottom_mm: PositiveFloat
    margin_left_mm: PositiveFloat


class TypographyConfig(StrictConfigModel):
    chinese_font: str = Field(min_length=1)
    latin_font: str = Field(min_length=1)
    base_font_size_pt: PositiveFloat
    line_spacing: PositiveFloat


class TextConfig(StrictConfigModel):
    text: str = ""


class FooterConfig(TextConfig):
    page_numbering: bool = True


class NumberingConfig(StrictConfigModel):
    question_style: Literal[
        "1", "1.", "(1)", "Q1", "Q1.", "arabic-dot", "lower-alpha", "upper-alpha", "roman"
    ] = "1."
    sub_question_style: Literal[
        "a", "a.", "(a)", "arabic-dot", "lower-alpha", "upper-alpha", "roman"
    ] = "(a)"
    sub_sub_question_style: Literal[
        "a", "a.", "(a)", "arabic-dot", "lower-alpha", "upper-alpha", "roman"
    ] = "roman"


class BlockStyleConfig(StrictConfigModel):
    spacing_before_pt: float = Field(default=0, ge=0)
    spacing_after_pt: float = Field(default=0, ge=0)


class QuestionStyleConfig(BlockStyleConfig):
    marks_display: Literal["inline", "right", "below"] = "right"
    marks_format: str = "({marks} marks)"
    default_answer_lines: int = Field(default=0, ge=0)


_METADATA_PLACEHOLDERS = {
    "school_name",
    "academic_year",
    "exam_name",
    "level",
    "subject",
    "document_type",
}


class AnswerSheetLayoutConfig(StrictConfigModel):
    metadata_lines: list[str] = Field(
        default_factory=lambda: [
            "{{school_name}}",
            "{{academic_year}} {{exam_name}}",
            "{{level}} {{subject}} ({{document_type}})",
        ],
        min_length=1,
        max_length=8,
    )
    mcq_columns: Literal[1, 2, 3] = 2
    mcq_borders: bool = True
    mcq_question_width_mm: float = Field(default=14, gt=0, le=40)
    mcq_answer_width_mm: float = Field(default=18, gt=0, le=50)
    mcq_alignment: Literal["left", "center", "right"] = "center"
    mcq_font_size_pt: float = Field(default=11, ge=6, le=24)
    mcq_row_height_mm: float = Field(default=7, ge=3, le=20)
    hierarchy_indent_mm: float = Field(default=7, ge=0, le=25)
    show_parent_totals: bool = True
    image_max_width_mm: float = Field(default=120, gt=0, le=180)
    answer_table_borders: bool = True
    answer_table_alignment: Literal["left", "center", "right"] = "left"
    answer_table_font_size_pt: float = Field(default=10, ge=6, le=24)
    repeat_table_header: bool = True

    @field_validator("metadata_lines")
    @classmethod
    def validate_placeholders(cls, lines: list[str]) -> list[str]:
        import re

        for line in lines:
            names = set(re.findall(r"{{\s*([a-z_]+)\s*}}", line))
            unsupported = names - _METADATA_PLACEHOLDERS
            if unsupported:
                raise ValueError(f"unsupported metadata placeholder(s): {sorted(unsupported)}")
        return lines


class RoleStyleConfig(StrictConfigModel):
    latin_font: str | None = Field(default=None, min_length=1)
    east_asia_font: str | None = Field(default=None, min_length=1)
    size_pt: PositiveFloat | None = None
    bold: bool | None = None
    alignment: Literal["left", "center", "right", "justify"] | None = None
    spacing_before_pt: float | None = Field(default=None, ge=0)
    spacing_after_pt: float | None = Field(default=None, ge=0)
    indentation_mm: float | None = Field(default=None, ge=0)


class TemplateProfileConfig(StrictConfigModel):
    page_config_json: PageConfig
    typography_config_json: TypographyConfig
    header_config_json: TextConfig
    footer_config_json: FooterConfig
    numbering_config_json: NumberingConfig
    section_style_config_json: BlockStyleConfig
    question_style_config_json: QuestionStyleConfig
    answer_sheet_layout_json: AnswerSheetLayoutConfig = Field(
        default_factory=AnswerSheetLayoutConfig
    )
    role_styles: dict[SemanticRole, RoleStyleConfig] = Field(default_factory=dict)


class TemplateProfileRead(TemplateProfileConfig):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    version: int
    school_name: str
    logo_asset_id: UUID | None
    source_docx_sha256: str | None = None
    ooxml_layout_blueprint_json: dict[str, object] = Field(default_factory=dict)
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TemplateProfileCreate(TemplateProfileConfig):
    name: str = Field(min_length=1, max_length=255)
    school_name: str = Field(min_length=1, max_length=255)
    logo_asset_id: UUID | None = None
    # Set only by the format-import flow. Raw OOXML is persisted in private
    # storage; JSON keeps only a content-free blueprint plus SHA-256.
    source_docx_base64: str | None = None
    ooxml_layout_blueprint_json: dict[str, object] = Field(default_factory=dict)
    is_active: bool = True


class TemplateProfileImportDraft(TemplateProfileConfig):
    """Unsaved import proposal; identity evidence may legitimately be absent.

    Persisted ``TemplateProfileCreate`` remains strict.  Keeping this boundary
    separate prevents low-confidence body text or a made-up placeholder from
    masquerading as detected school metadata in the review form.
    """

    name: str = Field(min_length=1, max_length=255)
    school_name: str = Field(default="", max_length=255)
    logo_asset_id: UUID | None = None
    is_active: bool = True


class TemplateProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    school_name: str | None = Field(default=None, min_length=1, max_length=255)
    logo_asset_id: UUID | None = None
    page_config_json: PageConfig | None = None
    typography_config_json: TypographyConfig | None = None
    header_config_json: TextConfig | None = None
    footer_config_json: FooterConfig | None = None
    numbering_config_json: NumberingConfig | None = None
    section_style_config_json: BlockStyleConfig | None = None
    question_style_config_json: QuestionStyleConfig | None = None
    answer_sheet_layout_json: AnswerSheetLayoutConfig | None = None
    is_active: bool | None = None
