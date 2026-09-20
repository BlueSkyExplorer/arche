"""Deterministically rasterize grouped Word drawings into PNG assets.

Legacy ``.doc`` diagrams often become DrawingML group shapes after the existing
LibreOffice conversion.  python-docx cannot render those shapes.  LibreOffice's
own graphic export filter can, without OCR or interpretation, so answer-sheet
imports use it as a lossless bridge to the typed image-content representation.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from app.core.config import Settings
from app.exam.parsing.blocks import BlockKind, DocumentBlock, ParseResult


class ShapeRasterizationError(RuntimeError):
    pass


_UNO_SCRIPT = r'''import sys
import time
import uno
from com.sun.star.beans import PropertyValue

def prop(name, value):
    item = PropertyValue()
    item.Name = name
    item.Value = value
    return item

context = uno.getComponentContext()
resolver = context.ServiceManager.createInstanceWithContext(
    "com.sun.star.bridge.UnoUrlResolver", context
)
remote = None
for _ in range(50):
    try:
        remote = resolver.resolve(
            f"uno:socket,host=127.0.0.1,port={sys.argv[1]};urp;StarOffice.ComponentContext"
        )
        break
    except Exception:
        time.sleep(0.1)
if remote is None:
    raise RuntimeError("LibreOffice listener did not start")
services = remote.ServiceManager
desktop = services.createInstanceWithContext("com.sun.star.frame.Desktop", remote)
document = desktop.loadComponentFromURL(
    uno.systemPathToFileUrl(sys.argv[2]), "_blank", 0, (prop("Hidden", True),)
)
if document is None:
    raise RuntimeError("LibreOffice could not open DOCX")
exporter = services.createInstanceWithContext(
    "com.sun.star.drawing.GraphicExportFilter", remote
)
output_index = 0
for index in range(document.DrawPage.Count):
    shape = document.DrawPage.getByIndex(index)
    if shape.ShapeType != "com.sun.star.drawing.GroupShape":
        continue
    exporter.setSourceDocument(shape)
    target = f"{sys.argv[3]}/shape-{output_index:04d}.png"
    if not exporter.filter(
        (prop("URL", uno.systemPathToFileUrl(target)), prop("MediaType", "image/png"))
    ):
        raise RuntimeError("group-shape export failed")
    output_index += 1
document.close(True)
'''


def _office_binary(settings: Settings) -> Path:
    configured = settings.libreoffice_bin
    candidate = Path(configured)
    if candidate.exists():
        return candidate
    resolved = shutil.which(configured if candidate.name == configured else candidate.name)
    if resolved is None and configured.endswith("/soffice"):
        resolved = shutil.which("soffice")
    if resolved is None:
        raise ShapeRasterizationError("LibreOffice is unavailable for grouped drawings")
    return Path(resolved)


def _available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _python_candidates(office: Path, settings: Settings) -> list[Path]:
    """Return UNO-capable Python runtimes, preferring explicit deployment config.

    Rootless LibreOffice installs commonly use a wrapper for ``LIBREOFFICE_BIN``;
    in that case ``office.parent / 'python'`` points at the wrapper directory,
    not LibreOffice's bundled ABI-compatible Python.  ``LIBREOFFICE_PYTHON_BIN``
    keeps that deployment detail explicit without hard-coding a host path.
    """
    candidates: list[Path] = []
    if settings.libreoffice_python_bin:
        configured = Path(settings.libreoffice_python_bin)
        if configured.exists():
            candidates.append(configured)
        elif configured.name == settings.libreoffice_python_bin:
            resolved = shutil.which(settings.libreoffice_python_bin)
            if resolved:
                candidates.append(Path(resolved))
    candidates.append(office.parent / "python")
    system_python = shutil.which("python3")
    if system_python:
        candidates.append(Path(system_python))
    return list(dict.fromkeys(item for item in candidates if item.exists()))


def rasterize_group_shapes(data: bytes, settings: Settings) -> list[bytes]:
    """Return grouped drawings in document order as deterministic PNG bytes."""
    office = _office_binary(settings)
    python_candidates = _python_candidates(office, settings)
    if not python_candidates:
        raise ShapeRasterizationError("LibreOffice Python/UNO runtime is unavailable")

    with tempfile.TemporaryDirectory(prefix="arche-shapes-") as directory:
        root = Path(directory)
        source = root / "source.docx"
        output = root / "output"
        profile = root / "profile"
        output.mkdir()
        source.write_bytes(data)
        port = _available_port()
        env = os.environ.copy()
        env.setdefault("SAL_USE_VCLPLUGIN", "svp")
        listener = subprocess.Popen(
            [
                str(office),
                f"-env:UserInstallation={profile.as_uri()}",
                "--headless",
                f"--accept=socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext",
                "--norestore",
                "--nodefault",
                "--nolockcheck",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        last_error = "UNO export failed"
        try:
            for python in python_candidates:
                result = subprocess.run(
                    [str(python), "-c", _UNO_SCRIPT, str(port), str(source), str(output)],
                    capture_output=True,
                    timeout=30,
                    check=False,
                    env=env,
                )
                if result.returncode == 0:
                    return [path.read_bytes() for path in sorted(output.glob("shape-*.png"))]
                last_error = result.stderr.decode(errors="replace")[-500:]
                time.sleep(0.1)
        except subprocess.TimeoutExpired as exc:
            raise ShapeRasterizationError("grouped-drawing rasterization timed out") from exc
        finally:
            listener.terminate()
            try:
                listener.wait(timeout=5)
            except subprocess.TimeoutExpired:
                listener.kill()
                listener.wait()
        raise ShapeRasterizationError(last_error)


def attach_group_shape_assets(parsed: ParseResult, data: bytes, settings: Settings) -> None:
    """Attach rasterized groups to non-text table cells only when mapping is exact."""
    cells: list[tuple[DocumentBlock, str]] = []
    for block in parsed.blocks:
        if block.kind != BlockKind.TABLE:
            continue
        for cell, kind in block.meta.get("non_text_cells", {}).items():
            if kind in {"drawing", "image"}:
                cells.append((block, str(cell)))
    if not cells:
        return
    images = rasterize_group_shapes(data, settings)
    if len(images) != len(cells):
        raise ShapeRasterizationError(
            f"ambiguous grouped-drawing mapping ({len(images)} drawings for {len(cells)} cells)"
        )
    for index, ((block, cell), image) in enumerate(zip(cells, images, strict=True)):
        local_id = f"shape-{index}"
        parsed.assets[local_id] = image
        cell_assets = block.meta.setdefault("cell_assets", {})
        cell_assets[cell] = [{"local_id": local_id, "mime_type": "image/png"}]
