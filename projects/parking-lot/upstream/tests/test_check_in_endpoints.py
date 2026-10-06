"""Check-in endpoint tests (Success / Failure / Security)."""

import os

from app.core.security import hash_password
from app.domain.user import User, UserRole
from app.infrastructure.local_evidence_storage import LocalEvidenceStorage
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from app.main import app
from app.presentation.deps import get_evidence_storage

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16 + b"jpeg-body"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16 + b"png-body"


async def _seed_user(session_factory, username, role, pin="1234"):
    async with session_factory() as session:
        repository = SqlAlchemyUserRepository(session)
        await repository.create(
            User(
                id=None,
                username=username,
                display_name=username.title(),
                role=role,
                pin_hash=hash_password(pin),
            )
        )
        await session.commit()


async def _login(client, username, pin="1234"):
    return await client.post(
        "/api/auth/login", json={"username": username, "pin": pin}
    )


async def _operator_headers(client, session_factory):
    await _seed_user(session_factory, "operator", UserRole.OPERATOR)
    token = (await _login(client, "operator")).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_vehicle(client, headers, plate="ABC123"):
    category = await client.post(
        "/api/categories", json={"name": "carro"}, headers=headers
    )
    if category.status_code != 201:
        # non-admin cannot create categories/vehicles; use admin instead.
        raise AssertionError("expected admin headers for setup")
    vehicle = await client.post(
        "/api/vehicles",
        json={"plate": plate, "category_id": category.json()["id"]},
        headers=headers,
    )
    return vehicle.json()


async def _admin_headers(client, session_factory):
    await _seed_user(session_factory, "admin", UserRole.ADMIN)
    token = (await _login(client, "admin")).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _use_tmp_storage(tmp_path):
    storage = LocalEvidenceStorage(str(tmp_path))
    app.dependency_overrides[get_evidence_storage] = lambda: storage


async def test_check_in_existing_vehicle_with_photos(
    client, session_factory, tmp_path
):
    admin_headers = await _admin_headers(client, session_factory)
    await _create_vehicle(client, admin_headers)
    operator_headers = await _operator_headers(client, session_factory)
    _use_tmp_storage(tmp_path)

    response = await client.post(
        "/api/check-ins",
        data={"plate": "abc123"},
        files=[("photos", ("dent.jpg", JPEG, "image/jpeg"))],
        headers=operator_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "open"
    assert len(body["photos"]) == 1
    assert body["plate"] == "ABC123"
    assert body["photo_count"] == 1
    stored_path = os.path.join(str(tmp_path), body["photos"][0]["file_path"])
    assert os.path.isfile(stored_path)
    with open(stored_path, "rb") as f:
        assert f.read() == JPEG
    assert stored_path.endswith(".jpg")


async def test_check_in_without_photos(client, session_factory, tmp_path):
    admin_headers = await _admin_headers(client, session_factory)
    await _create_vehicle(client, admin_headers, plate="NOPHOTO1")
    operator_headers = await _operator_headers(client, session_factory)
    _use_tmp_storage(tmp_path)

    response = await client.post(
        "/api/check-ins",
        data={"plate": "NOPHOTO1"},
        headers=operator_headers,
    )

    assert response.status_code == 201
    assert response.json()["photos"] == []
    assert response.json()["photo_count"] == 0


async def _create_category(client, headers, name="moto"):
    response = await client.post(
        "/api/categories", json={"name": name}, headers=headers
    )
    return response.json()["id"]


async def _vehicles_by_plate(client, headers, plate):
    response = await client.get(
        "/api/vehicles", params={"plate": plate}, headers=headers
    )
    return response.json()


async def test_check_in_existing_plate_ignores_new_vehicle_fields(
    client, session_factory, tmp_path
):
    admin_headers = await _admin_headers(client, session_factory)
    vehicle = await _create_vehicle(client, admin_headers, plate="KEEP123")
    other_category = await _create_category(client, admin_headers)
    operator_headers = await _operator_headers(client, session_factory)
    _use_tmp_storage(tmp_path)

    response = await client.post(
        "/api/check-ins",
        data={
            "plate": "keep123",
            "category_id": str(other_category),
            "color": "blue",
            "brand": "Mazda",
        },
        headers=operator_headers,
    )

    assert response.status_code == 201
    assert response.json()["vehicle_id"] == vehicle["id"]
    stored = await _vehicles_by_plate(client, operator_headers, "KEEP123")
    assert len(stored) == 1
    assert stored[0]["category_id"] == vehicle["category_id"]
    assert stored[0]["color"] is None
    assert stored[0]["brand"] is None


async def test_check_in_new_plate_with_category_registers_vehicle(
    client, session_factory, tmp_path
):
    admin_headers = await _admin_headers(client, session_factory)
    category_id = await _create_category(client, admin_headers)
    operator_headers = await _operator_headers(client, session_factory)
    _use_tmp_storage(tmp_path)

    response = await client.post(
        "/api/check-ins",
        data={
            "plate": "NEW123",
            "category_id": str(category_id),
            "color": "red",
            "brand": "Yamaha",
        },
        headers=operator_headers,
    )

    assert response.status_code == 201
    stored = await _vehicles_by_plate(client, operator_headers, "NEW123")
    assert len(stored) == 1
    assert stored[0]["id"] == response.json()["vehicle_id"]
    assert stored[0]["category_id"] == category_id
    assert stored[0]["color"] == "red"
    assert stored[0]["brand"] == "Yamaha"


async def test_check_in_new_plate_without_category_is_unprocessable(
    client, session_factory, tmp_path
):
    operator_headers = await _operator_headers(client, session_factory)
    _use_tmp_storage(tmp_path)

    response = await client.post(
        "/api/check-ins",
        data={"plate": "ZZZ999"},
        headers=operator_headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Vehicle not registered: category_id is required"
    )
    assert await _vehicles_by_plate(client, operator_headers, "ZZZ999") == []


async def test_check_in_new_plate_unknown_category_is_not_found(
    client, session_factory, tmp_path
):
    operator_headers = await _operator_headers(client, session_factory)
    _use_tmp_storage(tmp_path)

    response = await client.post(
        "/api/check-ins",
        data={"plate": "ZZZ999", "category_id": "9999"},
        headers=operator_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Category not found"
    assert await _vehicles_by_plate(client, operator_headers, "ZZZ999") == []


async def test_check_in_new_plate_is_normalized_without_duplicates(
    client, session_factory, tmp_path
):
    admin_headers = await _admin_headers(client, session_factory)
    category_id = await _create_category(client, admin_headers)
    operator_headers = await _operator_headers(client, session_factory)
    _use_tmp_storage(tmp_path)

    first = await client.post(
        "/api/check-ins",
        data={"plate": " abc 123 ", "category_id": str(category_id)},
        headers=operator_headers,
    )
    second = await client.post(
        "/api/check-ins",
        data={"plate": "ABC123", "category_id": str(category_id)},
        headers=operator_headers,
    )

    assert first.status_code == 201
    assert second.status_code == 409
    all_vehicles = (await client.get("/api/vehicles", headers=operator_headers)).json()
    assert [v["plate"] for v in all_vehicles] == ["ABC123"]


async def test_check_in_blank_plate_is_unprocessable(
    client, session_factory, tmp_path
):
    operator_headers = await _operator_headers(client, session_factory)
    _use_tmp_storage(tmp_path)

    response = await client.post(
        "/api/check-ins",
        data={"plate": "   ", "category_id": "1"},
        headers=operator_headers,
    )

    assert response.status_code == 422


async def test_duplicate_open_session_is_conflict(client, session_factory, tmp_path):
    admin_headers = await _admin_headers(client, session_factory)
    await _create_vehicle(client, admin_headers, plate="DUP123")
    operator_headers = await _operator_headers(client, session_factory)
    _use_tmp_storage(tmp_path)
    await client.post(
        "/api/check-ins", data={"plate": "DUP123"}, headers=operator_headers
    )

    response = await client.post(
        "/api/check-ins", data={"plate": "DUP123"}, headers=operator_headers
    )

    assert response.status_code == 409


async def test_unauthenticated_check_in_is_rejected(client, tmp_path):
    _use_tmp_storage(tmp_path)

    response = await client.post(
        "/api/check-ins", data={"plate": "ABC123", "category_id": "1"}
    )

    assert response.status_code == 401


async def test_list_open_sessions(client, session_factory, tmp_path):
    admin_headers = await _admin_headers(client, session_factory)
    await _create_vehicle(client, admin_headers, plate="LIST123")
    operator_headers = await _operator_headers(client, session_factory)
    _use_tmp_storage(tmp_path)
    await client.post(
        "/api/check-ins", data={"plate": "LIST123"}, headers=operator_headers
    )

    response = await client.get("/api/check-ins", headers=operator_headers)

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "open"
    assert response.json()[0]["plate"] == "LIST123"
    assert response.json()[0]["photo_count"] == 0


# --- B-UP: evidence upload hardening --------------------------------------


def _stored_files(tmp_path):
    return sorted(os.listdir(tmp_path))


async def _registered_operator(client, session_factory, plate):
    admin_headers = await _admin_headers(client, session_factory)
    await _create_vehicle(client, admin_headers, plate=plate)
    return await _operator_headers(client, session_factory)


async def test_png_named_jpg_is_stored_with_detected_extension(
    client, session_factory, tmp_path
):
    headers = await _registered_operator(client, session_factory, "PNG001")
    _use_tmp_storage(tmp_path)

    response = await client.post(
        "/api/check-ins",
        data={"plate": "PNG001"},
        files=[("photos", ("photo.jpg", PNG, "image/jpeg"))],
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["photos"][0]["file_path"].endswith(".png")


async def test_svg_renamed_to_jpg_is_rejected_without_side_effects(
    client, session_factory, tmp_path
):
    """Security: content type is sniffed, client name/MIME are ignored."""
    headers = await _registered_operator(client, session_factory, "SVG001")
    _use_tmp_storage(tmp_path)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>x()</script></svg>'

    response = await client.post(
        "/api/check-ins",
        data={"plate": "SVG001"},
        files=[("photos", ("evil.jpg", svg, "image/jpeg"))],
        headers=headers,
    )

    assert response.status_code == 422
    assert "JPEG or PNG" in response.json()["detail"]
    assert _stored_files(tmp_path) == []
    assert (await client.get("/api/check-ins", headers=headers)).json() == []


async def test_html_disguised_as_png_is_rejected(client, session_factory, tmp_path):
    headers = await _registered_operator(client, session_factory, "HTML01")
    _use_tmp_storage(tmp_path)

    response = await client.post(
        "/api/check-ins",
        data={"plate": "HTML01"},
        files=[("photos", ("x.png", b"<html><body>hi</body></html>", "image/png"))],
        headers=headers,
    )

    assert response.status_code == 422
    assert _stored_files(tmp_path) == []


async def test_photo_over_size_limit_is_413(client, session_factory, tmp_path):
    headers = await _registered_operator(client, session_factory, "BIG001")
    _use_tmp_storage(tmp_path)
    too_big = JPEG + b"\x00" * (5 * 1024 * 1024)

    response = await client.post(
        "/api/check-ins",
        data={"plate": "BIG001"},
        files=[("photos", ("big.jpg", too_big, "image/jpeg"))],
        headers=headers,
    )

    assert response.status_code == 413
    assert _stored_files(tmp_path) == []


async def test_more_than_five_photos_is_422(client, session_factory, tmp_path):
    headers = await _registered_operator(client, session_factory, "MANY01")
    _use_tmp_storage(tmp_path)
    files = [("photos", (f"p{i}.jpg", JPEG, "image/jpeg")) for i in range(6)]

    response = await client.post(
        "/api/check-ins", data={"plate": "MANY01"}, files=files, headers=headers
    )

    assert response.status_code == 422
    assert _stored_files(tmp_path) == []


async def test_five_photos_is_accepted(client, session_factory, tmp_path):
    headers = await _registered_operator(client, session_factory, "FIVE01")
    _use_tmp_storage(tmp_path)
    files = [("photos", (f"p{i}.jpg", JPEG, "image/jpeg")) for i in range(5)]

    response = await client.post(
        "/api/check-ins", data={"plate": "FIVE01"}, files=files, headers=headers
    )

    assert response.status_code == 201
    assert len(_stored_files(tmp_path)) == 5


async def test_no_orphan_files_after_duplicate_session_conflict(
    client, session_factory, tmp_path
):
    headers = await _registered_operator(client, session_factory, "ORPH01")
    _use_tmp_storage(tmp_path)
    photo = [("photos", ("a.jpg", JPEG, "image/jpeg"))]
    await client.post(
        "/api/check-ins", data={"plate": "ORPH01"}, files=photo, headers=headers
    )

    response = await client.post(
        "/api/check-ins", data={"plate": "ORPH01"}, files=photo, headers=headers
    )

    assert response.status_code == 409
    assert len(_stored_files(tmp_path)) == 1


async def test_no_orphan_files_after_unregistered_vehicle_422(
    client, session_factory, tmp_path
):
    headers = await _operator_headers(client, session_factory)
    _use_tmp_storage(tmp_path)

    response = await client.post(
        "/api/check-ins",
        data={"plate": "NOCAT1"},
        files=[("photos", ("a.jpg", JPEG, "image/jpeg"))],
        headers=headers,
    )

    assert response.status_code == 422
    assert _stored_files(tmp_path) == []


# --- B-FORM: form field limits --------------------------------------------


async def test_plate_of_twenty_chars_is_accepted(client, session_factory, tmp_path):
    admin_headers = await _admin_headers(client, session_factory)
    category_id = await _create_category(client, admin_headers)
    headers = await _operator_headers(client, session_factory)
    _use_tmp_storage(tmp_path)

    response = await client.post(
        "/api/check-ins",
        data={"plate": "P" * 20, "category_id": str(category_id)},
        headers=headers,
    )

    assert response.status_code == 201


async def test_overlong_form_fields_are_422(client, session_factory, tmp_path):
    headers = await _operator_headers(client, session_factory)
    _use_tmp_storage(tmp_path)
    cases = [
        {"plate": "P" * 21, "category_id": "1"},
        {"plate": "OK1", "category_id": "1", "color": "c" * 31},
        {"plate": "OK1", "category_id": "1", "brand": "b" * 51},
    ]

    for data in cases:
        response = await client.post("/api/check-ins", data=data, headers=headers)
        assert response.status_code == 422, data


# --- S7: created_by audit --------------------------------------------------


async def test_auto_registered_vehicle_records_operator(
    client, session_factory, tmp_path
):
    from app.infrastructure.repositories.vehicle_repository import (
        SqlAlchemyVehicleRepository,
    )

    admin_headers = await _admin_headers(client, session_factory)
    category_id = await _create_category(client, admin_headers)
    headers = await _operator_headers(client, session_factory)
    _use_tmp_storage(tmp_path)

    await client.post(
        "/api/check-ins",
        data={"plate": "AUD001", "category_id": str(category_id)},
        headers=headers,
    )

    async with session_factory() as session:
        vehicle = await SqlAlchemyVehicleRepository(session).get_by_plate("AUD001")
        operator = await SqlAlchemyUserRepository(session).get_by_username("operator")
    assert vehicle.created_by == operator.id
