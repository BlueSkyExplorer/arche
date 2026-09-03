from pathlib import Path

import pytest

from app.core.storage import LocalDirStorage
from app.services.assets import image_dimensions, sniff_mime


def test_local_storage_round_trip_and_path_safety(tmp_path: Path) -> None:
    storage = LocalDirStorage(tmp_path)
    storage.put("workspace/item.bin", b"private")
    assert storage.get("workspace/item.bin") == b"private"
    storage.delete("workspace/item.bin")
    with pytest.raises(FileNotFoundError):
        storage.get("workspace/item.bin")
    with pytest.raises(ValueError):
        storage.put("../escape", b"no")


def test_magic_sniffing_and_png_dimensions() -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + (2).to_bytes(4, "big") + (3).to_bytes(4, "big")
    assert sniff_mime(png) == "image/png"
    assert image_dimensions(png, "image/png") == (2, 3)
    assert sniff_mime(b"<svg></svg>") is None
