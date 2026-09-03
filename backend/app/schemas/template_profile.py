from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat

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
        "1", "1.", "(1)", "arabic-dot", "lower-alpha", "upper-alpha", "roman"
    ] = "1."
    sub_question_style: Literal[
        "a", "a.", "(a)", "arabic-dot", "lower-alpha", "upper-alpha", "roman"
    ] = "(a)"


class BlockStyleConfig(StrictConfigModel):
    spacing_before_pt: float = Field(default=0, ge=0)
    spacing_after_pt: float = Field(default=0, ge=0)


class QuestionStyleConfig(BlockStyleConfig):
    marks_display: Literal["inline", "right", "below"] = "right"
    marks_format: str = "({marks} marks)"
    default_answer_lines: int = Field(default=0, ge=0)


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
    role_styles: dict[SemanticRole, RoleStyleConfig] = Field(default_factory=dict)


class TemplateProfileRead(TemplateProfileConfig):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    version: int
    school_name: str
    logo_asset_id: UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TemplateProfileCreate(TemplateProfileConfig):
    name: str = Field(min_length=1, max_length=255)
    school_name: str = Field(min_length=1, max_length=255)
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
    is_active: bool | None = None
