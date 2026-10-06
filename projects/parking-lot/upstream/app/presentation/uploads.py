"""Evidence upload validation at the HTTP edge (size, count, real type)."""

from dataclasses import dataclass

from fastapi import UploadFile

from app.domain.errors import DomainValidationError, InvalidPhotoError, PhotoTooLargeError
from app.domain.evidence_photo import PhotoUpload, detect_image_extension

_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class UploadLimits:
    max_bytes: int
    max_files: int


async def read_photo_uploads(uploads: list[UploadFile], limits: UploadLimits) -> list[PhotoUpload]:
    """Validate every upload before anything is stored.

    422 when more than `max_files` or the content is not JPEG/PNG (sniffed
    magic bytes; client filename/Content-Type are ignored); 413 when one
    file exceeds `max_bytes`.
    """
    if len(uploads) > limits.max_files:
        raise DomainValidationError(f"At most {limits.max_files} photos are allowed")
    return [await _read_photo(upload, limits.max_bytes) for upload in uploads]


async def _read_photo(upload: UploadFile, max_bytes: int) -> PhotoUpload:
    content = await _read_limited(upload, max_bytes)
    extension = detect_image_extension(content)
    if extension is None:
        raise InvalidPhotoError()
    return PhotoUpload(content=content, extension=extension)


async def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    buffer = bytearray()
    while chunk := await upload.read(_CHUNK_BYTES):
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise PhotoTooLargeError(
                f"Each photo must be at most {max_bytes // (1024 * 1024)} MB"
            )
    return bytes(buffer)
