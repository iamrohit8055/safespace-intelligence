"""Tests for media upload, streaming, public map observations, and GeoJSON boundaries."""

import io
import uuid

from fastapi import status
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.iam import Role, User, UserRole
from app.models.reporting import ReportCategory


def _create_user(db: Session, role_name: str) -> tuple[User, str]:
    user = User(
        email=f"media_test_{role_name}_{uuid.uuid4().hex[:6]}@safespace.org",
        hashed_password=hash_password("ValidPassword123!"),
        full_name=f"Media {role_name.capitalize()}",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    role = db.execute(select(Role).where(Role.name == role_name)).scalar_one()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=user.id)
    return user, token


def _create_sample_jpeg() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _create_sample_png() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGBA", (120, 80), color="red")
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_get_categories_endpoint(auth_client: TestClient) -> None:
    """Verify active categories list returns standard taxonomy."""
    resp = auth_client.get("/api/v1/reports/categories")
    assert resp.status_code == status.HTTP_200_OK
    categories = resp.json()
    assert len(categories) >= 5
    codes = [c["code"] for c in categories]
    assert "STREET_LIGHTING" in codes
    assert "MAINTENANCE" in codes


def test_public_map_endpoint_privacy(auth_client: TestClient, db_session: Session) -> None:
    """Verify public map endpoint returns fuzzed coordinates and excludes reporter id."""
    citizen, citizen_token = _create_user(db_session, "citizen")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    # Submit a report
    create_payload = {
        "title": "Dark Street Intersection",
        "description": "Street lights completely out on 4th Avenue.",
        "category_id": lighting_cat.id,
        "latitude": 40.712776,
        "longitude": -74.005974,
        "address_text": "4th Ave & Main St",
    }
    submit_resp = auth_client.post(
        "/api/v1/reports",
        json=create_payload,
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert submit_resp.status_code == status.HTTP_201_CREATED

    # Query public map
    map_resp = auth_client.get("/api/v1/reports/public/map")
    assert map_resp.status_code == status.HTTP_200_OK
    items = map_resp.json()
    assert len(items) >= 1

    matched = next((item for item in items if item["title"] == "Dark Street Intersection"), None)
    assert matched is not None
    # Verify coordinate was rounded to 3 decimal places
    assert matched["latitude"] == round(40.712776, 3)
    assert matched["longitude"] == round(-74.005974, 3)
    # Verify reporter identity is NOT in response
    assert "reporter_id" not in matched
    assert matched["category_code"] == "STREET_LIGHTING"


def test_media_upload_and_download(auth_client: TestClient, db_session: Session) -> None:
    """Verify uploading, metadata storage, and downloading of photographic evidence."""
    citizen, citizen_token = _create_user(db_session, "citizen")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    # 1. Create report
    submit_resp = auth_client.post(
        "/api/v1/reports",
        json={
            "title": "Broken Street Lamp Post",
            "description": "Exposed wires and cracked glass fixture.",
            "category_id": lighting_cat.id,
            "latitude": 40.713,
            "longitude": -74.006,
        },
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert submit_resp.status_code == status.HTTP_201_CREATED
    report_id = submit_resp.json()["id"]

    # 2. Upload JPEG
    jpeg_bytes = _create_sample_jpeg()
    upload_resp = auth_client.post(
        f"/api/v1/reports/{report_id}/media",
        files={"file": ("photo.jpg", jpeg_bytes, "image/jpeg")},
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert upload_resp.status_code == status.HTTP_201_CREATED
    media_data = upload_resp.json()
    assert media_data["report_id"] == report_id
    assert media_data["mime_type"] == "image/jpeg"
    assert media_data["width"] == 100
    assert media_data["height"] == 100
    media_id = media_data["id"]

    # 3. Duplicate upload should be rejected with 409
    dup_resp = auth_client.post(
        f"/api/v1/reports/{report_id}/media",
        files={"file": ("photo_dup.jpg", jpeg_bytes, "image/jpeg")},
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert dup_resp.status_code == status.HTTP_409_CONFLICT

    # 4. Download media file
    dl_resp = auth_client.get(
        f"/api/v1/reports/{report_id}/media/{media_id}",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert dl_resp.status_code == status.HTTP_200_OK
    assert dl_resp.headers["content-type"] == "image/jpeg"
    assert len(dl_resp.content) > 0


def test_media_upload_invalid_type_rejected(auth_client: TestClient, db_session: Session) -> None:
    """Verify non-image formats are rejected with 400 Bad Request."""
    citizen, citizen_token = _create_user(db_session, "citizen")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    submit_resp = auth_client.post(
        "/api/v1/reports",
        json={
            "title": "Valid Report for Media Reject",
            "description": "Testing media rejection.",
            "category_id": lighting_cat.id,
            "latitude": 40.713,
            "longitude": -74.006,
        },
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    report_id = submit_resp.json()["id"]

    upload_resp = auth_client.post(
        f"/api/v1/reports/{report_id}/media",
        files={"file": ("doc.pdf", b"%PDF-1.4 dummy content", "application/pdf")},
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert upload_resp.status_code == status.HTTP_400_BAD_REQUEST


def test_admin_areas_geojson_endpoint(auth_client: TestClient, db_session: Session) -> None:
    """Verify admin GeoJSON endpoint requires staff role and returns FeatureCollection."""
    _, admin_token = _create_user(db_session, "admin")
    _, citizen_token = _create_user(db_session, "citizen")

    url = "/api/v1/admin/intelligence/areas/geojson"

    # Citizen -> 403
    cit_resp = auth_client.get(url, headers={"Authorization": f"Bearer {citizen_token}"})
    assert cit_resp.status_code == status.HTTP_403_FORBIDDEN

    # Admin -> 200
    adm_resp = auth_client.get(url, headers={"Authorization": f"Bearer {admin_token}"})
    assert adm_resp.status_code == status.HTTP_200_OK
    data = adm_resp.json()
    assert data["type"] == "FeatureCollection"
    assert isinstance(data["features"], list)
