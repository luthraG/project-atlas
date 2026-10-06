"""Vehicle endpoints."""

from fastapi import APIRouter, Depends, Response, status

from app.application.vehicle_service import VehiclePatch, VehicleService
from app.domain.pagination import Page, PageRequest
from app.domain.vehicle import Vehicle
from app.presentation.deps import get_current_user, get_vehicle_service, require_admin
from app.presentation.pagination import page_request, with_total
from app.presentation.schemas import VehicleCreate, VehicleRead, VehicleUpdate

router = APIRouter(tags=["vehicles"])


@router.get(
    "/vehicles",
    response_model=list[VehicleRead],
    dependencies=[Depends(get_current_user)],
)
async def list_vehicles(
    response: Response,
    plate: str | None = None,
    page: PageRequest = Depends(page_request),
    service: VehicleService = Depends(get_vehicle_service),
) -> list[VehicleRead]:
    if plate is not None:
        vehicle = await service.find_by_plate(plate)
        result = Page([vehicle] if vehicle else [], 1 if vehicle else 0)
    else:
        result = await service.list_page(page)
    return [VehicleRead.model_validate(vehicle) for vehicle in with_total(response, result)]


@router.post(
    "/vehicles",
    response_model=VehicleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_vehicle(
    body: VehicleCreate, service: VehicleService = Depends(get_vehicle_service)
) -> VehicleRead:
    vehicle = Vehicle(id=None, plate=body.plate, category_id=body.category_id,
                      color=body.color, brand=body.brand)
    return VehicleRead.model_validate(await service.create(vehicle))


@router.patch(
    "/vehicles/{vehicle_id}",
    response_model=VehicleRead,
    dependencies=[Depends(require_admin)],
)
async def update_vehicle(
    vehicle_id: int,
    body: VehicleUpdate,
    service: VehicleService = Depends(get_vehicle_service),
) -> VehicleRead:
    patch = VehiclePatch(**body.model_dump())
    return VehicleRead.model_validate(await service.update(vehicle_id, patch))


@router.delete(
    "/vehicles/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_vehicle(
    vehicle_id: int, service: VehicleService = Depends(get_vehicle_service)
) -> None:
    await service.delete(vehicle_id)
