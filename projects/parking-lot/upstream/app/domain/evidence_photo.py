"""Evidence photo domain entity."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class EvidencePhoto:
    id: int | None
    session_id: int
    file_path: str
    taken_at: datetime


@dataclass(frozen=True)
class PhotoUpload:
    """Validated photo bytes plus the extension derived from its content."""

    content: bytes
    extension: str


# Magic-byte signatures of the only accepted evidence formats.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
)


def detect_image_extension(content: bytes) -> str | None:
    """Return ".jpg"/".png" from the file's magic bytes, else None.

    Client-supplied filename and Content-Type are never trusted.
    """
    for signature, extension in _SIGNATURES:
        if content.startswith(signature):
            return extension
    return None
