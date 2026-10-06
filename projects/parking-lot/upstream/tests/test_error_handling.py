"""Global error contract (B-ERR): {"detail", "code"} for every domain error."""

import logging

from app.main import app
from app.presentation.deps import get_category_service


async def test_not_found_maps_to_404_with_code(client, admin_headers):
    response = await client.patch(
        "/api/vehicles/999", json={"color": "red"}, headers=admin_headers
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Vehicle not found", "code": "VehicleNotFoundError"}


async def test_conflict_maps_to_409_with_code(client, admin_headers):
    await client.post("/api/categories", json={"name": "moto"}, headers=admin_headers)

    response = await client.post("/api/categories", json={"name": "moto"}, headers=admin_headers)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Category already exists",
        "code": "DuplicateCategoryNameError",
    }


async def test_domain_validation_maps_to_422_with_original_message(client, admin_headers):
    category = await client.post("/api/categories", json={"name": "c"}, headers=admin_headers)

    response = await client.post(
        "/api/tariffs",
        json={"category_id": category.json()["id"], "type": "hourly", "amount": 0},
        headers=admin_headers,
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Amount must be a positive integer",
        "code": "DomainValidationError",
    }


async def test_missing_token_is_401_with_code(client):
    response = await client.get("/api/categories")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
    assert response.json()["code"] == "AuthenticationError"


async def test_operator_on_admin_route_is_403_with_code(client, operator_headers):
    response = await client.get("/api/users", headers=operator_headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin required", "code": "AdminRequiredError"}


async def test_unexpected_error_is_generic_500_without_leak(
    unsafe_client, operator_headers, caplog
):
    def _boom():
        raise RuntimeError("postgres://user:s3cret@db leaked")

    app.dependency_overrides[get_category_service] = _boom

    with caplog.at_level(logging.ERROR):
        response = await unsafe_client.get("/api/categories", headers=operator_headers)

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error", "code": "InternalError"}
    assert "s3cret" not in response.text
    assert "Traceback" not in response.text
    assert any("s3cret" in (r.exc_text or "") or r.exc_info for r in caplog.records)


async def test_request_validation_keeps_fastapi_shape(client, admin_headers):
    response = await client.post("/api/categories", json={}, headers=admin_headers)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
