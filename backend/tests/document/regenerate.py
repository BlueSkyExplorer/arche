"""Regenerate deterministic binary fixture and renderer goldens.

From ``backend/`` run: ``REGEN_GOLDEN=1 uv run pytest tests/document -q -s``.
The PNG is generated first by running ``uv run python -m tests.document.regenerate``.
"""

import struct
import zlib
from difflib import unified_diff
from pathlib import Path


def update_golden(path: Path, actual: bytes) -> None:
    """Write a golden and show reviewers exactly what changed."""
    previous = path.read_bytes() if path.exists() else b""
    if previous != actual:
        previous_text = previous.decode(errors="replace").replace("><", ">\n<")
        actual_text = actual.decode(errors="replace").replace("><", ">\n<")
        diff = unified_diff(
            previous_text.splitlines(keepends=True),
            actual_text.splitlines(keepends=True),
            fromfile=str(path),
            tofile=f"{path} (regenerated)",
        )
        print("".join(diff), end="")
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(actual)


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
