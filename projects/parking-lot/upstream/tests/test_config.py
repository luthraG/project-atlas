"""Settings validation and CORS policy tests (Success / Failure / Security)."""

import pytest
from pydantic import ValidationError

from app.core.config import PLACEHOLDER_SECRET_KEY, Settings

STRONG_KEY = "k" * 48


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_production_accepts_strong_secret():
    settings = _settings(environment="production", secret_key=STRONG_KEY)

    assert settings.secret_key == STRONG_KEY


def test_production_rejects_placeholder_secret():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _settings(environment="production", secret_key=PLACEHOLDER_SECRET_KEY)


def test_production_rejects_short_secret():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _settings(environment="production", secret_key="x" * 31)


def test_default_environment_is_production_secure_by_default(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    with pytest.raises(ValidationError):
        _settings()


@pytest.mark.parametrize("environment", ["development", "test"])
def test_dev_and_test_allow_placeholder(environment):
    settings = _settings(environment=environment)

    assert settings.secret_key == PLACEHOLDER_SECRET_KEY


def test_business_timezone_defaults_to_bogota():
    assert _settings(environment="test").business_timezone == "America/Bogota"


def test_invalid_business_timezone_is_rejected():
    with pytest.raises(ValidationError):
        _settings(environment="test", business_timezone="Mars/Olympus")


def test_cors_origins_default_to_none_and_parse_list():
    assert _settings(environment="test").cors_origin_list == []
    parsed = _settings(environment="test", cors_origins="http://a, http://b ,")
    assert parsed.cors_origin_list == ["http://a", "http://b"]


async def test_cors_does_not_allow_credentials_or_unknown_origins(client):
    response = await client.options(
        "/api/health",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers
