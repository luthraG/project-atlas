"""Conditional GET (ETag / If-None-Match) on read-mostly catalogs."""

import pytest


@pytest.fixture
async def seeded(client, admin_headers):
    category = await client.post("/api/categories", json={"name": "carro"}, headers=admin_headers)
    await client.post(
        "/api/tariffs",
        json={"category_id": category.json()["id"], "type": "hourly", "amount": 3000},
        headers=admin_headers,
    )
    return admin_headers


@pytest.mark.parametrize("path", ["/api/categories", "/api/tariffs"])
async def test_get_returns_weak_etag_and_private_cache_control(client, seeded, path):
    response = await client.get(path, headers=seeded)

    assert response.status_code == 200
    assert response.headers["ETag"].startswith('W/"')
    assert response.headers["Cache-Control"] == "private, max-age=60"


@pytest.mark.parametrize("path", ["/api/categories", "/api/tariffs"])
async def test_matching_if_none_match_returns_304_without_body(client, seeded, path):
    etag = (await client.get(path, headers=seeded)).headers["ETag"]

    response = await client.get(path, headers={**seeded, "If-None-Match": etag})

    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["ETag"] == etag


async def test_etag_changes_after_write(client, seeded):
    first = (await client.get("/api/categories", headers=seeded)).headers["ETag"]
    await client.post("/api/categories", json={"name": "moto"}, headers=seeded)

    response = await client.get("/api/categories", headers={**seeded, "If-None-Match": first})

    assert response.status_code == 200
    assert response.headers["ETag"] != first


async def test_conditional_get_still_requires_auth(client, seeded):
    etag = (await client.get("/api/categories", headers=seeded)).headers["ETag"]

    response = await client.get("/api/categories", headers={"If-None-Match": etag})

    assert response.status_code == 401
