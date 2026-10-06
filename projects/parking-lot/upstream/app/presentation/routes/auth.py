"""Authentication endpoints."""

from fastapi import APIRouter, Depends, Request

from app.application.auth_service import AuthService, LoginAttempt
from app.presentation.deps import get_auth_service
from app.presentation.schemas import LoginRequest, TokenResponse, UserRead

router = APIRouter(tags=["auth"])


def _client_ip(request: Request) -> str:
    # Direct client address; X-Forwarded-For is NOT trusted (no proxy).
    return request.client.host if request.client else "unknown"


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    user = await service.login(LoginAttempt(body.username, body.pin, _client_ip(request)))
    return TokenResponse(access_token=service.issue_token(user), user=UserRead.model_validate(user))
