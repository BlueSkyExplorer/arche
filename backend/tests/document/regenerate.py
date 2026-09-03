"""Regenerate deterministic binary fixture and renderer goldens.

From ``backend/`` run: ``REGEN_GOLDEN=1 uv run pytest tests/document -q``.
The PNG is generated first by running ``uv run python -m tests.document.regenerate``.
"""

import struct
import zlib
from pathlib import Path


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def main() -> None:
    fixtures = Path(__file__).parents[1] / "fixtures"
    raw = b"\x00\x33\x66\x99"
    png = b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    png += png_chunk(b"IDAT", zlib.compress(raw)) + png_chunk(b"IEND", b"")
    (fixtures / "tiny.png").write_bytes(png)


if __name__ == "__main__":
    main()
