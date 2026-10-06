"""List endpoints: limit/offset + X-Total-Count; body stays a JSON list."""

import pytest
from sqlalchemy import event

from app.domain.user import UserRole

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16 + b"jpeg-body"


async def _category(client, headers, name="carro") -> int:
    response = await client.post("/api/categories", json={"name": name}, headers=headers)
    return response.json()["id"]


async def _vehicles(client, headers, count: int) -> list[dict]:
    category_id = await _category(client, headers)
    created = []
    for index in range(count):
        response = await client.post(
            "/api/vehicles",
            json={"plate": f"PAG{index:03d}", "category_id": category_id},
            headers=headers,
        )
        created.append(response.json())
    return created


async def test_vehicles_page_with_total_header(client, admin_headers):
    await _vehicles(client, admin_headers, 5)

    response = await client.get("/api/vehicles?limit=2&offset=1", headers=admin_headers)

    assert response.status_code == 200
    assert [v["plate"] for v in response.json()] == ["PAG001", "PAG002"]
    assert response.headers["X-Total-Count"] == "5"


async def test_default_page_returns_everything_small(client, admin_headers):
    await _vehicles(client, admin_headers, 3)

    response = await client.get("/api/vehicles", headers=admin_headers)

    assert len(response.json()) == 3
    assert response.headers["X-Total-Count"] == "3"


@pytest.mark.parametrize("query", ["limit=0", "limit=501", "offset=-1", "limit=abc"])
async def test_out_of_bounds_pagination_is_422(client, admin_headers, query):
    response = await client.get(f"/api/vehicles?{query}", headers=admin_headers)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "path", ["/api/users", "/api/categories", "/api/tariffs", "/api/monthly-passes",
             "/api/check-ins"],
)
async def test_every_list_endpoint_exposes_total(client, admin_headers, path):
    response = await client.get(f"{path}?limit=1", headers=admin_headers)

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "X-Total-Count" in response.headers


async def test_users_are_paginated(client, admin_headers, seed_user):
    await seed_user("zed", UserRole.OPERATOR)

    response = await client.get("/api/users?limit=1&offset=1", headers=admin_headers)

    assert [u["username"] for u in response.json()] == ["zed"]
    assert response.headers["X-Total-Count"] == "2"


async def test_vehicle_read_exposes_created_by(client, admin_headers, operator_headers):
    category_id = await _category(client, admin_headers)
    await client.post("/api/check-ins", data={"plate": "NEW1", "category_id": category_id},
                      headers=operator_headers)
    admin_created = await client.post(
        "/api/vehicles", json={"plate": "ADM1", "category_id": category_id},
        headers=admin_headers,
    )

    listed = {v["plate"]: v for v in
              (await client.get("/api/vehicles", headers=admin_headers)).json()}

    assert isinstance(listed["NEW1"]["created_by"], int)
    assert admin_created.json()["created_by"] is None


def _count_queries(session_factory) -> list[str]:
    statements: list[str] = []
    engine = session_factory.kw["bind"].sync_engine

    @event.listens_for(engine, "before_cursor_execute")
    def _record(_conn, _cursor, statement, *_args):
        statements.append(statement)

    return statements


async def _open_check_ins(client, admin_headers, operator_headers, count, tmp_path):
    from app.infrastructure.local_evidence_storage import LocalEvidenceStorage
    from app.main import app
    from app.presentation.deps import get_evidence_storage

    storage = LocalEvidenceStorage(str(tmp_path))
    app.dependency_overrides[get_evidence_storage] = lambda: storage
    category_id = await _category(client, admin_headers, name=f"cat{count}")
    for index in range(count):
        await client.post(
            "/api/check-ins",
            data={"plate": f"N{count}X{index}", "category_id": category_id},
            files=[("photos", ("p.jpg", JPEG, "image/jpeg"))],
            headers=operator_headers,
        )


async def test_list_check_ins_uses_constant_queries(
    client, session_factory, admin_headers, operator_headers, tmp_path
):
    await _open_check_ins(client, admin_headers, operator_headers, 1, tmp_path)
    statements = _count_queries(session_factory)
    await client.get("/api/check-ins", headers=operator_headers)
    single = len(statements)
    await _open_check_ins(client, admin_headers, operator_headers, 4, tmp_path)
    statements.clear()

    response = await client.get("/api/check-ins", headers=operator_headers)

    assert len(response.json()) == 5
    assert all(len(item["photos"]) == 1 for item in response.json())
    assert all(item["photo_count"] == 1 for item in response.json())
    assert {item["plate"] for item in response.json()} == {
        "N1X0", "N4X0", "N4X1", "N4X2", "N4X3"}
    assert len(statements) == single
