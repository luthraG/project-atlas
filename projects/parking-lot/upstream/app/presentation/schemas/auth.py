"""Auth and user management DTOs."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.user import UserRole


class LoginRequest(BaseModel):
    username: str = Field(max_length=50)
    # Loose upper bound (not the 4-6 digit rule) so a bad PIN stays a 401,
    # while huge payloads never reach Argon2.
    pin: str = Field(max_length=64)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: UserRole
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    display_name: str = Field(min_length=1, max_length=100)
    role: UserRole
    pin: str = Field(max_length=64)

    @field_validator("pin")
    @classmethod
    def pin_must_be_digits(cls, value: str) -> str:
        if not value.isdigit() or not 4 <= len(value) <= 6:
            raise ValueError("PIN must be 4 to 6 digits")
        return value


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: UserRole | None = None
    is_active: bool | None = None
