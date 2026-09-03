import logging
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.config import Settings
from app.core.storage import StorageBackend
from app.document.renderer import (
    PaperData,
    RenderQuestion,
    RenderSection,
    RenderTemplateProfile,
    render_paper,
)
from app.models import Asset, Export, TemplateProfile
from app.schemas.content import DocNode
from app.schemas.template_profile import TemplateProfileConfig
from app.services.authorization import assert_workspace_access
from app.services.papers import get_paper, paper_tree

logger = logging.getLogger(__name__)


def get_export(db: Session, export_id: UUID, user: CurrentUser) -> Export:
    item = db.get(Export, export_id)
    if item is None:
        raise HTTPException(404, "Export not found")
    assert_workspace_access(item.workspace_id, user.workspace_id)
    return item


def _texts(items: list[dict[str, object]]) -> tuple[str, ...]:
    return tuple(str(item.get("text", "")) for item in items if item.get("text"))


def _render(
    db: Session, paper_id: UUID, user: CurrentUser, storage: StorageBackend
) -> tuple[bytes, int]:
    paper = get_paper(db, paper_id, user)
    template = db.get(TemplateProfile, paper.template_profile_id)
    if template is None or template.workspace_id != user.workspace_id:
        raise HTTPException(404, "Template not found")
    tree, _ = paper_tree(db, paper)
    sections = tuple(
        RenderSection(
            title=section.title,
            position=section.position,
            instructions=_texts(section.instructions_json),
            questions=tuple(
                RenderQuestion(
                    id=question.id,
                    position=pq.position,
                    content=DocNode.model_validate(question.content_json),
                    marks=question.marks,
                    marks_override=pq.marks_override,
                )
                for pq, question in pairs
            ),
        )
        for section, pairs in tree
    )
    config = TemplateProfileConfig.model_validate(
        {
            "page_config_json": template.page_config_json,
            "typography_config_json": template.typography_config_json,
            "header_config_json": template.header_config_json,
            "footer_config_json": template.footer_config_json,
            "numbering_config_json": template.numbering_config_json,
            "section_style_config_json": template.section_style_config_json,
            "question_style_config_json": template.question_style_config_json,
            "role_styles": template.role_styles,
        }
    )
    profile = RenderTemplateProfile(
        school_name=template.school_name, logo_asset_id=template.logo_asset_id, config=config
    )

    def resolve(asset_id: UUID) -> bytes:
        asset = db.get(Asset, asset_id)
        if asset is None or asset.workspace_id != user.workspace_id:
            raise ValueError("Referenced asset unavailable")
        return storage.get(asset.storage_key)

    data = PaperData(
        title=paper.title,
        subject=paper.subject,
        level=paper.level,
        paper_date=paper.paper_date,
        duration_minutes=paper.duration_minutes,
        instructions=_texts(paper.instructions_json),
        sections=sections,
    )
    return render_paper(data, profile, resolve), template.version


def _new(db: Session, user: CurrentUser, paper_id: UUID, version: int, fmt: str) -> Export:
    item = Export(
        workspace_id=user.workspace_id,
        paper_id=paper_id,
        template_version=version,
        format=fmt,
        status="pending",
        storage_key=None,
        error_message=None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _succeed(db: Session, item: Export, storage: StorageBackend, data: bytes) -> None:
    key = f"{item.workspace_id}/exports/{item.id}.{item.format}"
    storage.put(key, data)
    item.storage_key = key
    item.status = "succeeded"
    db.commit()
    db.refresh(item)


def _fail(db: Session, item: Export, message: str) -> None:
    item.status = "failed"
    item.error_message = message[:1000]
    db.commit()
    db.refresh(item)


def _convert_pdf(docx: bytes, settings: Settings) -> bytes:
    configured = settings.libreoffice_bin
    binary = (
        configured
        if Path(configured).exists()
        else (shutil.which(configured) if Path(configured).name == configured else None)
    )
    if binary is None and configured == "/Applications/LibreOffice.app/Contents/MacOS/soffice":
        binary = shutil.which("soffice")
    if binary is None:
        raise RuntimeError("LibreOffice is unavailable")
    with tempfile.TemporaryDirectory(prefix="arche-export-") as directory:
        root = Path(directory)
        source = root / "paper.docx"
        source.write_bytes(docx)
        process = subprocess.Popen(
            [
                binary,
                "-env:UserInstallation=file:///tmp/arche-lo-profile",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(root),
                str(source),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=settings.export_max_pdf_timeout_s)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise RuntimeError("PDF conversion timed out") from None
        if process.returncode != 0:
            raise RuntimeError("PDF conversion failed")
        output = root / "paper.pdf"
        if not output.exists() or not output.read_bytes().startswith(b"%PDF"):
            raise RuntimeError("PDF conversion produced no valid PDF")
        del stdout, stderr
        return output.read_bytes()


def create_export(
    db: Session,
    paper_id: UUID,
    user: CurrentUser,
    fmt: str,
    storage: StorageBackend,
    settings: Settings,
) -> Export:
    if fmt not in {"docx", "pdf"}:
        raise HTTPException(422, "format must be docx or pdf")
    paper = get_paper(db, paper_id, user)
    template = db.get(TemplateProfile, paper.template_profile_id)
    if template is None:
        raise HTTPException(404, "Template not found")
    docx_export = _new(db, user, paper.id, template.version, "docx")
    docx_export.status = "processing"
    db.commit()
    try:
        docx, version = _render(db, paper.id, user, storage)
        docx_export.template_version = version
        _succeed(db, docx_export, storage, docx)
    except Exception:
        logger.exception("DOCX export failed paper_id=%s export_id=%s", paper.id, docx_export.id)
        _fail(db, docx_export, "Document rendering failed")
        return docx_export
    if fmt == "docx":
        return docx_export
    pdf_export = _new(db, user, paper.id, version, "pdf")
    pdf_export.status = "processing"
    db.commit()
    try:
        _succeed(db, pdf_export, storage, _convert_pdf(docx, settings))
    except Exception:
        logger.exception("PDF export failed paper_id=%s export_id=%s", paper.id, pdf_export.id)
        _fail(db, pdf_export, "PDF conversion failed")
    return pdf_export
