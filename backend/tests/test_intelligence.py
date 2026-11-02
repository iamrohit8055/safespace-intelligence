"""Comprehensive automated test suite for the Safety Deficiency Index (SDI) Intelligence Engine.

Covers:
1. Mathematical scoring formulas (category deficiency bounds, severity mapping, rounding).
2. Weight validation and missing data re-normalization.
3. Area aggregation eligibility rules (verified status, boundary match, duplicate exclusion).
4. Service orchestration, idempotence, historical versioning, and database persistence.
5. Role-based access control (RBAC) and HTTP API endpoints.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.intelligence.constants import (
    DEFAULT_CONFIGURATION_VERSION,
    STATE_INSUFFICIENT_DATA,
    STATE_OBSERVED,
)
from app.intelligence.scoring import (
    calculate_category_deficiency_score,
    calculate_sdi,
    validate_configuration_weights,
)
from app.models.geography import AdministrativeArea
from app.models.iam import Role, User, UserRole
from app.models.intelligence import AreaScore
from app.models.reporting import Report, ReportCategory
from app.models.verification import ReportStatusHistory, ReportVerification


def _create_user_with_role(
    db_session: Session,
    role_name: str,
    email: str | None = None,
) -> tuple[User, str]:
    """Helper creating a user with a specific role and returning (user, jwt_token)."""
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


def _create_test_area(db_session: Session, name: str = "Test Ward") -> AdministrativeArea:
    """Helper creating a bounded administrative area with a test polygon."""
    area_code = f"AREA_{uuid.uuid4().hex[:8].upper()}"
    area = AdministrativeArea(
        name=name,
        code=area_code,
        area_type="ward",
        boundary=WKTElement(
            "SRID=4326;MULTIPOLYGON(((10.0 10.0, 10.0 20.0, 20.0 20.0, 20.0 10.0, 10.0 10.0)))"
        ),
        properties={"test": True},
    )
    db_session.add(area)
    db_session.commit()
    return area


def _create_verified_report(
    db_session: Session,
    reporter: User,
    category: ReportCategory,
    area: AdministrativeArea | None,
    verified_severity: int,
    verifier: User,
    status_val: str = "VERIFIED",
    duplicate_of_report_id: uuid.UUID | None = None,
    latitude: float = 15.0,
    longitude: float = 15.0,
) -> Report:
    """Helper creating a report with explicit verification state and history."""
    report = Report(
        reporter_id=reporter.id,
        category_id=category.id,
        administrative_area_id=area.id if area else None,
        title=f"Deficiency in {category.code}",
        description="Detailed infrastructure deficiency description.",
        location=WKTElement(f"SRID=4326;POINT({longitude} {latitude})"),
        status=status_val,
        observed_at=datetime.now(UTC),
    )
    db_session.add(report)
    db_session.flush()

    if duplicate_of_report_id is not None:
        report.duplicate_of_id = duplicate_of_report_id

    # Create initial submission history
    db_session.add(
        ReportStatusHistory(
            report_id=report.id,
            from_status=None,
            to_status="SUBMITTED",
            changed_by_user_id=reporter.id,
            reason="Initial submission",
        )
    )

    if status_val == "VERIFIED":
        # Verification record
        db_session.add(
            ReportVerification(
                report_id=report.id,
                verifier_id=verifier.id,
                decision="VERIFIED",
                verified_severity=verified_severity,
                verified_at=datetime.now(UTC),
            )
        )
        db_session.add(
            ReportStatusHistory(
                report_id=report.id,
                from_status="UNDER_VERIFICATION",
                to_status="VERIFIED",
                changed_by_user_id=verifier.id,
                reason="Verification approved",
            )
        )

    db_session.commit()
    return report


# -----------------------------------------------------------------------------
# 1. Mathematical Scoring & Validation Unit Tests
# -----------------------------------------------------------------------------


def test_category_deficiency_score_exact_values() -> None:
    """Verify formula: (mean_severity / 5.0) * 100.00 with round_half_up."""
    # Min severity 1 -> 20.00
    assert calculate_category_deficiency_score([1]) == Decimal("20.00")

    # Max severity 5 -> 100.00
    assert calculate_category_deficiency_score([5]) == Decimal("100.00")

    # Mid severity 3 -> 60.00
    assert calculate_category_deficiency_score([3]) == Decimal("60.00")

    # Balanced [1, 5] -> mean 3.0 -> 60.00
    assert calculate_category_deficiency_score([1, 5]) == Decimal("60.00")

    # [2, 3] -> mean 2.5 -> 50.00
    assert calculate_category_deficiency_score([2, 3]) == Decimal("50.00")

    # [2, 4, 5] -> mean 11/3 = 3.6666... -> * 20 = 73.3333... -> 73.33
    assert calculate_category_deficiency_score([2, 4, 5]) == Decimal("73.33")

    # [1, 2] -> mean 1.5 -> 30.00
    assert calculate_category_deficiency_score([1, 2]) == Decimal("30.00")


def test_category_deficiency_score_empty_or_invalid_raises() -> None:
    """Verify empty sequences or out-of-bounds severities raise ValueError."""
    with pytest.raises(
        ValueError, match="Cannot calculate category deficiency score from empty observations"
    ):
        calculate_category_deficiency_score([])

    with pytest.raises(ValueError, match="Severity score must be an integer between 1 and 5"):
        calculate_category_deficiency_score([0])

    with pytest.raises(ValueError, match="Severity score must be an integer between 1 and 5"):
        calculate_category_deficiency_score([6])


def test_validate_configuration_weights() -> None:
    """Verify weight sum validation with tolerance and non-negativity."""
    # Exactly 1.0
    validate_configuration_weights([Decimal("0.30"), Decimal("0.70")])

    # Within tolerance (+0.0001)
    validate_configuration_weights([Decimal("0.50"), Decimal("0.5001")])

    # Over tolerance (> 0.0001)
    with pytest.raises(ValueError, match="must sum to 1.0"):
        validate_configuration_weights([Decimal("0.50"), Decimal("0.60")])

    # Under tolerance
    with pytest.raises(ValueError, match="must sum to 1.0"):
        validate_configuration_weights([Decimal("0.40"), Decimal("0.40")])

    # Negative weight
    with pytest.raises(ValueError, match="Category weight must be non-negative"):
        validate_configuration_weights([Decimal("-0.10"), Decimal("1.10")])


def test_calculate_sdi_all_categories_observed() -> None:
    """Verify SDI calculation when 100% of categories are observed."""
    category_scores = {
        1: Decimal("40.00"),
        2: Decimal("60.00"),
        3: Decimal("80.00"),
    }
    assigned_weights = {
        1: Decimal("0.3000"),
        2: Decimal("0.5000"),
        3: Decimal("0.2000"),
    }

    sdi, norm_weights, contribs, completeness = calculate_sdi(category_scores, assigned_weights)

    assert completeness == Decimal("100.00")
    assert norm_weights[1] == Decimal("0.3000")
    assert norm_weights[2] == Decimal("0.5000")
    assert norm_weights[3] == Decimal("0.2000")

    # Expected SDI = (40 * 0.30) + (60 * 0.50) + (80 * 0.20) = 12 + 30 + 16 = 58.00
    assert sdi == Decimal("58.00")
    assert contribs[1] == Decimal("12.0000")
    assert contribs[2] == Decimal("30.0000")
    assert contribs[3] == Decimal("16.0000")


def test_calculate_sdi_partial_data_normalization() -> None:
    """Verify dynamic re-normalization when some categories lack sufficient data."""
    category_scores = {
        1: Decimal("60.00"),  # Observed
        2: Decimal("80.00"),  # Observed
        3: None,  # Insufficient data
    }
    assigned_weights = {
        1: Decimal("0.3000"),
        2: Decimal("0.2000"),
        3: Decimal("0.5000"),
    }

    sdi, norm_weights, contribs, completeness = calculate_sdi(category_scores, assigned_weights)

    # Observed weights sum = 0.5000 -> completeness = 50.00%
    assert completeness == Decimal("50.00")

    # Normalized weights: 0.30 / 0.50 = 0.6000, 0.20 / 0.50 = 0.4000
    assert norm_weights[1] == Decimal("0.6000")
    assert norm_weights[2] == Decimal("0.4000")
    assert norm_weights[3] is None

    # Expected SDI = 60 * 0.6000 + 80 * 0.4000 = 36 + 32 = 68.00
    assert sdi == Decimal("68.00")
    assert contribs[1] == Decimal("36.0000")
    assert contribs[2] == Decimal("32.0000")
    assert contribs[3] is None


def test_calculate_sdi_zero_categories_observed() -> None:
    """Verify SDI returns None and 0.00% completeness when no categories are observed."""
    category_scores = {
        1: None,
        2: None,
    }
    assigned_weights = {
        1: Decimal("0.6000"),
        2: Decimal("0.4000"),
    }

    sdi, norm_weights, contribs, completeness = calculate_sdi(category_scores, assigned_weights)

    assert sdi is None
    assert completeness == Decimal("0.00")
    assert norm_weights[1] is None
    assert norm_weights[2] is None
    assert contribs[1] is None
    assert contribs[2] is None


# -----------------------------------------------------------------------------
# 2. Database Model & Service Aggregation Tests
# -----------------------------------------------------------------------------


def test_eligible_verified_reports_filter_rules(db_session: Session) -> None:
    """Verify aggregation excludes unverified, duplicate, and out-of-area reports."""
    from app.intelligence.aggregation import get_eligible_verified_reports

    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    area1 = _create_test_area(db_session, "Target Ward")
    area2 = _create_test_area(db_session, "Outside Ward")

    cat_light = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    # 1. Eligible verified report in area1
    r1 = _create_verified_report(
        db_session, citizen, cat_light, area1, verified_severity=4, verifier=verifier
    )

    # 2. Verified report in area2 (outside target area) -> excluded
    _create_verified_report(
        db_session, citizen, cat_light, area2, verified_severity=3, verifier=verifier
    )

    # 3. Unverified SUBMITTED report in area1 -> excluded
    _create_verified_report(
        db_session,
        citizen,
        cat_light,
        area1,
        verified_severity=5,
        verifier=verifier,
        status_val="SUBMITTED",
    )

    # 4. Duplicate report in area1 -> excluded
    _create_verified_report(
        db_session,
        citizen,
        cat_light,
        area1,
        verified_severity=4,
        verifier=verifier,
        duplicate_of_report_id=r1.id,
    )

    eligible = get_eligible_verified_reports(db_session, area1.id)
    assert len(eligible) == 1
    assert eligible[0]["report_id"] == r1.id
    assert eligible[0]["verified_severity"] == 4
    assert eligible[0]["category_id"] == cat_light.id


def test_aggregation_resolves_latest_verified_severity(db_session: Session) -> None:
    """Verify that multiple verifications on reopened report pick the latest verified severity."""
    from app.intelligence.aggregation import get_eligible_verified_reports

    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    area = _create_test_area(db_session, "Reopened Ward")

    cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "PEDESTRIAN_PATHWAYS")
    ).scalar_one()

    # Report initially verified with severity 2
    report = _create_verified_report(
        db_session, citizen, cat, area, verified_severity=2, verifier=verifier
    )

    # Reopen and re-verify with severity 5
    db_session.add(
        ReportVerification(
            report_id=report.id,
            verifier_id=verifier.id,
            decision="VERIFIED",
            verified_severity=5,
            verified_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    eligible = get_eligible_verified_reports(db_session, area.id)
    assert len(eligible) == 1
    assert eligible[0]["verified_severity"] == 5


def test_calculate_area_sdi_service_idempotence_and_history(db_session: Session) -> None:
    """Verify recalculation marks old calculation as is_current=False and preserves history."""
    from app.intelligence.service import (
        calculate_area_sdi,
        get_area_sdi_history,
        get_current_area_sdi,
    )

    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    area = _create_test_area(db_session, "History Ward")

    cat_light = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    _create_verified_report(
        db_session, citizen, cat_light, area, verified_severity=3, verifier=verifier
    )

    # First calculation
    calc1 = calculate_area_sdi(db_session, area.id)
    assert calc1.is_current is True
    calc1_id = calc1.id

    # Add another report
    _create_verified_report(
        db_session, citizen, cat_light, area, verified_severity=5, verifier=verifier
    )

    # Second calculation
    calc2 = calculate_area_sdi(db_session, area.id)
    assert calc2.is_current is True
    assert calc2.id != calc1_id

    # Verify first calculation is now is_current=False
    db_session.expire_all()
    prev_calc = db_session.execute(select(AreaScore).where(AreaScore.id == calc1_id)).scalar_one()
    assert prev_calc.is_current is False

    # Current score returns calc2
    current = get_current_area_sdi(db_session, area.id)
    assert current.id == calc2.id

    # History returns both records in descending order
    history = get_area_sdi_history(db_session, area.id)
    assert len(history) == 2
    assert history[0].id == calc2.id
    assert history[1].id == calc1_id


def test_calculate_area_sdi_empty_area(db_session: Session) -> None:
    """Verify calculation on area with zero reports returns None score and descriptive reason."""
    from app.intelligence.service import calculate_area_sdi

    area = _create_test_area(db_session, "Empty Ward")
    score_record = calculate_area_sdi(db_session, area.id)

    assert score_record.score is None
    assert score_record.completeness_pct == Decimal("0.00")
    assert score_record.participating_categories_count == 0
    assert score_record.eligible_reports_count == 0
    assert score_record.reason == "Insufficient eligible observations to compute representative SDI"
    assert len(score_record.components) == 5

    for comp in score_record.components:
        assert comp.availability_state == STATE_INSUFFICIENT_DATA
        assert comp.category_score is None
        assert comp.report_count == 0


# -----------------------------------------------------------------------------
# 3. HTTP API Endpoints & RBAC Tests
# -----------------------------------------------------------------------------


def test_api_list_scoring_configurations(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify listing scoring configurations: verifier and admin allowed, citizen forbidden."""
    _, admin_token = _create_user_with_role(db_session, "admin")
    _, verifier_token = _create_user_with_role(db_session, "verifier")
    _, citizen_token = _create_user_with_role(db_session, "citizen")

    # Unauthenticated -> 401
    resp = auth_client.get("/api/v1/admin/intelligence/scoring-configurations")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Citizen -> 403
    resp = auth_client.get(
        "/api/v1/admin/intelligence/scoring-configurations",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Verifier -> 200
    resp = auth_client.get(
        "/api/v1/admin/intelligence/scoring-configurations",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    configs = resp.json()
    assert len(configs) >= 1
    v1_config = next(c for c in configs if c["version"] == DEFAULT_CONFIGURATION_VERSION)
    assert v1_config["is_active"] is True
    assert len(v1_config["weights"]) == 5

    # Admin -> 200
    resp = auth_client.get(
        "/api/v1/admin/intelligence/scoring-configurations",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK


def test_api_calculate_area_sdi_rbac(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify POST calculate is restricted strictly to admin."""
    _, admin_token = _create_user_with_role(db_session, "admin")
    _, verifier_token = _create_user_with_role(db_session, "verifier")
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    area = _create_test_area(db_session, "RBAC Ward")

    url = f"/api/v1/admin/intelligence/areas/{area.id}/calculate"

    # Unauthenticated -> 401
    resp = auth_client.post(url)
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Citizen -> 403
    resp = auth_client.post(url, headers={"Authorization": f"Bearer {citizen_token}"})
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Verifier -> 403 (Verifier cannot trigger calculations, admin only)
    resp = auth_client.post(url, headers={"Authorization": f"Bearer {verifier_token}"})
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Admin -> 200
    resp = auth_client.post(url, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["administrative_area_id"] == str(area.id)
    assert data["is_current"] is True


def test_api_calculate_area_sdi_with_verified_reports(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify end-to-end calculation API with verified deficiency reports."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, verifier_token = _create_user_with_role(db_session, "verifier")
    _, admin_token = _create_user_with_role(db_session, "admin")
    area = _create_test_area(db_session, "Calculation Ward")

    cat_light = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()
    cat_path = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "PEDESTRIAN_PATHWAYS")
    ).scalar_one()

    # Create 2 street lighting reports (severity 2, 4 -> mean 3.0 -> score 60.00)
    _create_verified_report(
        db_session, citizen, cat_light, area, verified_severity=2, verifier=verifier
    )
    _create_verified_report(
        db_session, citizen, cat_light, area, verified_severity=4, verifier=verifier
    )

    # Create 1 pedestrian pathways report (severity 5 -> score 100.00)
    _create_verified_report(
        db_session, citizen, cat_path, area, verified_severity=5, verifier=verifier
    )

    # Street lighting assigned weight: 0.30, Pathways: 0.25 -> observed sum = 0.55
    # Normalized: light = 0.30/0.55 = 0.5455, path = 0.25/0.55 = 0.4545
    # SDI = (60.00 * 0.30 + 100.00 * 0.25) / 0.55 = (18 + 25) / 0.55 = 43 / 0.55 = 78.18

    resp = auth_client.post(
        f"/api/v1/admin/intelligence/areas/{area.id}/calculate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["administrative_area_name"] == area.name
    assert data["configuration_version"] == DEFAULT_CONFIGURATION_VERSION
    assert Decimal(str(data["score"])) == Decimal("78.18")
    assert Decimal(str(data["completeness_pct"])) == Decimal("55.00")
    assert data["participating_categories_count"] == 2
    assert data["eligible_reports_count"] == 3
    assert data["is_current"] is True

    # Verify component breakdown
    components = {c["category_code"]: c for c in data["components"]}
    assert components["STREET_LIGHTING"]["availability_state"] == STATE_OBSERVED
    assert Decimal(str(components["STREET_LIGHTING"]["category_score"])) == Decimal("60.00")
    assert components["STREET_LIGHTING"]["report_count"] == 2

    assert components["PEDESTRIAN_PATHWAYS"]["availability_state"] == STATE_OBSERVED
    assert Decimal(str(components["PEDESTRIAN_PATHWAYS"]["category_score"])) == Decimal("100.00")
    assert components["PEDESTRIAN_PATHWAYS"]["report_count"] == 1

    assert components["VISIBILITY"]["availability_state"] == STATE_INSUFFICIENT_DATA
    assert components["VISIBILITY"]["category_score"] is None
    assert components["VISIBILITY"]["report_count"] == 0


def test_api_get_current_sdi_and_history(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify retrieving current SDI and chronological history."""
    _, admin_token = _create_user_with_role(db_session, "admin")
    _, verifier_token = _create_user_with_role(db_session, "verifier")
    area = _create_test_area(db_session, "Audit Ward")

    # Before calculation: GET current returns 404
    resp = auth_client.get(
        f"/api/v1/admin/intelligence/areas/{area.id}/sdi",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    # Execute first calculation
    resp1 = auth_client.post(
        f"/api/v1/admin/intelligence/areas/{area.id}/calculate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp1.status_code == status.HTTP_200_OK

    # Execute second calculation
    resp2 = auth_client.post(
        f"/api/v1/admin/intelligence/areas/{area.id}/calculate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp2.status_code == status.HTTP_200_OK

    # GET current -> returns latest calculation
    current_resp = auth_client.get(
        f"/api/v1/admin/intelligence/areas/{area.id}/sdi",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert current_resp.status_code == status.HTTP_200_OK
    assert current_resp.json()["id"] == resp2.json()["id"]
    assert current_resp.json()["is_current"] is True

    # GET history -> returns 2 items in descending order
    history_resp = auth_client.get(
        f"/api/v1/admin/intelligence/areas/{area.id}/history",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert history_resp.status_code == status.HTTP_200_OK
    history = history_resp.json()
    assert len(history) == 2
    assert history[0]["id"] == resp2.json()["id"]
    assert history[0]["is_current"] is True
    assert history[1]["id"] == resp1.json()["id"]
    assert history[1]["is_current"] is False


def test_api_nonexistent_area_and_configuration(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify 404 errors for nonexistent area UUID or methodology version."""
    _, admin_token = _create_user_with_role(db_session, "admin")
    fake_id = uuid.uuid4()

    # Nonexistent area
    resp = auth_client.post(
        f"/api/v1/admin/intelligence/areas/{fake_id}/calculate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    area = _create_test_area(db_session, "Version Ward")

    # Nonexistent configuration version
    resp = auth_client.post(
        f"/api/v1/admin/intelligence/areas/{area.id}/calculate?configuration_version=v999.0.0",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
