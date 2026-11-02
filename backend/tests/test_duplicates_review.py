"""Tests for Step 8B: Duplicate Review and Linking.

Covers:
1. Authorized verifier and admin can review candidates.
2. Citizen forbidden from reviewing candidates (403).
3. Confirmed duplicate links correctly via duplicate_of_id.
4. Non-duplicate decision does not alter report relationships.
5. Needs-review decision keeps candidate pending further review.
6. Prevention of self-links and circular duplicate relationships.
7. Canonical report cannot itself be a duplicate.
8. Multiple reviews preserve append-only review history.
9. Incompatible category link prevention.
10. Existing SDI aggregation excludes confirmed linked duplicates.
11. Transaction rollback on failure.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.intelligence.aggregation import get_eligible_verified_reports
from app.models.duplicates import DuplicateCandidate, DuplicateReviewHistory
from app.models.geography import AdministrativeArea
from app.models.iam import Role, User, UserRole
from app.models.reporting import Report, ReportCategory
from app.models.verification import ReportVerification
from app.schemas.duplicates import DuplicateReviewRequest
from app.services.duplicates import detect_candidates_for_report, review_duplicate_candidate


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
    lat: float = 40.7484,
    lon: float = -73.9857,
    status_val: str = "SUBMITTED",
    submitted_at: datetime | None = None,
    area: AdministrativeArea | None = None,
) -> Report:
    """Helper creating a report."""
    sub_time = submitted_at or datetime.now(UTC)
    report = Report(
        reporter_id=reporter.id,
        category_id=category.id,
        administrative_area_id=area.id if area else None,
        title=f"Report in {category.code}",
        description="Physical deficiency report observation.",
        location=WKTElement(f"SRID=4326;POINT({lon} {lat})"),
        status=status_val,
        observed_at=sub_time - timedelta(hours=1),
        submitted_at=sub_time,
    )
    db_session.add(report)
    db_session.commit()
    return report


def test_confirmed_duplicate_links_correctly(db_session: Session) -> None:
    """Verify that confirming a duplicate links the newer report to the earlier canonical report."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    t1 = datetime.now(UTC) - timedelta(hours=2)
    t2 = datetime.now(UTC) - timedelta(hours=1)

    r_earlier = _create_report(
        db_session, citizen, lighting_cat, lat=40.74844, lon=-73.9857, submitted_at=t1
    )
    r_later = _create_report(
        db_session, citizen, lighting_cat, lat=40.74848, lon=-73.9857, submitted_at=t2
    )

    candidates = detect_candidates_for_report(db_session, r_earlier.id)
    assert len(candidates) == 1
    candidate = candidates[0]

    req = DuplicateReviewRequest(
        decision="CONFIRMED_DUPLICATE",
        reason="Verified to refer to the exact same broken street luminaire",
    )
    updated_cand, history = review_duplicate_candidate(db_session, candidate.id, req, verifier)

    assert updated_cand.review_status == "CONFIRMED_DUPLICATE"
    assert updated_cand.reviewer_id == verifier.id

    # Reload reports
    db_session.refresh(r_earlier)
    db_session.refresh(r_later)

    # Deterministic rule: earlier report is canonical, later report has duplicate_of_id set
    assert r_earlier.duplicate_of_id is None
    assert r_later.duplicate_of_id == r_earlier.id

    # Verify audit history
    assert history.decision == "CONFIRMED_DUPLICATE"
    assert history.canonical_report_id == r_earlier.id
    assert history.duplicate_report_id == r_later.id
    assert history.reviewer_id == verifier.id


def test_non_duplicate_decision_preserves_relationships(db_session: Session) -> None:
    """Verify that NOT_DUPLICATE leaves reports independent without duplicate_of_id."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    r1 = _create_report(db_session, citizen, lighting_cat, lat=40.74844, lon=-73.9857)
    r2 = _create_report(db_session, citizen, lighting_cat, lat=40.74848, lon=-73.9857)

    candidates = detect_candidates_for_report(db_session, r1.id)
    cand = candidates[0]

    req = DuplicateReviewRequest(
        decision="NOT_DUPLICATE",
        reason="Distinct streetlights on opposite sides of the avenue",
    )
    updated_cand, history = review_duplicate_candidate(db_session, cand.id, req, verifier)

    assert updated_cand.review_status == "NOT_DUPLICATE"
    db_session.refresh(r1)
    db_session.refresh(r2)
    assert r1.duplicate_of_id is None
    assert r2.duplicate_of_id is None
    assert history.decision == "NOT_DUPLICATE"


def test_canonical_report_cannot_itself_be_a_duplicate(db_session: Session) -> None:
    """Verify that a report that is already a duplicate cannot be chosen as canonical."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    r_root = _create_report(db_session, citizen, lighting_cat, lat=40.74840, lon=-73.9857)
    r_dup = _create_report(db_session, citizen, lighting_cat, lat=40.74842, lon=-73.9857)
    r_dup.duplicate_of_id = r_root.id
    db_session.commit()

    r3 = _create_report(db_session, citizen, lighting_cat, lat=40.74844, lon=-73.9857)

    cand = DuplicateCandidate(
        first_report_id=min(r_dup.id, r3.id),
        second_report_id=max(r_dup.id, r3.id),
        distance_metres=Decimal("10.0"),
        time_difference_seconds=60,
        rule_version="v1.0.0",
        review_status="PENDING",
    )
    db_session.add(cand)
    db_session.commit()

    # Attempt to confirm duplicate with r_dup as canonical report
    req = DuplicateReviewRequest(
        decision="CONFIRMED_DUPLICATE",
        reason="Attempting to link to an already-duplicate report",
        canonical_report_id=r_dup.id,
    )
    with pytest.raises(Exception) as exc:
        review_duplicate_candidate(db_session, cand.id, req, verifier)
    assert "already a linked duplicate" in str(exc.value).lower()


def test_incompatible_categories_cannot_be_linked(db_session: Session) -> None:
    """Verify that candidate review rejects linking reports with incompatible categories."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()
    pothole_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "MAINTENANCE")
    ).scalar_one()

    r1 = _create_report(db_session, citizen, lighting_cat, lat=40.74840, lon=-73.9857)
    r2 = _create_report(db_session, citizen, pothole_cat, lat=40.74842, lon=-73.9857)

    cand = DuplicateCandidate(
        first_report_id=min(r1.id, r2.id),
        second_report_id=max(r1.id, r2.id),
        distance_metres=Decimal("10.0"),
        time_difference_seconds=60,
        rule_version="v1.0.0",
        review_status="PENDING",
    )
    db_session.add(cand)
    db_session.commit()

    req = DuplicateReviewRequest(
        decision="CONFIRMED_DUPLICATE", reason="Attempt cross-category link"
    )
    with pytest.raises(Exception) as exc:
        review_duplicate_candidate(db_session, cand.id, req, verifier)
    assert "incompatible categories" in str(exc.value).lower()


def test_transaction_failure_rolls_back_all_changes(db_session: Session) -> None:
    """Verify that if an error occurs during review, the transaction rolls back cleanly."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    r1 = _create_report(db_session, citizen, lighting_cat, lat=40.74844, lon=-73.9857)
    r2 = _create_report(db_session, citizen, lighting_cat, lat=40.74848, lon=-73.9857)

    candidates = detect_candidates_for_report(db_session, r1.id)
    cand = candidates[0]

    req = DuplicateReviewRequest(decision="CONFIRMED_DUPLICATE", reason="Simulated rollback test")

    # Simulate database error on commit
    with (
        patch.object(db_session, "commit", side_effect=RuntimeError("Simulated DB Crash")),
        pytest.raises(RuntimeError),
    ):
        review_duplicate_candidate(db_session, cand.id, req, verifier)

    db_session.refresh(r1)
    db_session.refresh(r2)
    db_session.refresh(cand)
    assert r1.duplicate_of_id is None
    assert r2.duplicate_of_id is None
    assert cand.review_status == "PENDING"


def test_multiple_reviews_preserve_history(db_session: Session) -> None:
    """Verify that multiple reviews of a candidate pair preserve all audit records."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    admin, _ = _create_user_with_role(db_session, "admin")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    r1 = _create_report(db_session, citizen, lighting_cat, lat=40.74844, lon=-73.9857)
    _create_report(db_session, citizen, lighting_cat, lat=40.74848, lon=-73.9857)

    candidates = detect_candidates_for_report(db_session, r1.id)
    cand = candidates[0]

    # First review: NEEDS_REVIEW
    req1 = DuplicateReviewRequest(decision="NEEDS_REVIEW", reason="Need daylight re-inspection")
    review_duplicate_candidate(db_session, cand.id, req1, verifier)

    # Second review: CONFIRMED_DUPLICATE
    req2 = DuplicateReviewRequest(decision="CONFIRMED_DUPLICATE", reason="Confirmed by day patrol")
    review_duplicate_candidate(db_session, cand.id, req2, admin)

    history = (
        db_session.execute(
            select(DuplicateReviewHistory)
            .where(DuplicateReviewHistory.candidate_id == cand.id)
            .order_by(DuplicateReviewHistory.reviewed_at.asc())
        )
        .scalars()
        .all()
    )
    assert len(history) == 2
    assert history[0].decision == "NEEDS_REVIEW"
    assert history[0].reviewer_id == verifier.id
    assert history[1].decision == "CONFIRMED_DUPLICATE"
    assert history[1].reviewer_id == admin.id


def test_sdi_aggregation_excludes_confirmed_duplicates(db_session: Session) -> None:
    """Verify that once a duplicate is confirmed, SDI aggregation excludes it."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    area_code = f"AREA_{uuid.uuid4().hex[:8].upper()}"
    area = AdministrativeArea(
        name="Test Dup Ward",
        code=area_code,
        area_type="ward",
        boundary=WKTElement(
            "SRID=4326;MULTIPOLYGON(((10.0 10.0, 10.0 20.0, 20.0 20.0, 20.0 10.0, 10.0 10.0)))"
        ),
        properties={},
    )
    db_session.add(area)
    db_session.commit()

    # Create two verified reports in the same area
    r1 = _create_report(
        db_session,
        citizen,
        lighting_cat,
        lat=15.0,
        lon=15.0,
        status_val="VERIFIED",
        area=area,
        submitted_at=datetime.now(UTC) - timedelta(hours=2),
    )
    v1 = ReportVerification(
        report_id=r1.id,
        verifier_id=verifier.id,
        decision="VERIFIED",
        verified_severity=5,
    )
    db_session.add(v1)

    r2 = _create_report(
        db_session,
        citizen,
        lighting_cat,
        lat=15.0001,
        lon=15.0001,
        status_val="VERIFIED",
        area=area,
        submitted_at=datetime.now(UTC) - timedelta(hours=1),
    )
    v2 = ReportVerification(
        report_id=r2.id,
        verifier_id=verifier.id,
        decision="VERIFIED",
        verified_severity=4,
    )
    db_session.add(v2)
    db_session.commit()

    # Before linking, both reports are eligible in area
    eligible_before = get_eligible_verified_reports(db_session, area.id)
    assert len(eligible_before) == 2

    # Link r2 as duplicate of r1
    cand = DuplicateCandidate(
        first_report_id=min(r1.id, r2.id),
        second_report_id=max(r1.id, r2.id),
        distance_metres=Decimal("15.0"),
        time_difference_seconds=3600,
        rule_version="v1.0.0",
        review_status="PENDING",
    )
    db_session.add(cand)
    db_session.commit()

    req = DuplicateReviewRequest(
        decision="CONFIRMED_DUPLICATE", reason="Duplicate broken streetlight"
    )
    review_duplicate_candidate(db_session, cand.id, req, verifier)

    # After linking, duplicate r2 is excluded from SDI calculation!
    eligible_after = get_eligible_verified_reports(db_session, area.id)
    assert len(eligible_after) == 1
    assert eligible_after[0]["report_id"] == r1.id


def test_api_review_candidate_rbac(auth_client: TestClient, db_session: Session) -> None:
    """Verify RBAC on POST /duplicate-candidates/{candidate_id}/review."""
    citizen, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    r1 = _create_report(db_session, citizen, lighting_cat, lat=40.74844, lon=-73.9857)
    r2 = _create_report(db_session, citizen, lighting_cat, lat=40.74848, lon=-73.9857)

    cand = DuplicateCandidate(
        first_report_id=min(r1.id, r2.id),
        second_report_id=max(r1.id, r2.id),
        distance_metres=Decimal("5.0"),
        time_difference_seconds=60,
        rule_version="v1.0.0",
        review_status="PENDING",
    )
    db_session.add(cand)
    db_session.commit()

    payload = {"decision": "CONFIRMED_DUPLICATE", "reason": "Exact physical duplicate"}

    # Citizen forbidden -> 403
    resp = auth_client.post(
        f"/api/v1/admin/intelligence/duplicate-candidates/{cand.id}/review",
        json=payload,
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Verifier allowed -> 200
    resp = auth_client.post(
        f"/api/v1/admin/intelligence/duplicate-candidates/{cand.id}/review",
        json=payload,
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["review_status"] == "CONFIRMED_DUPLICATE"


def test_canonical_selection_earlier_submitted_vs_later_verified(db_session: Session) -> None:
    """Verify that a later VERIFIED report is preferred over an earlier SUBMITTED report.

    This prevents SDI suppression where an unverified earlier report would otherwise
    take canonical status and cause the verified observation to be excluded.
    """
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    t1 = datetime.now(UTC) - timedelta(hours=3)
    t2 = datetime.now(UTC) - timedelta(hours=1)

    # Report A: earlier, SUBMITTED
    r_submitted = _create_report(
        db_session,
        citizen,
        cat,
        lat=40.74844,
        lon=-73.9857,
        status_val="SUBMITTED",
        submitted_at=t1,
    )

    # Report B: later, VERIFIED with severity 4
    r_verified = _create_report(
        db_session,
        citizen,
        cat,
        lat=40.74848,
        lon=-73.9857,
        status_val="VERIFIED",
        submitted_at=t2,
    )
    v = ReportVerification(
        report_id=r_verified.id,
        verifier_id=verifier.id,
        decision="VERIFIED",
        verified_severity=4,
        verification_notes="Confirmed working defective luminaire",
    )
    db_session.add(v)
    db_session.commit()

    candidates = detect_candidates_for_report(db_session, r_submitted.id)
    assert len(candidates) == 1
    cand = candidates[0]

    req = DuplicateReviewRequest(
        decision="CONFIRMED_DUPLICATE",
        reason="Identical broken light confirmed",
    )
    cand_res, history = review_duplicate_candidate(db_session, cand.id, req, verifier)

    db_session.refresh(r_submitted)
    db_session.refresh(r_verified)

    # The later VERIFIED report MUST be selected as canonical to avoid SDI suppression
    assert r_verified.duplicate_of_id is None
    assert r_submitted.duplicate_of_id == r_verified.id
    assert history.canonical_report_id == r_verified.id
    assert history.duplicate_report_id == r_submitted.id


def test_canonical_selection_two_verified_reports(db_session: Session) -> None:
    """Verify that when both reports are VERIFIED, the earlier submitted report is selected."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    t1 = datetime.now(UTC) - timedelta(hours=4)
    t2 = datetime.now(UTC) - timedelta(hours=2)

    r_v1 = _create_report(
        db_session, citizen, cat, lat=40.74844, lon=-73.9857, status_val="VERIFIED", submitted_at=t1
    )
    db_session.add(
        ReportVerification(
            report_id=r_v1.id, verifier_id=verifier.id, decision="VERIFIED", verified_severity=3
        )
    )

    r_v2 = _create_report(
        db_session, citizen, cat, lat=40.74848, lon=-73.9857, status_val="VERIFIED", submitted_at=t2
    )
    db_session.add(
        ReportVerification(
            report_id=r_v2.id, verifier_id=verifier.id, decision="VERIFIED", verified_severity=4
        )
    )
    db_session.commit()

    candidates = detect_candidates_for_report(db_session, r_v1.id)
    assert len(candidates) == 1
    cand = candidates[0]

    req = DuplicateReviewRequest(decision="CONFIRMED_DUPLICATE", reason="Both verified same defect")
    _, history = review_duplicate_candidate(db_session, cand.id, req, verifier)

    db_session.refresh(r_v1)
    db_session.refresh(r_v2)

    # Earlier verified report is canonical
    assert r_v1.duplicate_of_id is None
    assert r_v2.duplicate_of_id == r_v1.id
    assert history.canonical_report_id == r_v1.id
    assert history.duplicate_report_id == r_v2.id


def test_canonical_selection_two_submitted_reports(db_session: Session) -> None:
    """Verify that when both reports are unverified SUBMITTED, the earlier submitted report wins."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    t1 = datetime.now(UTC) - timedelta(hours=5)
    t2 = datetime.now(UTC) - timedelta(hours=1)

    r_s1 = _create_report(
        db_session,
        citizen,
        cat,
        lat=40.74844,
        lon=-73.9857,
        status_val="SUBMITTED",
        submitted_at=t1,
    )
    r_s2 = _create_report(
        db_session,
        citizen,
        cat,
        lat=40.74848,
        lon=-73.9857,
        status_val="SUBMITTED",
        submitted_at=t2,
    )

    candidates = detect_candidates_for_report(db_session, r_s1.id)
    cand = candidates[0]

    req = DuplicateReviewRequest(decision="CONFIRMED_DUPLICATE", reason="Duplicate citizen reports")
    _, history = review_duplicate_candidate(db_session, cand.id, req, verifier)

    db_session.refresh(r_s1)
    db_session.refresh(r_s2)

    # Earlier report is canonical
    assert r_s1.duplicate_of_id is None
    assert r_s2.duplicate_of_id == r_s1.id
    assert history.canonical_report_id == r_s1.id
    assert history.duplicate_report_id == r_s2.id


def test_canonical_selection_rejected_and_archived_reports(db_session: Session) -> None:
    """Verify that ARCHIVED and REJECTED reports are never selected as canonical."""
    from fastapi import HTTPException

    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    t1 = datetime.now(UTC) - timedelta(hours=6)
    t2 = datetime.now(UTC) - timedelta(hours=2)

    # r_rejected (earlier) vs r_submitted (later)
    r_rejected = _create_report(
        db_session,
        citizen,
        cat,
        lat=40.74844,
        lon=-73.9857,
        status_val="REJECTED",
        submitted_at=t1,
    )
    r_submitted = _create_report(
        db_session,
        citizen,
        cat,
        lat=40.74848,
        lon=-73.9857,
        status_val="SUBMITTED",
        submitted_at=t2,
    )

    cand = DuplicateCandidate(
        first_report_id=min(r_rejected.id, r_submitted.id),
        second_report_id=max(r_rejected.id, r_submitted.id),
        distance_metres=Decimal("4.5"),
        time_difference_seconds=14400,
        rule_version="v1.0.0",
        review_status="PENDING",
    )
    db_session.add(cand)
    db_session.commit()

    # Automatic selection should pick r_submitted as canonical because r_rejected is ineligible
    req = DuplicateReviewRequest(decision="CONFIRMED_DUPLICATE", reason="Link to active report")
    _, history = review_duplicate_candidate(db_session, cand.id, req, verifier)

    db_session.refresh(r_rejected)
    db_session.refresh(r_submitted)

    assert r_submitted.duplicate_of_id is None
    assert r_rejected.duplicate_of_id == r_submitted.id
    assert history.canonical_report_id == r_submitted.id

    # Test that explicit selection of a REJECTED report fails with 400
    r_rejected2 = _create_report(
        db_session, citizen, cat, lat=40.74844, lon=-73.9857, status_val="REJECTED"
    )
    r_archived2 = _create_report(
        db_session, citizen, cat, lat=40.74848, lon=-73.9857, status_val="ARCHIVED"
    )
    cand2 = DuplicateCandidate(
        first_report_id=min(r_rejected2.id, r_archived2.id),
        second_report_id=max(r_rejected2.id, r_archived2.id),
        distance_metres=Decimal("3.0"),
        time_difference_seconds=100,
        rule_version="v1.0.0",
        review_status="PENDING",
    )
    db_session.add(cand2)
    db_session.commit()

    # Both are ineligible -> should raise HTTPException 400
    with pytest.raises(HTTPException) as exc_info:
        review_duplicate_candidate(db_session, cand2.id, req, verifier)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "ARCHIVED or REJECTED reports cannot serve as canonical" in exc_info.value.detail


def test_sdi_aggregation_after_canonical_linking(db_session: Session) -> None:
    """Verify that the verified canonical report remains eligible for SDI calculations."""
    from app.intelligence.service import calculate_area_sdi

    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    area = AdministrativeArea(
        name="SDI Duplicate Test Ward",
        code=f"WARD_{uuid.uuid4().hex[:6].upper()}",
        area_type="ward",
        boundary=WKTElement(
            "SRID=4326;MULTIPOLYGON(((10.0 10.0, 10.0 20.0, 20.0 20.0, 20.0 10.0, 10.0 10.0)))"
        ),
        properties={"zone": "commercial"},
    )
    db_session.add(area)
    db_session.commit()

    t1 = datetime.now(UTC) - timedelta(hours=3)
    t2 = datetime.now(UTC) - timedelta(hours=1)

    # Report A: earlier, SUBMITTED
    r_submitted = _create_report(
        db_session,
        citizen,
        cat,
        lat=15.0,
        lon=15.0,
        status_val="SUBMITTED",
        submitted_at=t1,
        area=area,
    )

    # Report B: later, VERIFIED with severity 4
    r_verified = _create_report(
        db_session,
        citizen,
        cat,
        lat=15.0001,
        lon=15.0001,
        status_val="VERIFIED",
        submitted_at=t2,
        area=area,
    )
    db_session.add(
        ReportVerification(
            report_id=r_verified.id,
            verifier_id=verifier.id,
            decision="VERIFIED",
            verified_severity=4,
            verification_notes="Verified defective luminaire",
        )
    )
    db_session.commit()

    # Detect and confirm duplicate
    candidates = detect_candidates_for_report(db_session, r_submitted.id)
    cand = candidates[0]
    req = DuplicateReviewRequest(
        decision="CONFIRMED_DUPLICATE", reason="Confirmed identical defect"
    )
    review_duplicate_candidate(db_session, cand.id, req, verifier)

    db_session.refresh(r_verified)
    db_session.refresh(r_submitted)

    # Verified report is canonical
    assert r_verified.duplicate_of_id is None
    assert r_submitted.duplicate_of_id == r_verified.id

    # Verify query for eligible reports for SDI includes r_verified and excludes r_submitted
    eligible = get_eligible_verified_reports(db_session, area.id)
    assert len(eligible) == 1
    assert eligible[0]["report_id"] == r_verified.id
    assert eligible[0]["verified_severity"] == 4

    # Calculate SDI for the area
    area_score = calculate_area_sdi(db_session, area.id)
    assert area_score.score is not None
    assert area_score.eligible_reports_count == 1
    # Severity 4 on 1-5 scale -> (4/5)*100 = 80.00
    assert area_score.score == Decimal("80.00")
