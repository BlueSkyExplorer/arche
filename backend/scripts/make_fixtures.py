"""Build the synthetic school-format DOCX fixture used by template-import tests.

Run from the repo root (or anywhere):  python scripts/make_fixtures.py
Output: tests/fixtures/school_format.docx (and .doc)
"""
import subprocess
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "school_format.docx"


def set_east_asia_font(style, name: str) -> None:
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), name)


def add_page_field(paragraph) -> None:
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)


def build() -> None:
    doc = Document()
    section = doc.sections[0]
    section.page_width = Mm(210)  # A4
    section.page_height = Mm(297)
    section.top_margin = Mm(20)
    section.right_margin = Mm(20)
    section.bottom_margin = Mm(20)
    section.left_margin = Mm(20)

    normal = doc.styles["Normal"]
    normal.font.name = "Liberation Serif"  # latin font
    normal.font.size = Pt(12)
    set_east_asia_font(normal, "Noto Sans CJK")

    # Header / footer
    section.header.paragraphs[0].text = "ST. MARY'S COLLEGE"
    footer_para = section.footer.paragraphs[0]
    footer_para.text = "Page "
    add_page_field(footer_para)

    # Body: a section heading + one Q&A with an answer line
    doc.add_heading("Section A", level=1)
    doc.add_paragraph("1. Solve 2 + 2. (2 marks)")
    doc.add_paragraph("Answer: ____")
    doc.add_paragraph("2. 試計算 12 × 4。 （2分）")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")

    # Also produce a .doc fixture for the conversion tests
    doc_path = Path(str(OUT).replace(".docx", ".doc"))
    subprocess.run(
        [
            "/opt/data/libreoffice/bin/soffice-arche",
            "-env:UserInstallation=file:///tmp/arche-lo-profile",
            "--headless", "--convert-to", "doc", "--outdir", str(OUT.parent), str(OUT),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
    )
    print(f"wrote {doc_path} ({doc_path.stat().st_size} bytes)")


if __name__ == "__main__":
    build()