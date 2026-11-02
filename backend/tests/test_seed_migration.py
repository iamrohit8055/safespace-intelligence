"""Tests for baseline seed data migration (roles and report categories)."""

import uuid
from datetime import UTC, datetime

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.iam import Role, User, UserRole
from app.models.reporting import Report, ReportCategory

EXPECTED_ROLES = {"citizen", "verifier", "maintenance", "admin"}
EXPECTED_CATEGORIES = {
    "STREET_LIGHTING",
    "PEDESTRIAN_PATHWAYS",
    "VISIBILITY",
    "PUBLIC_ASSISTANCE",
    "MAINTENANCE",
}


def test_all_four_standard_roles_exist(db_session: Session) -> None:
    """Verify that all four approved standard roles exist in the database."""
    roles = db_session.execute(select(Role)).scalars().all()
    role_names = {r.name for r in roles}
    assert EXPECTED_ROLES.issubset(role_names), f"Missing roles: {EXPECTED_ROLES - role_names}"

    for role in roles:
        if role.name in EXPECTED_ROLES:
            assert isinstance(role.id, int)
            assert 1 <= role.id <= 32767, f"Role ID {role.id} outside SMALLINT range"
            assert role.description is not None and len(role.description) > 0


def test_all_five_baseline_categories_exist(db_session: Session) -> None:
    """Verify that all five approved baseline deficiency categories exist in the database."""
    categories = db_session.execute(select(ReportCategory)).scalars().all()
    category_codes = {c.code for c in categories}
    assert EXPECTED_CATEGORIES.issubset(category_codes), (
        f"Missing categories: {EXPECTED_CATEGORIES - category_codes}"
    )

    for cat in categories:
        if cat.code in EXPECTED_CATEGORIES:
            assert isinstance(cat.id, int)
            assert 1 <= cat.id <= 32767, f"Category ID {cat.id} outside SMALLINT range"
            assert cat.name is not None and len(cat.name) > 0
            assert cat.description is not None and len(cat.description) > 0
            assert cat.is_active is True


def test_seed_records_prevent_duplicate_insertion(db_session: Session) -> None:
    """Verify that inserting duplicate role names or category codes violates unique constraints."""
    duplicate_role = Role(name="citizen", description="Duplicate role test")
    db_session.add(duplicate_role)
    with pytest.raises(IntegrityError) as exc_role:
        db_session.flush()
    assert "roles_name_key" in str(exc_role.value).lower()
    db_session.rollback()

    duplicate_cat = ReportCategory(
        code="STREET_LIGHTING",
        name="Duplicate Lighting",
        description="Duplicate category test",
    )
    db_session.add(duplicate_cat)
    with pytest.raises(IntegrityError) as exc_cat:
        db_session.flush()
    assert "report_categories_code_key" in str(exc_cat.value).lower()
    db_session.rollback()


def test_seeded_roles_and_categories_integrate_with_foreign_keys(
    db_session: Session,
) -> None:
    """Verify foreign key relationships function correctly with seeded roles and categories."""
    user = User(
        email=f"tester_{uuid.uuid4().hex[:8]}@safespace.org",
        hashed_password="argon2id_hash_placeholder",
        full_name="Seed Integration Tester",
    )
    db_session.add(user)
    db_session.flush()

    citizen_role = db_session.execute(select(Role).where(Role.name == "citizen")).scalar_one()
    user_role = UserRole(user_id=user.id, role_id=citizen_role.id)
    db_session.add(user_role)
    db_session.flush()

    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    report = Report(
        reporter_id=user.id,
        category_id=lighting_cat.id,
        title="Dark Alleyway",
        description="Street luminaire is completely out",
        location=WKTElement("SRID=4326;POINT(-73.9857 40.7484)"),
        status="SUBMITTED",
        observed_at=datetime.now(UTC),
    )
    db_session.add(report)
    db_session.flush()

    assert report.id is not None
    assert report.category.code == "STREET_LIGHTING"
    assert citizen_role in user.roles


def test_downgrade_respects_foreign_keys_and_fails_safely_on_dependent_records(
    db_session: Session,
) -> None:
    """Verify downgrade delete queries fail safely with RESTRICT when dependent rows exist."""
    user = User(
        email=f"tester_{uuid.uuid4().hex[:8]}@safespace.org",
        hashed_password="argon2id_hash_placeholder",
        full_name="Dependency Tester",
    )
    db_session.add(user)
    db_session.flush()

    verifier_role = db_session.execute(select(Role).where(Role.name == "verifier")).scalar_one()
    user_role = UserRole(user_id=user.id, role_id=verifier_role.id)
    db_session.add(user_role)
    db_session.flush()

    visibility_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "VISIBILITY")
    ).scalar_one()

    report = Report(
        reporter_id=user.id,
        category_id=visibility_cat.id,
        title="Overgrown Tree",
        description="Blind corner",
        location=WKTElement("SRID=4326;POINT(-73.9857 40.7484)"),
        status="SUBMITTED",
        observed_at=datetime.now(UTC),
    )
    db_session.add(report)
    db_session.flush()

    # Attempting to execute the migration downgrade delete must fail due to ON DELETE RESTRICT
    with pytest.raises(IntegrityError) as exc_cat:
        db_session.execute(text("DELETE FROM report_categories WHERE code = 'VISIBILITY';"))
        db_session.flush()
    assert "reports_category_id_fkey" in str(exc_cat.value).lower()
    db_session.rollback()

    # Attempting to execute migration downgrade delete for role must fail due to ON DELETE RESTRICT
    # Re-insert user and user_role after rollback
    user = User(
        email=f"tester_{uuid.uuid4().hex[:8]}@safespace.org",
        hashed_password="argon2id_hash_placeholder",
        full_name="Dependency Tester",
    )
    db_session.add(user)
    db_session.flush()

    verifier_role = db_session.execute(select(Role).where(Role.name == "verifier")).scalar_one()
    user_role = UserRole(user_id=user.id, role_id=verifier_role.id)
    db_session.add(user_role)
    db_session.flush()

    with pytest.raises(IntegrityError) as exc_role:
        db_session.execute(text("DELETE FROM roles WHERE name = 'verifier';"))
        db_session.flush()
    assert "user_roles_role_id_fkey" in str(exc_role.value).lower()
    db_session.rollback()
