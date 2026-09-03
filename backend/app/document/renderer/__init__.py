"""Deterministic DOCX renderer for canonical paper content.

Answer-space lines use empty paragraphs with a bottom border. ``blankHeightMm`` produces
one bordered paragraph with an exact requested height; ``lines`` produces that many
fixed-height (7 mm) rows. This avoids font-dependent underscore widths. Link ``rel`` and
``target`` attributes are accepted as editor metadata but intentionally do not affect
Word hyperlinks. Inline marks follow the final body paragraph, except after a table or
answer-space block, where a dedicated right-aligned ``QuestionMarks`` paragraph is used.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal
from io import BytesIO
from uuid import UUID

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.shared import Mm, Pt
from docx.table import _Cell
from docx.text.paragraph import Paragraph
from docx.text.run import Run
from pydantic import BaseModel, ConfigDict, Field

from app.document.ooxml import (
    add_hyperlink,
    append_page_number,
    ensure_paragraph_style,
    normalize_zip_timestamps,
    set_paragraph_bottom_border,
    set_run_fonts,
    set_style_fonts,
    set_table_borders,
)
from app.schemas.content import (
    AnswerSpaceNode,
    BlockNode,
    BulletListNode,
    DocNode,
    HeadingNode,
    ImageNode,
    InlineNode,
    LinkMark,
    OrderedListNode,
    ParagraphNode,
    SubQuestionNode,
    TableNode,
    TextNode,
)
from app.schemas.template_profile import RoleStyleConfig, SemanticRole, TemplateProfileConfig
from app.services.numbering import format_question_label


class RenderModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RenderQuestion(RenderModel):
    id: UUID
    position: int
    content: DocNode
    marks: Decimal = Field(ge=0)
    marks_override: Decimal | None = Field(default=None, ge=0)

    @property
    def effective_marks(self) -> Decimal:
        return self.marks_override if self.marks_override is not None else self.marks


class RenderSection(RenderModel):
    title: str
    position: int
    instructions: tuple[str, ...] = ()
    questions: tuple[RenderQuestion, ...] = ()


class PaperData(RenderModel):
    title: str
    subject: str = ""
    level: str = ""
    paper_date: date | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    instructions: tuple[str, ...] = ()
    sections: tuple[RenderSection, ...] = ()


class RenderTemplateProfile(RenderModel):
    school_name: str = ""
    logo_asset_id: UUID | None = None
    config: TemplateProfileConfig


AssetResolver = Callable[[UUID], bytes]
AssetSource = AssetResolver | Mapping[UUID, bytes]

_ALIGNMENTS = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}
_ROLE_DEFAULTS: dict[SemanticRole, RoleStyleConfig] = {
    "Normal": RoleStyleConfig(),
    "PaperTitle": RoleStyleConfig(size_pt=18, bold=True, alignment="center", spacing_after_pt=8),
    "PaperMetadata": RoleStyleConfig(alignment="center", spacing_after_pt=4),
    "SectionHeading": RoleStyleConfig(
        size_pt=14, bold=True, spacing_before_pt=12, spacing_after_pt=6
    ),
    "QuestionBody": RoleStyleConfig(spacing_before_pt=6, spacing_after_pt=3),
    "QuestionSubpart": RoleStyleConfig(indentation_mm=8, spacing_after_pt=3),
    "QuestionMarks": RoleStyleConfig(alignment="right", spacing_after_pt=6),
    "AnswerSpace": RoleStyleConfig(spacing_after_pt=0),
}


def _resolve(source: AssetSource, asset_id: UUID) -> bytes:
    return source(asset_id) if callable(source) else source[asset_id]


def _configure_styles(document: DocumentObject, config: TemplateProfileConfig) -> None:
    typography = config.typography_config_json
    for role, defaults in _ROLE_DEFAULTS.items():
        if role == "SectionHeading":
            block = config.section_style_config_json
            defaults = defaults.model_copy(
                update={
                    "spacing_before_pt": block.spacing_before_pt,
                    "spacing_after_pt": block.spacing_after_pt,
                }
            )
        elif role == "QuestionBody":
            block = config.question_style_config_json
            defaults = defaults.model_copy(
                update={
                    "spacing_before_pt": block.spacing_before_pt,
                    "spacing_after_pt": block.spacing_after_pt,
                }
            )
        override = config.role_styles.get(role)
        values = override.model_dump(exclude_none=True) if override else {}
        selected = defaults.model_copy(update=values)
        style = ensure_paragraph_style(document, role)
        set_style_fonts(
            style,
            selected.latin_font or typography.latin_font,
            selected.east_asia_font or typography.chinese_font,
        )
        style.font.size = Pt(selected.size_pt or typography.base_font_size_pt)
        if selected.bold is not None:
            style.font.bold = selected.bold
        paragraph_format = style.paragraph_format
        paragraph_format.line_spacing = typography.line_spacing
        if selected.alignment is not None:
            paragraph_format.alignment = _ALIGNMENTS[selected.alignment]
        if selected.spacing_before_pt is not None:
            paragraph_format.space_before = Pt(selected.spacing_before_pt)
        if selected.spacing_after_pt is not None:
            paragraph_format.space_after = Pt(selected.spacing_after_pt)
        if selected.indentation_mm is not None:
            paragraph_format.left_indent = Mm(selected.indentation_mm)


def _style_run(run: Run, config: TemplateProfileConfig) -> None:
    typography = config.typography_config_json
    set_run_fonts(run, typography.latin_font, typography.chinese_font)


def _add_inline(
    paragraph: Paragraph,
    node: InlineNode,
    config: TemplateProfileConfig,
    assets: AssetSource,
    width_mm: float,
) -> None:
    if isinstance(node, ImageNode):
        image_width = min(node.attrs.width_mm or width_mm, width_mm)
        paragraph.add_run().add_picture(
            BytesIO(_resolve(assets, node.attrs.asset_id)), width=Mm(image_width)
        )
        return
    if node.type == "hardBreak":
        paragraph.add_run().add_break()
        return
    assert isinstance(node, TextNode)
    link = next((mark for mark in node.marks if isinstance(mark, LinkMark)), None)
    run = add_hyperlink(paragraph, link.attrs.href) if link else paragraph.add_run()
    run.text = node.text
    _style_run(run, config)
    mark_types = {mark.type for mark in node.marks}
    run.bold = "bold" in mark_types
    run.italic = "italic" in mark_types
    run.underline = "underline" in mark_types or link is not None
    run.font.subscript = "subscript" in mark_types
    run.font.superscript = "superscript" in mark_types


def _fill_paragraph(
    paragraph: Paragraph,
    node: ParagraphNode | HeadingNode,
    config: TemplateProfileConfig,
    assets: AssetSource,
    width_mm: float,
) -> None:
    for inline in node.content:
        _add_inline(paragraph, inline, config, assets, width_mm)


def _new_paragraph(container: DocumentObject | _Cell, style: str) -> Paragraph:
    return container.add_paragraph(style=style)


def _render_list(
    container: DocumentObject | _Cell,
    node: BulletListNode | OrderedListNode,
    config: TemplateProfileConfig,
    assets: AssetSource,
    width_mm: float,
    sub_question_index: list[int] | None = None,
    sub_question_style: str = "(a)",
) -> None:
    start = node.attrs.start if isinstance(node, OrderedListNode) else 1
    for offset, item in enumerate(node.content):
        prefix = "• " if isinstance(node, BulletListNode) else f"{start + offset}. "
        first = True
        for block in item.content:
            if first and isinstance(block, ParagraphNode):
                paragraph = _new_paragraph(container, "QuestionBody")
                paragraph.paragraph_format.left_indent = Mm(8)
                paragraph.add_run(prefix)
                _fill_paragraph(paragraph, block, config, assets, width_mm - 8)
            else:
                _render_block(
                    container,
                    block,
                    config,
                    assets,
                    width_mm - 8,
                    sub_question_index,
                    sub_question_style,
                )
            first = False


def _render_table(
    container: DocumentObject | _Cell,
    node: TableNode,
    config: TemplateProfileConfig,
    assets: AssetSource,
    width_mm: float,
    sub_question_index: list[int] | None = None,
    sub_question_style: str = "(a)",
) -> None:
    table = container.add_table(rows=len(node.content), cols=len(node.content[0].content))
    table.autofit = False
    set_table_borders(table)
    for row_index, row_node in enumerate(node.content):
        for column_index, cell_node in enumerate(row_node.content):
            cell = table.cell(row_index, column_index)
            for index, block in enumerate(cell_node.content):
                if index == 0 and isinstance(block, ParagraphNode):
                    paragraph = cell.paragraphs[0]
                    paragraph.style = "QuestionBody"
                    _fill_paragraph(
                        paragraph, block, config, assets, width_mm / len(row_node.content)
                    )
                else:
                    _render_block(
                        cell,
                        block,
                        config,
                        assets,
                        width_mm / len(row_node.content),
                        sub_question_index,
                        sub_question_style,
                    )


def _render_block(
    container: DocumentObject | _Cell,
    node: BlockNode,
    config: TemplateProfileConfig,
    assets: AssetSource,
    width_mm: float,
    sub_question_index: list[int] | None = None,
    sub_question_style: str = "(a)",
) -> None:
    if isinstance(node, ParagraphNode):
        _fill_paragraph(_new_paragraph(container, "QuestionBody"), node, config, assets, width_mm)
    elif isinstance(node, HeadingNode):
        _fill_paragraph(_new_paragraph(container, "SectionHeading"), node, config, assets, width_mm)
    elif isinstance(node, (BulletListNode, OrderedListNode)):
        _render_list(
            container,
            node,
            config,
            assets,
            width_mm,
            sub_question_index,
            sub_question_style,
        )
    elif isinstance(node, TableNode):
        _render_table(
            container,
            node,
            config,
            assets,
            width_mm,
            sub_question_index,
            sub_question_style,
        )
    elif isinstance(node, ImageNode):
        _add_inline(_new_paragraph(container, "QuestionBody"), node, config, assets, width_mm)
    elif isinstance(node, SubQuestionNode):
        if sub_question_index is None:
            sub_question_index = [0]
        sub_question_index[0] += 1
        label = node.attrs.label or format_question_label(
            sub_question_index[0],
            sub_question_style,  # type: ignore[arg-type]
        )
        paragraph = _new_paragraph(container, "QuestionSubpart")
        paragraph.add_run(f"{label} ")
        for index, child in enumerate(node.content):
            if index == 0 and isinstance(child, ParagraphNode):
                _fill_paragraph(paragraph, child, config, assets, width_mm - 8)
            else:
                _render_block(
                    container,
                    child,
                    config,
                    assets,
                    width_mm - 8,
                    sub_question_index,
                    sub_question_style,
                )
    elif isinstance(node, AnswerSpaceNode):
        heights = (
            [7.0] * node.attrs.lines
            if node.attrs.lines is not None
            else [node.attrs.blank_height_mm or 0.0]
        )
        for height in heights:
            paragraph = _new_paragraph(container, "AnswerSpace")
            paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
            paragraph.paragraph_format.line_spacing = Mm(height)
            set_paragraph_bottom_border(paragraph)


def _contains_answer_space(value: object) -> bool:
    if isinstance(value, AnswerSpaceNode):
        return True
    if isinstance(value, BaseModel):
        return any(_contains_answer_space(item) for item in value.__dict__.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_answer_space(item) for item in value)
    return False


def _format_marks(value: Decimal, pattern: str) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return pattern.format(marks=rendered)


def render_paper(
    paper_data: PaperData,
    template_profile: RenderTemplateProfile,
    questions_with_assets: AssetSource,
) -> bytes:
    """Render validated, ORM-free input into DOCX bytes without external I/O."""
    document = Document()
    config = template_profile.config
    _configure_styles(document, config)
    section = document.sections[0]
    page = config.page_config_json
    if page.size == "A4":
        section.page_width, section.page_height = Mm(210), Mm(297)
        page_width = 210.0
    else:
        section.page_width, section.page_height = Mm(215.9), Mm(279.4)
        page_width = 215.9
    section.top_margin, section.right_margin = Mm(page.margin_top_mm), Mm(page.margin_right_mm)
    section.bottom_margin, section.left_margin = Mm(page.margin_bottom_mm), Mm(page.margin_left_mm)
    available_width = page_width - page.margin_left_mm - page.margin_right_mm
    header = section.header.paragraphs[0]
    header.style = "PaperMetadata"
    if template_profile.logo_asset_id is not None:
        header.add_run().add_picture(
            BytesIO(_resolve(questions_with_assets, template_profile.logo_asset_id)), width=Mm(20)
        )
    header.add_run(template_profile.school_name)
    if config.header_config_json.text:
        header.add_run(f"  {config.header_config_json.text}")
    footer = section.footer.paragraphs[0]
    footer.style = "PaperMetadata"
    footer.add_run(config.footer_config_json.text)
    if config.footer_config_json.page_numbering:
        if config.footer_config_json.text:
            footer.add_run("  ")
        append_page_number(footer)
    document.add_paragraph(paper_data.title, style="PaperTitle")
    metadata = " · ".join(value for value in (paper_data.subject, paper_data.level) if value)
    if paper_data.paper_date:
        metadata = " · ".join(
            value for value in (metadata, paper_data.paper_date.isoformat()) if value
        )
    if paper_data.duration_minutes is not None:
        metadata = " · ".join(
            value for value in (metadata, f"{paper_data.duration_minutes} minutes") if value
        )
    if metadata:
        document.add_paragraph(metadata, style="PaperMetadata")
    for instruction in paper_data.instructions:
        document.add_paragraph(instruction, style="QuestionBody")
    ordinal = 0
    for section_data in sorted(paper_data.sections, key=lambda value: value.position):
        document.add_paragraph(section_data.title, style="SectionHeading")
        for instruction in section_data.instructions:
            document.add_paragraph(instruction, style="QuestionBody")
        for question in sorted(section_data.questions, key=lambda value: value.position):
            ordinal += 1
            label = format_question_label(ordinal, config.numbering_config_json.question_style)
            blocks = list(question.content.content)
            if blocks and isinstance(blocks[0], ParagraphNode):
                first_block = blocks.pop(0)
                assert isinstance(first_block, ParagraphNode)
                paragraph = document.add_paragraph(style="QuestionBody")
                paragraph.add_run(f"{label} ")
                _fill_paragraph(
                    paragraph, first_block, config, questions_with_assets, available_width
                )
            else:
                document.add_paragraph(label, style="QuestionBody")
            sub_question_index = [0]
            for block in blocks:
                _render_block(
                    document,
                    block,
                    config,
                    questions_with_assets,
                    available_width,
                    sub_question_index,
                    config.numbering_config_json.sub_question_style,
                )
            if (
                config.question_style_config_json.default_answer_lines > 0
                and not _contains_answer_space(question.content)
            ):
                default_space = AnswerSpaceNode.model_validate(
                    {
                        "type": "answerSpace",
                        "attrs": {"lines": config.question_style_config_json.default_answer_lines},
                    }
                )
                _render_block(
                    document, default_space, config, questions_with_assets, available_width
                )
                blocks.append(default_space)
            marks = _format_marks(
                question.effective_marks, config.question_style_config_json.marks_format
            )
            display = config.question_style_config_json.marks_display
            final_is_separate_block = bool(blocks) and isinstance(
                blocks[-1], (TableNode, AnswerSpaceNode)
            )
            if display == "inline" and document.paragraphs and not final_is_separate_block:
                document.paragraphs[-1].add_run(f" {marks}")
            else:
                paragraph = document.add_paragraph(marks, style="QuestionMarks")
                if display == "below":
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    output = BytesIO()
    document.save(output)
    return normalize_zip_timestamps(output.getvalue())


__all__ = [
    "AssetResolver",
    "AssetSource",
    "PaperData",
    "RenderQuestion",
    "RenderSection",
    "RenderTemplateProfile",
    "render_paper",
]
