"""Seed initial development administrative areas, test users, and baseline observations."""

from datetime import UTC, datetime, timedelta

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.geometry import create_point_wkt
from app.core.security import hash_password
from app.database.session import SessionLocal
from app.models.geography import AdministrativeArea
from app.models.iam import Role, User, UserRole
from app.models.reporting import Report, ReportCategory
from app.models.verification import ReportStatusHistory, ReportVerification


def make_multipolygon_wkt(rings: list[list[tuple[float, float]]]) -> str:
    """Format coordinates as WGS 84 EWKT MultiPolygon."""
    poly_parts = []
    for ring in rings:
        coords = [f"{lon} {lat}" for lon, lat in ring]
        poly_parts.append(f"(({', '.join(coords)}))")
    return f"SRID=4326;MULTIPOLYGON({', '.join(poly_parts)})"


# Coordinates in Bengaluru metropolitan wards (Indiranagar, MG Road, Koramangala, HSR Layout)
SAMPLE_AREAS = [
    {
        "name": "Ward 111 - Shantala Nagar (MG Road & Brigade Rd)",
        "code": "WARD_111",
        "area_type": "ward",
        "polygon": [
            [
                (77.590, 12.965),
                (77.615, 12.965),
                (77.615, 12.985),
                (77.590, 12.985),
                (77.590, 12.965),
            ]
        ],
    },
    {
        "name": "Ward 112 - Domlur & Indiranagar (100ft Road)",
        "code": "WARD_112",
        "area_type": "ward",
        "polygon": [
            [
                (77.625, 12.965),
                (77.655, 12.965),
                (77.655, 12.985),
                (77.625, 12.985),
                (77.625, 12.965),
            ]
        ],
    },
    {
        "name": "Ward 151 - Koramangala (80ft Road & Sony World)",
        "code": "WARD_151",
        "area_type": "ward",
        "polygon": [
            [
                (77.610, 12.925),
                (77.640, 12.925),
                (77.640, 12.945),
                (77.610, 12.945),
                (77.610, 12.925),
            ]
        ],
    },
    {
        "name": "Ward 174 - HSR Layout (27th Main Sector 1)",
        "code": "WARD_174",
        "area_type": "ward",
        "polygon": [
            [
                (77.635, 12.905),
                (77.665, 12.905),
                (77.665, 12.925),
                (77.635, 12.925),
                (77.635, 12.905),
            ]
        ],
    },
]

DEMO_USERS = [
    {
        "email": "citizen@safespace.org",
        "full_name": "Aarav Sharma (Citizen)",
        "password": "CitizenPassword123!",
        "role": "citizen",
    },
    {
        "email": "verifier@safespace.org",
        "full_name": "Priya Patel (Verifier)",
        "password": "VerifierPassword123!",
        "role": "verifier",
    },
    {
        "email": "admin@safespace.org",
        "full_name": "Rajesh Iyer (City Administrator)",
        "password": "AdminPassword123!",
        "role": "admin",
    },
    {
        "email": "technician@safespace.org",
        "full_name": "Vikram Singh (Field Technician)",
        "password": "TechnicianPassword123!",
        "role": "maintenance",
    },
]


def seed_development_data() -> None:
    """Populate baseline demonstration dataset if database is empty."""
    db: Session = SessionLocal()
    try:
        # 1. Seed Demo Users
        users_by_role: dict[str, User] = {}
        for u_data in DEMO_USERS:
            existing = db.execute(
                select(User).where(User.email == u_data["email"])
            ).scalar_one_or_none()
            if existing is None:
                user = User(
                    email=u_data["email"],
                    hashed_password=hash_password(u_data["password"]),
                    full_name=u_data["full_name"],
                    is_active=True,
                    is_verified=True,
                )
                db.add(user)
                db.flush()
                role = db.execute(select(Role).where(Role.name == u_data["role"])).scalar_one()
                db.add(UserRole(user_id=user.id, role_id=role.id))
                db.commit()
                db.refresh(user)
                users_by_role[u_data["role"]] = user
            else:
                users_by_role[u_data["role"]] = existing

        # 2. Seed Administrative Areas
        area_count = db.execute(select(func.count(AdministrativeArea.id))).scalar_one()
        created_areas: list[AdministrativeArea] = []
        if area_count == 0:
            for a_data in SAMPLE_AREAS:
                wkt = make_multipolygon_wkt(a_data["polygon"])
                area = AdministrativeArea(
                    name=a_data["name"],
                    code=a_data["code"],
                    area_type=a_data["area_type"],
                    boundary=WKTElement(wkt, srid=4326),
                    properties={"population": 45000, "zone": "Urban Core"},
                )
                db.add(area)
                db.flush()
                created_areas.append(area)
            db.commit()
        else:
            created_areas = list(db.execute(select(AdministrativeArea)).scalars().all())

        # 3. Seed Reports if none exist
        report_count = db.execute(select(func.count(Report.id))).scalar_one()
        if report_count == 0 and created_areas:
            categories = list(db.execute(select(ReportCategory)).scalars().all())
            cat_map = {c.code: c for c in categories}
            citizen = users_by_role["citizen"]
            verifier = users_by_role["verifier"]

            sample_reports = [
                {
                    "title": "Broken Street Lamps on Brigade Road",
                    "description": (
                        "Entire stretch near Rex Junction has dark streetlights since last week."
                    ),
                    "category": cat_map.get("STREET_LIGHTING", categories[0]),
                    "area": created_areas[0],
                    "address_text": "Brigade Road, Shantala Nagar, Bengaluru",
                    "lat": 12.9735,
                    "lon": 77.6074,
                    "status": "VERIFIED",
                    "severity": 4,
                },
                {
                    "title": "Severe Pothole Near Metro Entrance",
                    "description": (
                        "Deep crater next to pedestrian crosswalk poses severe "
                        "risk to two-wheelers and pedestrians."
                    ),
                    "category": cat_map.get("MAINTENANCE", categories[0]),
                    "area": created_areas[0],
                    "address_text": "MG Road Metro Station Exit B, Bengaluru",
                    "lat": 12.9752,
                    "lon": 77.6062,
                    "status": "VERIFIED",
                    "severity": 5,
                },
                {
                    "title": "Overgrown Banyan Tree Obscuring 100ft Road Turn",
                    "description": (
                        "Dense tree branches completely block sightline at the "
                        "busy 12th Main intersection."
                    ),
                    "category": cat_map.get("VISIBILITY", categories[0]),
                    "area": created_areas[1],
                    "address_text": "100 Feet Road, Indiranagar, Bengaluru",
                    "lat": 12.9721,
                    "lon": 77.6412,
                    "status": "UNDER_VERIFICATION",
                    "severity": None,
                },
                {
                    "title": "Damaged Wheelchair Ramp on 80ft Road",
                    "description": (
                        "Concrete footpath slab broken and exposed iron rods "
                        "near Sony World Signal."
                    ),
                    "category": cat_map.get("PEDESTRIAN_PATHWAYS", categories[0]),
                    "area": created_areas[2],
                    "address_text": "80 Feet Road, 4th Block, Koramangala, Bengaluru",
                    "lat": 12.9351,
                    "lon": 77.6248,
                    "status": "SUBMITTED",
                    "severity": None,
                },
                {
                    "title": "Missing Emergency Help Point Signage",
                    "description": (
                        "Public safety assistance post beacon is missing near BDA Complex."
                    ),
                    "category": cat_map.get("PUBLIC_ASSISTANCE", categories[0]),
                    "area": created_areas[3],
                    "address_text": "Sector 1, 27th Main Road, HSR Layout, Bengaluru",
                    "lat": 12.9126,
                    "lon": 77.6441,
                    "status": "SUBMITTED",
                    "severity": None,
                },
            ]

            now = datetime.now(UTC)
            for s in sample_reports:
                pt_wkt = create_point_wkt(s["lon"], s["lat"])
                rep = Report(
                    reporter_id=citizen.id,
                    category_id=s["category"].id,
                    administrative_area_id=s["area"].id,
                    title=s["title"],
                    description=s["description"],
                    location=WKTElement(pt_wkt, srid=4326),
                    address_text=s["address_text"],
                    status=s["status"],
                    observed_at=now - timedelta(days=2),
                )
                db.add(rep)
                db.flush()

                db.add(
                    ReportStatusHistory(
                        report_id=rep.id,
                        from_status=None,
                        to_status="SUBMITTED",
                        changed_by_user_id=citizen.id,
                        reason="Initial submission",
                    )
                )

                if s["status"] in ("UNDER_VERIFICATION", "VERIFIED"):
                    db.add(
                        ReportStatusHistory(
                            report_id=rep.id,
                            from_status="SUBMITTED",
                            to_status=s["status"],
                            changed_by_user_id=verifier.id,
                            reason="Moderation review",
                        )
                    )

                if s["status"] == "VERIFIED":
                    db.add(
                        ReportVerification(
                            report_id=rep.id,
                            verifier_id=verifier.id,
                            decision="VERIFIED",
                            verified_severity=s["severity"],
                            verification_notes="Field inspection confirmed deficiency severity.",
                        )
                    )

            db.commit()
            print("Successfully seeded demo users, administrative areas, and sample reports.")
        else:
            print("Database already contains data; skipping initial seed.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_development_data()
