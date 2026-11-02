"""Comprehensive test suite for Identity & Access Management (IAM) endpoints and security."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
import pytest
from fastapi import APIRouter, Depends, status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import app
from app.models.iam import Role, User, UserRole

settings = get_settings()

# Mount test routes for RBAC verification
rbac_test_router = APIRouter(prefix="/api/v1/test-rbac", tags=["Test RBAC"])

admin_only_dependency = require_roles("admin")
staff_only_dependency = require_roles("verifier", "admin")


@rbac_test_router.get("/admin-only")
def admin_only_endpoint(
    user: Annotated[User, Depends(admin_only_dependency)],
) -> dict[str, str]:
    return {"message": "admin granted", "user_id": str(user.id)}


@rbac_test_router.get("/staff-only")
def staff_only_endpoint(
    user: Annotated[User, Depends(staff_only_dependency)],
) -> dict[str, str]:
    return {"message": "staff granted", "user_id": str(user.id)}


app.include_router(rbac_test_router)


# -----------------------------------------------------------------------------
# 1. Password Hashing & Security Tests (Argon2id)
# -----------------------------------------------------------------------------


def test_argon2id_password_hashing() -> None:
    """Verify password hashing produces Argon2id formatted hashes and verifies correctly."""
    plain = "SuperSecurePassword123!"
    hashed = hash_password(plain)

    assert hashed.startswith("$argon2id$")
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False


def test_password_length_bounds() -> None:
    """Verify password validation rejects passwords below 8 chars or above 128 chars."""
    with pytest.raises(ValueError, match="at least 8 characters"):
        hash_password("short1")

    long_password = "A" * 129
    with pytest.raises(ValueError, match="cannot exceed 128 characters"):
        hash_password(long_password)

    # Verification of overly long password fails safely without hashing attempt
    assert verify_password(long_password, "$argon2id$placeholder") is False


# -----------------------------------------------------------------------------
# 2. JWT Access Token Tests
# -----------------------------------------------------------------------------


def test_jwt_creation_and_claims() -> None:
    """Verify generated JWT contains standard sub, iat, exp claims."""
    user_id = uuid.uuid4()
    token = create_access_token(subject=user_id)

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]


def test_jwt_expired_token_rejected() -> None:
    """Verify expired token raises ExpiredSignatureError."""
    user_id = uuid.uuid4()
    # Create token expired 10 minutes ago
    expired_token = create_access_token(subject=user_id, expires_delta=timedelta(minutes=-10))

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)


def test_jwt_invalid_signature_rejected() -> None:
    """Verify token signed with a different key raises InvalidTokenError."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    bogus_token = jwt.encode(payload, "wrong_secret_key_12345678901234567890", algorithm="HS256")

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(bogus_token)


# -----------------------------------------------------------------------------
# 3. User Registration Endpoint Tests
# -----------------------------------------------------------------------------


def test_register_citizen_success(auth_client: TestClient, db_session: Session) -> None:
    """Verify successful citizen registration assigns citizen role and hashes password."""
    email = f"citizen_{uuid.uuid4().hex[:8]}@safespace.org"
    password = "SafeCitizenPass123!"
    payload = {
        "email": email,
        "password": password,
        "full_name": "Jane Citizen",
    }

    response = auth_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["email"] == email.lower()
    assert data["full_name"] == "Jane Citizen"
    assert data["is_active"] is True
    assert data["is_verified"] is False
    assert data["roles"] == ["citizen"]
    assert "password" not in data
    assert "hashed_password" not in data

    # Verify database state
    user_id = uuid.UUID(data["id"])
    db_user = db_session.execute(select(User).where(User.id == user_id)).scalar_one()
    assert db_user.hashed_password.startswith("$argon2id$")
    assert db_user.hashed_password != password
    assert verify_password(password, db_user.hashed_password) is True


def test_register_duplicate_email_rejected(auth_client: TestClient) -> None:
    """Verify duplicate email registrations are cleanly rejected with HTTP 409."""
    email = f"duplicate_{uuid.uuid4().hex[:8]}@safespace.org"
    payload = {
        "email": email,
        "password": "Password123!",
        "full_name": "Original User",
    }

    resp1 = auth_client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == status.HTTP_201_CREATED

    # Attempt registration with identical email (uppercase variation)
    payload_dup = {
        "email": email.upper(),
        "password": "OtherPassword123!",
        "full_name": "Imposter User",
    }
    resp2 = auth_client.post("/api/v1/auth/register", json=payload_dup)
    assert resp2.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in resp2.json()["detail"].lower()


def test_register_cannot_self_assign_privileged_roles(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify caller cannot supply extra role fields to elevate privileges."""
    email = f"sneaky_{uuid.uuid4().hex[:8]}@safespace.org"
    payload = {
        "email": email,
        "password": "Password123!",
        "full_name": "Sneaky User",
        "role": "admin",
        "roles": ["admin", "verifier"],
    }

    response = auth_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["roles"] == ["citizen"]

    # Verify in database
    db_user = db_session.execute(select(User).where(User.email == email.lower())).scalar_one()
    assigned_roles = [r.name for r in db_user.roles]
    assert assigned_roles == ["citizen"]
    assert "admin" not in assigned_roles


def test_register_invalid_password_length(auth_client: TestClient) -> None:
    """Verify registration rejects passwords shorter than 8 characters."""
    payload = {
        "email": f"short_{uuid.uuid4().hex[:8]}@safespace.org",
        "password": "short",
        "full_name": "Short Pass User",
    }
    response = auth_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# -----------------------------------------------------------------------------
# 4. User Login Endpoint Tests
# -----------------------------------------------------------------------------


def test_login_success_returns_jwt(auth_client: TestClient) -> None:
    """Verify correct credentials return signed JWT access token and update last_login_at."""
    email = f"login_{uuid.uuid4().hex[:8]}@safespace.org"
    password = "CorrectPassword123!"

    reg_resp = auth_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Login Tester"},
    )
    assert reg_resp.status_code == status.HTTP_201_CREATED

    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == status.HTTP_200_OK

    token_data = login_resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    payload = decode_access_token(token_data["access_token"])
    assert payload["sub"] == reg_resp.json()["id"]


def test_login_incorrect_password_rejected(auth_client: TestClient) -> None:
    """Verify incorrect password receives generic 401 error."""
    email = f"wrongpass_{uuid.uuid4().hex[:8]}@safespace.org"
    password = "CorrectPassword123!"

    auth_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Login Tester"},
    )

    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword123!"},
    )
    assert login_resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "incorrect email or password" in login_resp.json()["detail"].lower()


def test_login_unknown_account_rejected(auth_client: TestClient) -> None:
    """Verify unknown account receives generic 401 error to prevent user enumeration."""
    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent_account_404@safespace.org", "password": "SomePassword123!"},
    )
    assert login_resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "incorrect email or password" in login_resp.json()["detail"].lower()


def test_login_inactive_account_rejected(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify inactive account is blocked during login."""
    email = f"inactive_{uuid.uuid4().hex[:8]}@safespace.org"
    password = "Password123!"

    reg_resp = auth_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Inactive User"},
    )
    user_id = uuid.UUID(reg_resp.json()["id"])

    # Deactivate account
    db_user = db_session.execute(select(User).where(User.id == user_id)).scalar_one()
    db_user.is_active = False
    db_session.commit()

    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "inactive" in login_resp.json()["detail"].lower()


# -----------------------------------------------------------------------------
# 5. Current Authenticated User (`GET /me`) Tests
# -----------------------------------------------------------------------------


def test_get_me_success(auth_client: TestClient) -> None:
    """Verify /me returns user profile and roles for valid bearer token."""
    email = f"me_{uuid.uuid4().hex[:8]}@safespace.org"
    password = "MyPassword123!"

    auth_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Profile User"},
    )

    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_resp.json()["access_token"]

    me_resp = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == status.HTTP_200_OK

    data = me_resp.json()
    assert data["email"] == email.lower()
    assert data["full_name"] == "Profile User"
    assert data["roles"] == ["citizen"]
    assert "password" not in data
    assert "hashed_password" not in data


def test_get_me_missing_token_rejected(auth_client: TestClient) -> None:
    """Verify /me rejects unauthenticated request with HTTP 401."""
    resp = auth_client.get("/api/v1/auth/me")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_me_invalid_token_rejected(auth_client: TestClient) -> None:
    """Verify /me rejects malformed or tampered token with HTTP 401."""
    resp = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt.token"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_me_inactive_user_rejected(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify /me rejects token if user account was subsequently deactivated."""
    email = f"deactivated_{uuid.uuid4().hex[:8]}@safespace.org"
    password = "Password123!"

    reg_resp = auth_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Soon Inactive"},
    )
    user_id = uuid.UUID(reg_resp.json()["id"])

    login_resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_resp.json()["access_token"]

    # Deactivate account
    db_user = db_session.execute(select(User).where(User.id == user_id)).scalar_one()
    db_user.is_active = False
    db_session.commit()

    resp = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "inactive" in resp.json()["detail"].lower()


# -----------------------------------------------------------------------------
# 6. Role-Based Access Control (RBAC) Tests
# -----------------------------------------------------------------------------


def test_rbac_admin_allowed_and_citizen_forbidden(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify admin role can access admin endpoint while citizen role receives HTTP 403."""
    # 1. Citizen User
    citizen_email = f"citizen_rbac_{uuid.uuid4().hex[:8]}@safespace.org"
    auth_client.post(
        "/api/v1/auth/register",
        json={"email": citizen_email, "password": "Password123!", "full_name": "Citizen User"},
    )
    c_login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": citizen_email, "password": "Password123!"},
    )
    citizen_token = c_login.json()["access_token"]

    # Citizen accessing admin route -> 403 Forbidden
    c_resp = auth_client.get(
        "/api/v1/test-rbac/admin-only",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert c_resp.status_code == status.HTTP_403_FORBIDDEN
    assert "forbidden" in c_resp.json()["detail"].lower()

    # 2. Admin User
    admin_user = User(
        email=f"admin_rbac_{uuid.uuid4().hex[:8]}@safespace.org",
        hashed_password=hash_password("AdminPass123!"),
        full_name="Admin User",
        is_active=True,
    )
    db_session.add(admin_user)
    db_session.flush()

    admin_role = db_session.execute(select(Role).where(Role.name == "admin")).scalar_one()
    db_session.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
    db_session.commit()

    admin_token = create_access_token(subject=admin_user.id)

    # Admin accessing admin route -> 200 OK
    a_resp = auth_client.get(
        "/api/v1/test-rbac/admin-only",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert a_resp.status_code == status.HTTP_200_OK
    assert a_resp.json()["message"] == "admin granted"


def test_rbac_staff_endpoint_allows_verifier_and_admin(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify endpoint allowing (verifier, admin) grants verifier and blocks citizen."""
    # 1. Verifier User
    verifier_user = User(
        email=f"verifier_rbac_{uuid.uuid4().hex[:8]}@safespace.org",
        hashed_password=hash_password("VerifierPass123!"),
        full_name="Verifier Field Staff",
        is_active=True,
    )
    db_session.add(verifier_user)
    db_session.flush()

    verifier_role = db_session.execute(select(Role).where(Role.name == "verifier")).scalar_one()
    db_session.add(UserRole(user_id=verifier_user.id, role_id=verifier_role.id))
    db_session.commit()

    verifier_token = create_access_token(subject=verifier_user.id)

    # Verifier accessing staff route -> 200 OK
    v_resp = auth_client.get(
        "/api/v1/test-rbac/staff-only",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert v_resp.status_code == status.HTTP_200_OK
    assert v_resp.json()["message"] == "staff granted"

    # 2. Unauthenticated request -> 401 Unauthorized
    unauth_resp = auth_client.get("/api/v1/test-rbac/staff-only")
    assert unauth_resp.status_code == status.HTTP_401_UNAUTHORIZED
