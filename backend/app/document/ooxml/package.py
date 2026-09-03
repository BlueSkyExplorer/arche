"""Helpers for producing reproducible OOXML ZIP packages."""

from io import BytesIO
from zipfile import ZipFile, ZipInfo

_FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def normalize_zip_timestamps(package: bytes) -> bytes:
    """Rewrite a ZIP package with a stable timestamp on every member."""
    source = BytesIO(package)
    output = BytesIO()
    with ZipFile(source) as archive, ZipFile(output, "w") as normalized:
        for original in archive.infolist():
            info = ZipInfo(original.filename, _FIXED_ZIP_TIMESTAMP)
            info.compress_type = original.compress_type
            info.comment = original.comment
            info.extra = original.extra
            info.internal_attr = original.internal_attr
            info.external_attr = original.external_attr
            info.create_system = original.create_system
            normalized.writestr(info, archive.read(original.filename))
    return output.getvalue()
