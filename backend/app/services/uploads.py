"""Shared upload validation for import/ingest endpoints."""
from __future__ import annotations

from fastapi import HTTPException

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = (".doc", ".docx")


def validate_document_upload(filename: str, size: int) -> str:
    """Return the normalized lower-case extension, or raise a controlled HTTPException."""
    name = (filename or "").lower()
    if name.endswith(".docm") or ".docm" in name:
        raise HTTPException(status_code=415, detail="Macro-enabled documents are not supported")
    ext = next((e for e in ALLOWED_EXTENSIONS if name.endswith(e)), None)
    if ext is None:
        raise HTTPException(status_code=415, detail="Only .doc and .docx files are supported")
    if size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")
    return ext