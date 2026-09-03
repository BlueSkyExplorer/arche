from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat


class PageConfig(BaseModel):
    size: Literal["A4", "Letter"] = "A4"
    margin_top_mm: PositiveFloat
    margin_right_mm: PositiveFloat
    margin_bottom_mm: PositiveFloat
    margin_left_mm: PositiveFloat


class TypographyConfig(BaseModel):
    chinese_font: str = Field(min_length=1)
    latin_font: str = Field(min_length=1)
    base_font_size_pt: PositiveFloat
    line_spacing: PositiveFloat


class TextConfig(BaseModel):
    text: str = ""


class FooterConfig(TextConfig):
    page_numbering: bool = True


class NumberingConfig(BaseModel):
    question_style: Literal["1", "1.", "(1)"] = "1."
    sub_question_style: Literal["a", "a.", "(a)"] = "(a)"


class BlockStyleConfig(BaseModel):
    spacing_before_pt: float = Field(default=0, ge=0)
    spacing_after_pt: float = Field(default=0, ge=0)


class QuestionStyleConfig(BlockStyleConfig):
    marks_display: Literal["inline", "right", "below"] = "right"
    default_answer_lines: int = Field(default=0, ge=0)


class TemplateProfileConfig(BaseModel):
    page_config_json: PageConfig
    typography_config_json: TypographyConfig
    header_config_json: TextConfig
    footer_config_json: FooterConfig
    numbering_config_json: NumberingConfig
    section_style_config_json: BlockStyleConfig
    question_style_config_json: QuestionStyleConfig


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
