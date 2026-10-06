"""Pydantic DTOs, one module per feature (re-exported for convenience)."""

from app.presentation.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.presentation.schemas.categories import (
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
)
from app.presentation.schemas.check_ins import (
    CheckInForm,
    CheckInRead,
    EvidencePhotoRead,
)
from app.presentation.schemas.check_outs import (
    CheckOutRead,
    CheckOutRequest,
)
from app.presentation.schemas.monthly_passes import (
    MonthlyPassCreate,
    MonthlyPassRead,
    MonthlyPassUpdate,
)
from app.presentation.schemas.reports import (
    CategoryOccupancyRead,
    CategoryRevenueRead,
    DailyRevenueRead,
    OccupancyReportRead,
    RevenueReportRead,
)
from app.presentation.schemas.tariffs import (
    TariffCreate,
    TariffRead,
    TariffUpdate,
)
from app.presentation.schemas.vehicles import (
    VehicleCreate,
    VehicleRead,
    VehicleUpdate,
)

__all__ = [
    "CheckInForm",
    "CategoryCreate",
    "CategoryOccupancyRead",
    "CategoryRead",
    "CategoryRevenueRead",
    "CategoryUpdate",
    "CheckInRead",
    "CheckOutRead",
    "CheckOutRequest",
    "DailyRevenueRead",
    "EvidencePhotoRead",
    "LoginRequest",
    "MonthlyPassCreate",
    "MonthlyPassRead",
    "MonthlyPassUpdate",
    "OccupancyReportRead",
    "RevenueReportRead",
    "TariffCreate",
    "TariffRead",
    "TariffUpdate",
    "TokenResponse",
    "UserCreate",
    "UserRead",
    "UserUpdate",
    "VehicleCreate",
    "VehicleRead",
    "VehicleUpdate",
]
