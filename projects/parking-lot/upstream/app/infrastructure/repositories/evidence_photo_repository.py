"""SQLAlchemy implementation of the evidence photo repository port."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.evidence_photo import EvidencePhoto
from app.domain.repositories import EvidencePhotoRepository
from app.infrastructure.models import EvidencePhotoModel


class SqlAlchemyEvidencePhotoRepository(EvidencePhotoRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: EvidencePhotoModel) -> EvidencePhoto:
        return EvidencePhoto(
            id=model.id,
            session_id=model.session_id,
            file_path=model.file_path,
            taken_at=model.taken_at,
        )

    async def list_by_session_id(self, session_id: int) -> list[EvidencePhoto]:
        result = await self._session.execute(
            select(EvidencePhotoModel)
            .where(EvidencePhotoModel.session_id == session_id)
            .order_by(EvidencePhotoModel.id)
        )
        return [self._to_entity(model) for model in result.scalars()]

    async def list_by_session_ids(self, session_ids: list[int]) -> list[EvidencePhoto]:
        if not session_ids:
            return []
        result = await self._session.execute(
            select(EvidencePhotoModel)
            .where(EvidencePhotoModel.session_id.in_(session_ids))
            .order_by(EvidencePhotoModel.session_id, EvidencePhotoModel.id)
        )
        return [self._to_entity(model) for model in result.scalars()]

    async def create(self, photo: EvidencePhoto) -> EvidencePhoto:
        model = EvidencePhotoModel(
            session_id=photo.session_id,
            file_path=photo.file_path,
            taken_at=photo.taken_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)
