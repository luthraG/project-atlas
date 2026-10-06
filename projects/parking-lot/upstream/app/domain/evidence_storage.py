"""Evidence photo storage port."""

from abc import ABC, abstractmethod


class EvidenceStoragePort(ABC):
    @abstractmethod
    async def save(self, content: bytes, extension: str) -> str:
        """Persist already-validated photo bytes; return the stored path."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Remove a stored photo (compensation); missing files are ignored."""
        raise NotImplementedError
