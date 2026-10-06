"""Composition root for HTTP requests: FastAPI providers -> services.

Routes depend only on the service/auth providers below; this module is the
single place that knows the concrete infrastructure classes.
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth_service import AuthPorts, AuthService
from app.application.billing_service import FareService
from app.application.category_service import CategoryService
from app.application.check_in_service import CheckInPorts, CheckInService
from app.application.check_out_service import (
    CheckOutContext,
    CheckOutRepositories,
    CheckOutService,
)
from app.application.idempotency_service import IdempotencyService
from app.application.monthly_pass_service import MonthlyPassService
from app.application.report_service import ReportService
from app.application.tariff_service import TariffService
from app.application.user_service import UserService
from app.application.vehicle_service import VehicleService
from app.core.config import settings
from app.domain.billing import FareCalculator
from app.domain.clock import Clock, system_clock
from app.domain.errors import AdminRequiredError, AuthenticationError, InvalidTokenError
from app.domain.evidence_storage import EvidenceStoragePort
from app.domain.login_attempts import LoginAttemptLimiter
from app.domain.ports import CachePort, IdempotencyStore, PasswordHasher, TokenIssuer
from app.domain.repositories import (
    CategoryRepository,
    EvidencePhotoRepository,
    MonthlyPassRepository,
    ParkingSessionRepository,
    ReportRepository,
    TariffRepository,
    UserRepository,
    VehicleRepository,
)
from app.domain.user import User, UserRole
from app.infrastructure.cached_repositories import (
    CachedCategoryRepository,
    CachedReportRepository,
    CachedTariffRepository,
    ReportCachePolicy,
)
from app.infrastructure.database import get_session
from app.infrastructure.local_evidence_storage import LocalEvidenceStorage
from app.infrastructure.repositories.category_repository import SqlAlchemyCategoryRepository
from app.infrastructure.repositories.evidence_photo_repository import (
    SqlAlchemyEvidencePhotoRepository,
)
from app.infrastructure.repositories.idempotency_repository import SqlAlchemyIdempotencyStore
from app.infrastructure.repositories.monthly_pass_repository import (
    SqlAlchemyMonthlyPassRepository,
)
from app.infrastructure.repositories.parking_session_repository import (
    SqlAlchemyParkingSessionRepository,
)
from app.infrastructure.repositories.report_repository import SqlAlchemyReportRepository
from app.infrastructure.repositories.tariff_repository import SqlAlchemyTariffRepository
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.repositories.vehicle_repository import SqlAlchemyVehicleRepository
from app.infrastructure.security import Argon2PasswordHasher, JwtConfig, JwtTokenIssuer
from app.infrastructure.shared_resources import SharedResources, build_shared_resources
from app.presentation.uploads import UploadLimits

_bearer = HTTPBearer(auto_error=False)

# Process-wide singletons. `_shared` starts in-process and is swapped for
# the configured (possibly Redis-backed) set by the app lifespan.
_evidence_storage = LocalEvidenceStorage(settings.evidence_storage_path)
_password_hasher = Argon2PasswordHasher()
_token_issuer = JwtTokenIssuer(
    JwtConfig(settings.secret_key, settings.jwt_algorithm, settings.access_token_expire_minutes)
)
_fare_calculator = FareCalculator(settings.business_zone)
_shared: SharedResources = build_shared_resources(None)


def install_shared_resources(resources: SharedResources) -> SharedResources:
    """Swap the process-wide adapters; returns the previous set."""
    global _shared
    previous, _shared = _shared, resources
    return previous


# --- Singletons ---------------------------------------------------------------


async def get_clock() -> Clock:
    return system_clock


async def get_login_limiter() -> LoginAttemptLimiter:
    return _shared.login_limiter


async def get_cache() -> CachePort:
    return _shared.cache


async def get_password_hasher() -> PasswordHasher:
    return _password_hasher


async def get_token_issuer() -> TokenIssuer:
    return _token_issuer


async def get_fare_calculator() -> FareCalculator:
    return _fare_calculator


async def get_evidence_storage() -> EvidenceStoragePort:
    return _evidence_storage


async def get_upload_limits() -> UploadLimits:
    return UploadLimits(settings.evidence_max_bytes, settings.evidence_max_files)


# --- Repositories (request-scoped, one shared session/transaction) -----------


async def get_user_repository(session: AsyncSession = Depends(get_session)) -> UserRepository:
    return SqlAlchemyUserRepository(session)


async def get_category_repository(
    session: AsyncSession = Depends(get_session), cache: CachePort = Depends(get_cache)
) -> CategoryRepository:
    return CachedCategoryRepository(SqlAlchemyCategoryRepository(session), cache)


async def get_tariff_repository(
    session: AsyncSession = Depends(get_session), cache: CachePort = Depends(get_cache)
) -> TariffRepository:
    return CachedTariffRepository(SqlAlchemyTariffRepository(session), cache)


async def get_vehicle_repository(session: AsyncSession = Depends(get_session)) -> VehicleRepository:
    return SqlAlchemyVehicleRepository(session)


async def get_parking_session_repository(
    session: AsyncSession = Depends(get_session),
) -> ParkingSessionRepository:
    return SqlAlchemyParkingSessionRepository(session)


async def get_evidence_photo_repository(
    session: AsyncSession = Depends(get_session),
) -> EvidencePhotoRepository:
    return SqlAlchemyEvidencePhotoRepository(session)


async def get_monthly_pass_repository(
    session: AsyncSession = Depends(get_session),
) -> MonthlyPassRepository:
    return SqlAlchemyMonthlyPassRepository(session)


async def get_report_repository(
    session: AsyncSession = Depends(get_session),
    cache: CachePort = Depends(get_cache),
    clock: Clock = Depends(get_clock),
) -> ReportRepository:
    policy = ReportCachePolicy(zone=settings.business_zone, clock=clock)
    return CachedReportRepository(SqlAlchemyReportRepository(session), cache, policy)


async def get_idempotency_store(session: AsyncSession = Depends(get_session)) -> IdempotencyStore:
    return SqlAlchemyIdempotencyStore(session)


# --- Services -------------------------------------------------------------------


async def get_auth_service(
    users: UserRepository = Depends(get_user_repository),
    limiter: LoginAttemptLimiter = Depends(get_login_limiter),
    hasher: PasswordHasher = Depends(get_password_hasher),
    tokens: TokenIssuer = Depends(get_token_issuer),
) -> AuthService:
    return AuthService(AuthPorts(users, limiter, hasher, tokens))


async def get_user_service(
    users: UserRepository = Depends(get_user_repository),
    hasher: PasswordHasher = Depends(get_password_hasher),
) -> UserService:
    return UserService(users, hasher)


async def get_category_service(
    categories: CategoryRepository = Depends(get_category_repository),
) -> CategoryService:
    return CategoryService(categories)


async def get_tariff_service(
    tariffs: TariffRepository = Depends(get_tariff_repository),
) -> TariffService:
    return TariffService(tariffs)


async def get_vehicle_service(
    vehicles: VehicleRepository = Depends(get_vehicle_repository),
) -> VehicleService:
    return VehicleService(vehicles)


async def get_monthly_pass_service(
    passes: MonthlyPassRepository = Depends(get_monthly_pass_repository),
    vehicles: VehicleRepository = Depends(get_vehicle_repository),
) -> MonthlyPassService:
    return MonthlyPassService(passes, vehicles)


async def get_report_service(
    reports: ReportRepository = Depends(get_report_repository),
) -> ReportService:
    return ReportService(reports)


async def get_fare_service(
    tariffs: TariffRepository = Depends(get_tariff_repository),
    calculator: FareCalculator = Depends(get_fare_calculator),
) -> FareService:
    return FareService(tariffs, calculator)


async def get_check_in_ports(
    vehicles: VehicleRepository = Depends(get_vehicle_repository),
    sessions: ParkingSessionRepository = Depends(get_parking_session_repository),
    photos: EvidencePhotoRepository = Depends(get_evidence_photo_repository),
    categories: CategoryRepository = Depends(get_category_repository),
    storage: EvidenceStoragePort = Depends(get_evidence_storage),
) -> CheckInPorts:
    return CheckInPorts(vehicles, sessions, photos, categories, storage)


async def get_check_in_service(
    ports: CheckInPorts = Depends(get_check_in_ports), clock: Clock = Depends(get_clock)
) -> CheckInService:
    return CheckInService(ports, clock)


async def get_check_out_repositories(
    sessions: ParkingSessionRepository = Depends(get_parking_session_repository),
    vehicles: VehicleRepository = Depends(get_vehicle_repository),
    tariffs: TariffRepository = Depends(get_tariff_repository),
    monthly_passes: MonthlyPassRepository = Depends(get_monthly_pass_repository),
) -> CheckOutRepositories:
    return CheckOutRepositories(sessions, vehicles, tariffs, monthly_passes)


async def get_check_out_service(
    repos: CheckOutRepositories = Depends(get_check_out_repositories),
    calculator: FareCalculator = Depends(get_fare_calculator),
    clock: Clock = Depends(get_clock),
) -> CheckOutService:
    return CheckOutService(repos, CheckOutContext(calculator, clock))


async def get_idempotency_service(
    store: IdempotencyStore = Depends(get_idempotency_store), clock: Clock = Depends(get_clock)
) -> IdempotencyService:
    return IdempotencyService(store, clock)


# --- Authentication / authorization --------------------------------------------


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    users: UserRepository = Depends(get_user_repository),
    tokens: TokenIssuer = Depends(get_token_issuer),
) -> User:
    if credentials is None:
        raise AuthenticationError()
    user = await users.get_by_username(tokens.subject_of(credentials.credentials))
    if user is None or not user.is_active:
        raise InvalidTokenError()
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise AdminRequiredError()
    return user
