"""Health endpoint tests (Success / Failure / Security)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_returns_ok(client):
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_unknown_route_returns_not_found(client):
    response = await client.get("/api/unknown")

    assert response.status_code == 404


async def test_health_does_not_leak_configuration(client):
    response = await client.get("/api/health")

    body = response.json()
    assert "database_url" not in body
    assert "secret_key" not in body
    assert response.headers.get("server") is None
