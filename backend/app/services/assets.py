import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.storage import StorageBackend
from app.models import Asset
from app.services.authorization import assert_workspace_access

MAX_SIZE = 5 * 1024 * 1024
MIMES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def sniff_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def image_dimensions(data: bytes, mime: str) -> tuple[int | None, int | None]:
    if mime == "image/png" and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if mime == "image/gif" and len(data) >= 10:
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    if mime == "image/jpeg":
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9}:
                continue
            if offset + 2 > len(data):
                break
            length = int.from_bytes(data[offset : offset + 2], "big")
            if marker in {
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            } and offset + 7 <= len(data):
                return int.from_bytes(data[offset + 5 : offset + 7], "big"), int.from_bytes(
                    data[offset + 3 : offset + 5], "big"
                )
            if length < 2:
                break
            offset += length
    return None, None


def get_asset(db: Session, asset_id: UUID, user: CurrentUser) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    assert_workspace_access(asset.workspace_id, user.workspace_id)
    return asset


async def create_asset(
    db: Session, user: CurrentUser, storage: StorageBackend, kind: str, upload: UploadFile
) -> Asset:
    if kind not in {"logo", "question_image"}:
        raise HTTPException(422, "Invalid asset kind")
    name = Path(upload.filename or "upload").name
    ext = Path(name).suffix.casefold()
    if ext not in MIMES:
        raise HTTPException(415, "Unsupported image extension")
    data = await upload.read(MAX_SIZE + 1)
    if len(data) > MAX_SIZE:
        raise HTTPException(413, "Asset exceeds 5MB")
    sniffed = sniff_mime(data)
    if sniffed is None or upload.content_type != sniffed or MIMES[ext] != sniffed:
        raise HTTPException(415, "Image MIME type does not match content")
    width, height = image_dimensions(data, sniffed)
    if sniffed != "image/webp" and (not width or not height):
        raise HTTPException(415, "Invalid image")
    asset_id = uuid4()
    key = f"{user.workspace_id}/{asset_id}{ext}"
    safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:255] or "upload"
    storage.put(key, data)
    asset = Asset(
        id=asset_id,
        workspace_id=user.workspace_id,
        kind=kind,
        storage_key=key,
        original_filename=safe_name,
        mime_type=sniffed,
        size_bytes=len(data),
        width=width,
        height=height,
    )
    db.add(asset)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    db.refresh(asset)
    return asset


_EXT_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def create_asset_from_bytes(
    db: Session,
    user: CurrentUser,
    storage: StorageBackend,
    kind: str,
    data: bytes,
    original_filename: str,
) -> Asset:
    if kind not in {"logo", "question_image"}:
        raise HTTPException(422, "Invalid asset kind")
    mime = sniff_mime(data)
    if mime is None:
        raise HTTPException(415, "Unsupported image")
    width, height = image_dimensions(data, mime)
    asset_id = uuid4()
    key = f"{user.workspace_id}/{asset_id}{_EXT_BY_MIME[mime]}"
    safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_", original_filename)[:255] or "embedded"
    storage.put(key, data)
    asset = Asset(
        id=asset_id,
        workspace_id=user.workspace_id,
        kind=kind,
        storage_key=key,
        original_filename=safe_name,
        mime_type=mime,
        size_bytes=len(data),
        width=width,
        height=height,
    )
    db.add(asset)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    db.refresh(asset)
    return asset
