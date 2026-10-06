"""Billing endpoints: optional live fare preview."""

from fastapi import APIRouter, Depends
from pydantic import AwareDatetime

from app.application.billing_service import FareService, StayQuery
from app.presentation.deps import get_current_user, get_fare_service

router = APIRouter(tags=["billing"])


@router.get("/billing/quote", dependencies=[Depends(get_current_user)])
async def get_fare_quote(
    category_id: int,
    entry_time: AwareDatetime,
    exit_time: AwareDatetime,
    service: FareService = Depends(get_fare_service),
) -> dict[str, str]:
    amount = await service.quote(StayQuery(category_id, entry_time, exit_time))
    return {"amount": str(amount)}
