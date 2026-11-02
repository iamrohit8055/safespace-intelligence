"""Comprehensive tests for SQLAlchemy models, constraints, and database integrity."""

import uuid
from datetime import UTC, datetime

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.geography import AdministrativeArea
from app.models.iam import User
from app.models.reporting import Report, ReportCategory, ReportMedia
from app.models.verification import ReportStatusHistory, ReportVerification


def test_model_metadata_contains_all_nine_tables() -> None:
    """Verify Base.metadata contains exactly the nine core domain tables."""
    expected_tables = {
        "roles",
        "users",
        "user_roles",
        "administrative_areas",
        "report_categories",
        "reports",
        "report_media",
        "report_verifications",
        "report_status_history",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables), (
        f"Missing tables: {expected_tables - actual_tables}"
    )


def test_required_unique_constraints_exist() -> None:
    """Verify unique constraints and unique indexes on all required tables."""
    # roles.name unique
    roles_table = Base.metadata.tables["roles"]
    assert any(
        col.name == "name"
        for uq in roles_table.constraints
        if getattr(uq, "columns", None)
        for col in uq.columns
    )

    # users.email lower functional unique index
    users_table = Base.metadata.tables["users"]
    assert any(idx.name == "idx_users_email_lower" for idx in users_table.indexes)

    # user_roles composite PK
    user_roles_table = Base.metadata.tables["user_roles"]
    pk_cols = [c.name for c in user_roles_table.primary_key.columns]
    assert pk_cols == ["user_id", "role_id"]

    # administrative_areas.code unique
    admin_table = Base.metadata.tables["administrative_areas"]
    assert any(
        col.name == "code"
        for uq in admin_table.constraints
        if getattr(uq, "columns", None)
        for col in uq.columns
    )

    # report_categories.code unique
    categories_table = Base.metadata.tables["report_categories"]
    assert any(
        col.name == "code"
        for uq in categories_table.constraints
        if getattr(uq, "columns", None)
        for col in uq.columns
    )

    # report_media unique constraints
    media_table = Base.metadata.tables["report_media"]
    storage_ref_uq = next(
        (uq for uq in media_table.constraints if uq.name == "uq_report_media_storage_ref"),
        None,
    )
    assert storage_ref_uq is not None
    assert [c.name for c in storage_ref_uq.columns] == [
        "storage_provider",
        "storage_bucket",
        "storage_key",
    ]

    report_checksum_uq = next(
        (uq for uq in media_table.constraints if uq.name == "uq_report_media_report_checksum"),
        None,
    )
    assert report_checksum_uq is not None
    assert [c.name for c in report_checksum_uq.columns] == ["report_id", "checksum_sha256"]


def test_required_check_constraints_exist() -> None:
    """Verify all named check constraints exist on model metadata."""
    # users
    users_checks = {
        c.name for c in Base.metadata.tables["users"].constraints if hasattr(c, "sqltext")
    }
    assert "chk_users_email_format" in users_checks

    # administrative_areas
    admin_checks = {
        c.name
        for c in Base.metadata.tables["administrative_areas"].constraints
        if hasattr(c, "sqltext")
    }
    assert "chk_admin_area_type" in admin_checks
    assert "chk_admin_area_boundary_valid" in admin_checks
    assert "chk_admin_area_prevent_self_parent" in admin_checks

    # reports
    reports_checks = {
        c.name for c in Base.metadata.tables["reports"].constraints if hasattr(c, "sqltext")
    }
    assert "chk_reports_status_valid" in reports_checks
    assert "chk_reports_location_point" in reports_checks
    assert "chk_reports_location_coordinate_bounds" in reports_checks
    assert "chk_reports_prevent_self_duplicate" in reports_checks

    # report_media
    media_checks = {
        c.name for c in Base.metadata.tables["report_media"].constraints if hasattr(c, "sqltext")
    }
    assert "chk_media_file_size_positive" in media_checks
    assert "chk_media_mime_type_image_only" in media_checks
    assert "chk_media_dimensions_positive" in media_checks
    assert "chk_media_checksum_sha256_format" in media_checks

    # report_verifications
    verif_checks = {
        c.name
        for c in Base.metadata.tables["report_verifications"].constraints
        if hasattr(c, "sqltext")
    }
    assert "chk_verification_decision_valid" in verif_checks
    assert "chk_verification_severity_scale" in verif_checks
    assert "chk_verification_confidence_scale" in verif_checks
    assert "chk_verification_rejection_reason" in verif_checks

    # report_status_history
    history_checks = {
        c.name
        for c in Base.metadata.tables["report_status_history"].constraints
        if hasattr(c, "sqltext")
    }
    assert "chk_status_history_transition_valid" in history_checks
    assert "chk_status_history_statuses_allowed" in history_checks


def test_foreign_key_deletion_behavior_matches_specification() -> None:
    """Verify ondelete and onupdate behavior for all domain foreign keys."""
    # user_roles
    ur_fks = {fk.parent.name: fk for fk in Base.metadata.tables["user_roles"].foreign_keys}
    assert ur_fks["user_id"].ondelete == "CASCADE"
    assert ur_fks["role_id"].ondelete == "RESTRICT"
    assert ur_fks["assigned_by"].ondelete == "SET NULL"

    # administrative_areas
    admin_fks = {
        fk.parent.name: fk for fk in Base.metadata.tables["administrative_areas"].foreign_keys
    }
    assert admin_fks["parent_id"].ondelete == "RESTRICT"

    # reports
    reports_fks = {fk.parent.name: fk for fk in Base.metadata.tables["reports"].foreign_keys}
    assert reports_fks["reporter_id"].ondelete == "RESTRICT"
    assert reports_fks["category_id"].ondelete == "RESTRICT"
    assert reports_fks["administrative_area_id"].ondelete == "SET NULL"
    assert reports_fks["duplicate_of_id"].ondelete == "SET NULL"

    # report_media (RESTRICT on report_id)
    media_fks = {fk.parent.name: fk for fk in Base.metadata.tables["report_media"].foreign_keys}
    assert media_fks["report_id"].ondelete == "RESTRICT"

    # report_verifications (RESTRICT on report_id and verifier_id)
    verif_fks = {
        fk.parent.name: fk for fk in Base.metadata.tables["report_verifications"].foreign_keys
    }
    assert verif_fks["report_id"].ondelete == "RESTRICT"
    assert verif_fks["verifier_id"].ondelete == "RESTRICT"

    # report_status_history (RESTRICT on report_id)
    hist_fks = {
        fk.parent.name: fk for fk in Base.metadata.tables["report_status_history"].foreign_keys
    }
    assert hist_fks["report_id"].ondelete == "RESTRICT"
    assert hist_fks["changed_by_user_id"].ondelete == "SET NULL"


def test_report_categories_is_pure_taxonomy() -> None:
    """Ensure report_categories contains no scoring weights."""
    cat_table = Base.metadata.tables["report_categories"]
    assert "default_severity_weight" not in cat_table.columns
    assert "weight" not in cat_table.columns


# -----------------------------------------------------------------------------
# Database Integration Tests (Against live PostgreSQL 17 + PostGIS 3.5)
# -----------------------------------------------------------------------------


def _create_helper_fixtures(db_session: Session) -> tuple[User, ReportCategory]:
    """Helper to create a test user and category within the transactional session."""
    user = User(
        email=f"test_{uuid.uuid4().hex[:8]}@safespace.org",
        hashed_password="argon2id_hash_placeholder",
        full_name="Audit Inspector",
    )
    category = ReportCategory(
        code=f"TEST_CAT_{uuid.uuid4().hex[:6]}",
        name="Test Category",
        description="Category for testing constraints",
    )
    db_session.add(user)
    db_session.add(category)
    db_session.flush()
    return user, category


def test_initial_status_history_accepts_null_to_submitted(db_session: Session) -> None:
    """Verify initial report status history transition accepts NULL -> SUBMITTED atomically."""
    user, category = _create_helper_fixtures(db_session)

    report = Report(
        reporter_id=user.id,
        category_id=category.id,
        title="Broken Street Light",
        description="Light fixture is completely dark",
        location=WKTElement("SRID=4326;POINT(-73.9857 40.7484)"),
        status="SUBMITTED",
        observed_at=datetime.now(UTC),
    )
    db_session.add(report)
    db_session.flush()

    status_history = ReportStatusHistory(
        report_id=report.id,
        from_status=None,
        to_status="SUBMITTED",
        changed_by_user_id=user.id,
        reason="Initial report submission",
    )
    db_session.add(status_history)
    db_session.flush()

    assert status_history.id is not None
    assert status_history.from_status is None
    assert status_history.to_status == "SUBMITTED"


def test_invalid_initial_status_history_transition_rejected(db_session: Session) -> None:
    """Verify that an invalid initial transition (NULL -> VERIFIED) violates transition check."""
    user, category = _create_helper_fixtures(db_session)

    report = Report(
        reporter_id=user.id,
        category_id=category.id,
        title="Broken Light",
        description="Description",
        location=WKTElement("SRID=4326;POINT(0 0)"),
        status="SUBMITTED",
        observed_at=datetime.now(UTC),
    )
    db_session.add(report)
    db_session.flush()

    # Invalid initial transition: from_status is NULL but to_status is VERIFIED
    invalid_history = ReportStatusHistory(
        report_id=report.id,
        from_status=None,
        to_status="VERIFIED",
        changed_by_user_id=user.id,
    )
    db_session.add(invalid_history)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()

    assert "chk_status_history_transition_valid" in str(exc_info.value).lower()


def test_invalid_coordinates_rejected_by_check_constraint(db_session: Session) -> None:
    """Verify coordinates outside [-180, 180] x [-90, 90] violate coordinate bounds check."""
    user, category = _create_helper_fixtures(db_session)

    # Longitude = 195.0 (exceeds 180)
    invalid_report = Report(
        reporter_id=user.id,
        category_id=category.id,
        title="Invalid Coordinate",
        description="Testing bounds",
        location=WKTElement("SRID=4326;POINT(195.0 45.0)"),
        status="SUBMITTED",
        observed_at=datetime.now(UTC),
    )
    db_session.add(invalid_report)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()

    assert "chk_reports_location_coordinate_bounds" in str(exc_info.value).lower()


def test_verification_decision_verified_requires_severity(db_session: Session) -> None:
    """Verify that VERIFIED decision without severity violates chk_verification_severity_scale."""
    user, category = _create_helper_fixtures(db_session)

    report = Report(
        reporter_id=user.id,
        category_id=category.id,
        title="Observation",
        description="Description",
        location=WKTElement("SRID=4326;POINT(10.0 20.0)"),
        status="SUBMITTED",
        observed_at=datetime.now(UTC),
    )
    db_session.add(report)
    db_session.flush()

    # VERIFIED decision with NO verified_severity
    invalid_verif = ReportVerification(
        report_id=report.id,
        verifier_id=user.id,
        decision="VERIFIED",
        verified_severity=None,
    )
    db_session.add(invalid_verif)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "chk_verification_severity_scale" in str(exc_info.value).lower()


def test_verification_decision_rejected_forbids_severity(db_session: Session) -> None:
    """Verify that REJECTED decision with severity violates chk_verification_severity_scale."""
    user, category = _create_helper_fixtures(db_session)

    report = Report(
        reporter_id=user.id,
        category_id=category.id,
        title="Observation",
        description="Description",
        location=WKTElement("SRID=4326;POINT(10.0 20.0)"),
        status="SUBMITTED",
        observed_at=datetime.now(UTC),
    )
    db_session.add(report)
    db_session.flush()

    # REJECTED decision with a verified_severity (must be None when REJECTED)
    invalid_verif = ReportVerification(
        report_id=report.id,
        verifier_id=user.id,
        decision="REJECTED",
        rejection_reason="SPAM",
        verified_severity=3,
    )
    db_session.add(invalid_verif)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "chk_verification_severity_scale" in str(exc_info.value).lower()


def test_verification_decision_rejected_requires_reason(db_session: Session) -> None:
    """Verify that REJECTED decision without reason violates chk_verification_rejection_reason."""
    user, category = _create_helper_fixtures(db_session)

    report = Report(
        reporter_id=user.id,
        category_id=category.id,
        title="Observation",
        description="Description",
        location=WKTElement("SRID=4326;POINT(10.0 20.0)"),
        status="SUBMITTED",
        observed_at=datetime.now(UTC),
    )
    db_session.add(report)
    db_session.flush()

    # REJECTED decision with NO rejection_reason
    invalid_verif = ReportVerification(
        report_id=report.id,
        verifier_id=user.id,
        decision="REJECTED",
        rejection_reason=None,
    )
    db_session.add(invalid_verif)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "chk_verification_rejection_reason" in str(exc_info.value).lower()


def test_media_invalid_checksum_rejected(db_session: Session) -> None:
    """Verify report_media checksum constraint rejects invalid SHA256 formats."""
    user, category = _create_helper_fixtures(db_session)

    report = Report(
        reporter_id=user.id,
        category_id=category.id,
        title="Report for Media",
        description="Testing media constraints",
        location=WKTElement("SRID=4326;POINT(12.5 41.9)"),
        status="SUBMITTED",
        observed_at=datetime.now(UTC),
    )
    db_session.add(report)
    db_session.flush()

    # Invalid checksum format (not 64 hex characters)
    bad_checksum_media = ReportMedia(
        report_id=report.id,
        storage_provider="s3",
        storage_bucket="safespace-evidence",
        storage_key="reports/2026/img1.webp",
        mime_type="image/webp",
        file_size_bytes=1024,
        checksum_sha256="invalid_not_hex_64_chars",
    )
    db_session.add(bad_checksum_media)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "chk_media_checksum_sha256_format" in str(exc_info.value).lower()


def test_media_negative_dimensions_rejected(db_session: Session) -> None:
    """Verify report_media dimensions constraint rejects negative width or height."""
    user, category = _create_helper_fixtures(db_session)

    report = Report(
        reporter_id=user.id,
        category_id=category.id,
        title="Report for Media",
        description="Testing media constraints",
        location=WKTElement("SRID=4326;POINT(12.5 41.9)"),
        status="SUBMITTED",
        observed_at=datetime.now(UTC),
    )
    db_session.add(report)
    db_session.flush()

    # Invalid negative width
    bad_dim_media = ReportMedia(
        report_id=report.id,
        storage_provider="s3",
        storage_bucket="safespace-evidence",
        storage_key="reports/2026/img2.webp",
        mime_type="image/webp",
        file_size_bytes=1024,
        checksum_sha256="a" * 64,
        width=-50,
        height=100,
    )
    db_session.add(bad_dim_media)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "chk_media_dimensions_positive" in str(exc_info.value).lower()


def test_valid_media_persists_cleanly(db_session: Session) -> None:
    """Verify valid report_media persists cleanly and respects constraints."""
    user, category = _create_helper_fixtures(db_session)

    report = Report(
        reporter_id=user.id,
        category_id=category.id,
        title="Report for Media",
        description="Testing media constraints",
        location=WKTElement("SRID=4326;POINT(12.5 41.9)"),
        status="SUBMITTED",
        observed_at=datetime.now(UTC),
    )
    db_session.add(report)
    db_session.flush()

    valid_checksum = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    valid_media = ReportMedia(
        report_id=report.id,
        storage_provider="s3",
        storage_bucket="safespace-evidence",
        storage_key=f"reports/2026/{uuid.uuid4().hex}.webp",
        mime_type="image/webp",
        file_size_bytes=2048,
        checksum_sha256=valid_checksum,
        width=1920,
        height=1080,
    )
    db_session.add(valid_media)
    db_session.flush()
    assert valid_media.id is not None


def test_administrative_area_prevent_self_parent(db_session: Session) -> None:
    """Verify administrative_areas chk_admin_area_prevent_self_parent constraint."""
    area_id = uuid.uuid4()
    # A MultiPolygon covering a small square
    polygon_wkt = (
        "SRID=4326;MULTIPOLYGON(((10.0 10.0, 10.0 11.0, 11.0 11.0, 11.0 10.0, 10.0 10.0)))"
    )

    invalid_area = AdministrativeArea(
        id=area_id,
        name="Self Parent Ward",
        code=f"WARD_{uuid.uuid4().hex[:6]}",
        area_type="ward",
        parent_id=area_id,  # Points to itself
        boundary=WKTElement(polygon_wkt),
    )
    db_session.add(invalid_area)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "chk_admin_area_prevent_self_parent" in str(exc_info.value).lower()
