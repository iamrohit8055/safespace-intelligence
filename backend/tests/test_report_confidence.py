"""Tests for Step 8C: Individual Report Evidence Confidence Assessment.

Covers:
1. Confidence formula calculation and dynamic weight re-normalization.
2. Missing/deferred factors are not treated as zero (marked UNAVAILABLE).
3. Available weights sum to 1.0000 upon normalization.
4. Confidence score bounded between 0.0000 and 1.0000.
5. Zero measurable factors produces NULL rather than an invented zero.
6. Methodology version and factor breakdown preservation.
7. Evidence confidence never alters verified_severity or report status.
8. Append-only historical confidence preservation.
9. Unavailable evidence does not receive fabricated values.
10. Role-based access control (RBAC) and HTTP endpoints.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import status
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.intelligence.confidence import (
    calculate_report_confidence,
    get_report_confidence_history,
)
from app.models.confidence import (
    ConfidenceConfiguration,
    ConfidenceConfigurationFactor,
)
from app.models.iam import Role, User, UserRole
from app.models.reporting import Report, ReportCategory
from app.models.verification import ReportVerification


def _create_user_with_role(
    db_session: Session,
    role_name: str,
    email: str | None = None,
) -> tuple[User, str]:
    """Helper creating a user and returning (user, jwt_token)."""
    user_email = email or f"{role_name}_{uuid.uuid4().hex[:8]}@safespace.org"
    user = User(
        email=user_email,
        hashed_password=hash_password("SecurePassword123!"),
        full_name=f"Test {role_name.capitalize()} User",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    role = db_session.execute(select(Role).where(Role.name == role_name)).scalar_one()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    db_session.commit()

    token = create_access_token(subject=user.id)
    return user, token


def _create_report(
    db_session: Session,
    reporter: User,
    category: ReportCategory,
    status_val: str = "VERIFIED",
    verified_severity: int | None = 4,
    verifier: User | None = None,
    verification_notes: str | None = "Thoroughly inspected on site; high priority deficiency.",
    observed_at: datetime | None = None,
    submitted_at: datetime | None = None,
) -> Report:
    """Helper creating a report with optional verification."""
    sub_time = submitted_at or datetime.now(UTC)
    obs_time = observed_at or (sub_time - timedelta(hours=2))

    report = Report(
        reporter_id=reporter.id,
        category_id=category.id,
        title=f"Report in {category.code}",
        description="Physical deficiency observation description.",
        location=WKTElement("SRID=4326;POINT(-73.9857 40.7484)"),
        status=status_val,
        observed_at=obs_time,
        submitted_at=sub_time,
    )
    db_session.add(report)
    db_session.flush()

    if status_val == "VERIFIED" and verifier:
        v = ReportVerification(
            report_id=report.id,
            verifier_id=verifier.id,
            decision="VERIFIED",
            verified_severity=verified_severity,
            verification_notes=verification_notes,
        )
        db_session.add(v)

    db_session.commit()
    return report


def test_confidence_formula_and_normalization(db_session: Session) -> None:
    """Verify confidence formula correctly weights available factors and ignores missing ones."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    report = _create_report(
        db_session,
        reporter=citizen,
        category=lighting_cat,
        status_val="VERIFIED",
        verified_severity=4,
        verifier=verifier,
        verification_notes="Comprehensive physical inspection confirms luminaire failure",
    )

    conf = calculate_report_confidence(db_session, report.id)

    assert conf.confidence_score is not None
    assert Decimal("0.0000") <= conf.confidence_score <= Decimal("1.0000")
    assert conf.total_factors_count == 5
    assert conf.available_factors_count == 2
    assert conf.completeness_pct == Decimal("40.00")

    # Verify components
    components = {c.factor_code: c for c in conf.components}

    # VERIFICATION_COMPLETENESS: UNAVAILABLE
    # (note-length scoring removed; no structured rubric in schema)
    assert components["VERIFICATION_COMPLETENESS"].availability_state == "UNAVAILABLE"
    assert components["VERIFICATION_COMPLETENESS"].factor_score is None
    assert "Structured verification completeness criteria unavailable" in (
        components["VERIFICATION_COMPLETENESS"].unavailability_reason or ""
    )

    # EVIDENCE_FRESHNESS: observed (1.0000 because delta < 24h), assigned 0.2500
    assert components["EVIDENCE_FRESHNESS"].availability_state == "OBSERVED"
    assert components["EVIDENCE_FRESHNESS"].factor_score == Decimal("1.0000")

    # INDEPENDENT_CORROBORATION: observed (0.5000 because single report), assigned 0.2500
    assert components["INDEPENDENT_CORROBORATION"].availability_state == "OBSERVED"
    assert components["INDEPENDENT_CORROBORATION"].factor_score == Decimal("0.5000")

    # EVIDENCE_AVAILABILITY & QUALITY: UNAVAILABLE
    assert components["EVIDENCE_AVAILABILITY"].availability_state == "UNAVAILABLE"
    assert components["EVIDENCE_AVAILABILITY"].factor_score is None
    assert components["EVIDENCE_QUALITY"].availability_state == "UNAVAILABLE"
    assert components["EVIDENCE_QUALITY"].factor_score is None

    # Check sum of normalized weights over available factors: 0.5000 + 0.5000 = 1.0000
    norm_sum = (
        components["EVIDENCE_FRESHNESS"].normalized_weight
        + components["INDEPENDENT_CORROBORATION"].normalized_weight
    )
    assert norm_sum == Decimal("1.0000")

    # Expected: 1.00 * 0.5000 + 0.50 * 0.5000 = 0.5000 + 0.2500 = 0.7500
    expected_score = Decimal("1.0000") * Decimal("0.5000") + Decimal("0.5000") * Decimal("0.5000")
    assert abs(conf.confidence_score - expected_score) <= Decimal("0.0002")


def test_missing_factors_not_treated_as_zero(db_session: Session) -> None:
    """Verify unavailable factors are excluded from denominator rather than penalizing score."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    report = _create_report(
        db_session,
        reporter=citizen,
        category=lighting_cat,
        status_val="VERIFIED",
        verified_severity=4,
        verifier=verifier,
        verification_notes="Detailed inspector verification note exceeding fifteen chars",
    )

    conf = calculate_report_confidence(db_session, report.id)

    # If unavailable factors (0.30 + 0.10 + 0.10 = 0.50) were treated as 0
    # instead of re-normalizing, the unnormalized score would be 0.3750 instead of 0.7500.
    assert conf.confidence_score == Decimal("0.7500")
    assert conf.confidence_score > Decimal("0.3750")


def test_confidence_does_not_modify_verified_severity(db_session: Session) -> None:
    """Verify calculating confidence never modifies physical verified_severity or report status."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    report = _create_report(
        db_session,
        reporter=citizen,
        category=lighting_cat,
        status_val="VERIFIED",
        verified_severity=5,
        verifier=verifier,
    )

    calculate_report_confidence(db_session, report.id)

    db_session.refresh(report)
    verification = (
        db_session.execute(
            select(ReportVerification).where(ReportVerification.report_id == report.id)
        )
        .scalars()
        .first()
    )

    assert report.status == "VERIFIED"
    assert verification.verified_severity == 5


def test_historical_confidence_preservation(db_session: Session) -> None:
    """Verify recalculating confidence creates a new record and preserves calculations."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    report = _create_report(
        db_session,
        reporter=citizen,
        category=lighting_cat,
        status_val="SUBMITTED",
        verified_severity=None,
    )

    # First calculation when report was single and uncorroborated
    first_calc = calculate_report_confidence(db_session, report.id)
    first_score = first_calc.confidence_score

    # Another distinct citizen submits a report that is confirmed as a duplicate
    citizen2, _ = _create_user_with_role(
        db_session, "citizen", email="citizen2_corrob@safespace.org"
    )
    corroborating_report = _create_report(
        db_session,
        reporter=citizen2,
        category=lighting_cat,
        status_val="VERIFIED",
        verified_severity=3,
        verifier=verifier,
    )
    corroborating_report.duplicate_of_id = report.id
    db_session.commit()

    # Recalculate confidence with independent corroboration present
    second_calc = calculate_report_confidence(db_session, report.id)
    second_score = second_calc.confidence_score

    # History contains both
    history = get_report_confidence_history(db_session, report.id)
    assert len(history) == 2
    assert second_calc.is_current is True
    assert first_calc.is_current is False
    assert second_score > first_score


def test_zero_measurable_factors_produces_null(db_session: Session) -> None:
    """Verify that if all factors are unavailable, confidence score is NULL rather than zero."""
    # Create dummy config with 0 measurable factors
    zero_config = ConfidenceConfiguration(
        version="v_zero_measurable",
        name="Zero Measurable Factors Test Config",
        description="Methodology where all factors are unavailable",
        is_active=True,
        methodology_metadata={},
    )
    db_session.add(zero_config)
    db_session.flush()

    factor = ConfidenceConfigurationFactor(
        configuration_id=zero_config.id,
        factor_code="TEST_DEFERRED",
        name="Test Deferred Factor",
        description="Deferred",
        weight=Decimal("1.0000"),
        is_measurable=False,
        unavailability_reason="Test unavailable",
    )
    db_session.add(factor)
    db_session.commit()

    citizen, _ = _create_user_with_role(db_session, "citizen")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()
    report = _create_report(db_session, citizen, lighting_cat)

    conf = calculate_report_confidence(db_session, report.id, config_version="v_zero_measurable")
    assert conf.confidence_score is None
    assert conf.completeness_pct == Decimal("0.00")
    assert conf.available_factors_count == 0


def test_api_report_confidence_rbac(auth_client: TestClient, db_session: Session) -> None:
    """Verify RBAC on GET and POST /reports/{report_id}/confidence endpoints."""
    citizen, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()
    report = _create_report(db_session, citizen, lighting_cat)

    # Unauthenticated -> 401
    resp = auth_client.get(f"/api/v1/admin/intelligence/reports/{report.id}/confidence")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Citizen -> 403
    resp = auth_client.get(
        f"/api/v1/admin/intelligence/reports/{report.id}/confidence",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Verifier calculate -> 200
    resp = auth_client.post(
        f"/api/v1/admin/intelligence/reports/{report.id}/calculate-confidence",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert "confidence_score" in data
    assert "completeness_pct" in data
    assert "components" in data

    # Verifier read -> 200
    resp = auth_client.get(
        f"/api/v1/admin/intelligence/reports/{report.id}/confidence",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK


def test_proximity_candidates_not_treated_as_corroboration(db_session: Session) -> None:
    """Verify automated duplicate candidates are NOT treated as corroboration."""
    from app.models.duplicates import DuplicateCandidate

    citizen1, _ = _create_user_with_role(db_session, "citizen", email="cit1_prox@safespace.org")
    citizen2, _ = _create_user_with_role(db_session, "citizen", email="cit2_prox@safespace.org")
    cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    r1 = _create_report(db_session, citizen1, cat)
    r2 = _create_report(db_session, citizen2, cat)

    # An automated proximity candidate is detected but remains PENDING / unreviewed
    cand = DuplicateCandidate(
        first_report_id=min(r1.id, r2.id),
        second_report_id=max(r1.id, r2.id),
        distance_metres=Decimal("12.50"),
        time_difference_seconds=120,
        rule_version="v1.0.0",
        review_status="PENDING",
    )
    db_session.add(cand)
    db_session.commit()

    # Calculate confidence on r1
    conf = calculate_report_confidence(db_session, r1.id)
    components = {c.factor_code: c for c in conf.components}

    # INDEPENDENT_CORROBORATION must remain 0.5000 (single uncorroborated report)
    # Automatically detected candidate must NOT artificially boost corroboration
    assert components["INDEPENDENT_CORROBORATION"].factor_score == Decimal("0.5000")


def test_corroboration_requires_distinct_reporters(db_session: Session) -> None:
    """Verify corroboration requires distinct reporters, ignoring same author."""
    citizen_author, _ = _create_user_with_role(db_session, "citizen", email="author@safespace.org")
    citizen_other1, _ = _create_user_with_role(db_session, "citizen", email="other1@safespace.org")
    citizen_other2, _ = _create_user_with_role(db_session, "citizen", email="other2@safespace.org")
    cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    # Canonical report
    r_canon = _create_report(db_session, citizen_author, cat)

    # 1. Author submits a duplicate report themselves and links it
    r_author_dup = _create_report(db_session, citizen_author, cat)
    r_author_dup.duplicate_of_id = r_canon.id
    db_session.commit()

    # Author's own duplicate must NOT boost corroboration
    conf1 = calculate_report_confidence(db_session, r_canon.id)
    comp1 = {c.factor_code: c for c in conf1.components}
    assert comp1["INDEPENDENT_CORROBORATION"].factor_score == Decimal("0.5000")

    # 2. A distinct citizen links a confirmed duplicate report
    r_other1_dup = _create_report(db_session, citizen_other1, cat)
    r_other1_dup.duplicate_of_id = r_canon.id
    db_session.commit()

    # 1 distinct independent reporter -> 0.8000
    conf2 = calculate_report_confidence(db_session, r_canon.id)
    comp2 = {c.factor_code: c for c in conf2.components}
    assert comp2["INDEPENDENT_CORROBORATION"].factor_score == Decimal("0.8000")

    # 3. A second distinct citizen links another confirmed duplicate report
    r_other2_dup = _create_report(db_session, citizen_other2, cat)
    r_other2_dup.duplicate_of_id = r_canon.id
    db_session.commit()

    # >= 2 distinct independent reporters -> 1.0000
    conf3 = calculate_report_confidence(db_session, r_canon.id)
    comp3 = {c.factor_code: c for c in conf3.components}
    assert comp3["INDEPENDENT_CORROBORATION"].factor_score == Decimal("1.0000")
