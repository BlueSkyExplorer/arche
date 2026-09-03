"""Isolated helpers for Word features not exposed by python-docx."""

from app.document.ooxml.package import normalize_zip_timestamps
from app.document.ooxml.word import (
    add_hyperlink,
    append_page_number,
    ensure_paragraph_style,
    set_paragraph_bottom_border,
    set_run_fonts,
    set_style_fonts,
    set_table_borders,
)

__all__ = [
    "add_hyperlink",
    "append_page_number",
    "ensure_paragraph_style",
    "normalize_zip_timestamps",
    "set_paragraph_bottom_border",
    "set_run_fonts",
    "set_style_fonts",
    "set_table_borders",
]
