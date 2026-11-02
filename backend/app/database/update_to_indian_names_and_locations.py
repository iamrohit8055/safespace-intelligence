"""Update users, administrative wards, and deficiency reports to Indian context."""

from geoalchemy2.elements import WKTElement
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.geometry import create_point_wkt
from app.database.session import SessionLocal
from app.intelligence.priority import calculate_area_inspection_priority
from app.intelligence.service import calculate_area_sdi
from app.models.geography import AdministrativeArea
from app.models.iam import User
from app.models.reporting import Report

INDIAN_USERS = [
    {
        "email": "citizen@safespace.org",
        "full_name": "Aarav Sharma (Citizen)",
    },
    {
        "email": "verifier@safespace.org",
        "full_name": "Priya Patel (Verifier)",
    },
    {
        "email": "admin@safespace.org",
        "full_name": "Rajesh Iyer (City Administrator)",
    },
    {
        "email": "technician@safespace.org",
        "full_name": "Vikram Singh (Field Technician)",
    },
]


def make_multipolygon_wkt(rings: list[list[tuple[float, float]]]) -> str:
    """Format coordinates as WGS 84 EWKT MultiPolygon."""
    poly_parts = []
    for ring in rings:
        coords = [f"{lon} {lat}" for lon, lat in ring]
        poly_parts.append(f"(({', '.join(coords)}))")
    return f"SRID=4326;MULTIPOLYGON({', '.join(poly_parts)})"


# Coordinates centered in Bengaluru metropolitan municipal wards
INDIAN_AREAS = [
    {
        "code": "WARD_111",
        "name": "Ward 111 - Shantala Nagar (MG Road & Brigade Rd)",
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
        "code": "WARD_112",
        "name": "Ward 112 - Domlur & Indiranagar (100ft Road)",
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
        "code": "WARD_151",
        "name": "Ward 151 - Koramangala (80ft Road & Sony World)",
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
        "code": "WARD_174",
        "name": "Ward 174 - HSR Layout (27th Main Sector 1)",
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

INDIAN_REPORTS = [
    {
        "title": "Dark Streetlights on 100 Feet Road, Indiranagar",
        "description": (
            "Streetlights along the median from 12th Main to BDA Complex have "
            "been non-functional for three nights, creating a hazard."
        ),
        "address": "100 Feet Road, Near BDA Complex, Indiranagar, Bengaluru 560038",
        "lat": 12.9750,
        "lon": 77.6410,
    },
    {
        "title": "Severe Waterlogged Pothole near Sony World Junction",
        "description": (
            "Deep depression on the right lane posing severe skid hazard "
            "for two-wheelers and pedestrians crossing the signal."
        ),
        "address": "Sony World Signal, 80 Feet Road, 4th Block, Koramangala, Bengaluru 560034",
        "lat": 12.9350,
        "lon": 77.6240,
    },
    {
        "title": "Overgrown Peepal Tree Obscuring Traffic Signal on CMH Road",
        "description": (
            "Dense low-hanging branches completely obscure the pedestrian "
            "crossing signal opposite the metro station entrance."
        ),
        "address": "CMH Road, Indiranagar Metro Station Pillar 124, Bengaluru 560038",
        "lat": 12.9780,
        "lon": 77.6430,
    },
    {
        "title": "Broken Footpath Paver Slabs on Brigade Road",
        "description": (
            "Cracked concrete slabs with open drain exposure along the "
            "commercial pedestrian walkway blocking mobility access."
        ),
        "address": "Brigade Road, Near Rex Junction, Shantala Nagar, Bengaluru 560001",
        "lat": 12.9710,
        "lon": 77.6070,
    },
    {
        "title": "Missing Warning Signboard near Open Utility Trench",
        "description": (
            "Excavated cable chamber left without barricades or night "
            "retro-reflective tape on the service lane."
        ),
        "address": "27th Main Road, Sector 1, HSR Layout, Bengaluru 560102",
        "lat": 12.9120,
        "lon": 77.6480,
    },
]


def apply_indian_updates() -> None:
    """Apply Indian user names, administrative boundaries, and addresses."""
    db: Session = SessionLocal()
    try:
        # 1. Update user names
        for u in INDIAN_USERS:
            db.execute(
                update(User).where(User.email == u["email"]).values(full_name=u["full_name"])
            )
        users = db.execute(select(User)).scalars().all()
        generic_names = [
            "Ananya Sharma",
            "Kavita Reddy",
            "Rohan Verma",
            "Arjun Nair",
            "Suresh Kumar",
        ]
        for i, user in enumerate(users):
            has_western = any(n in user.full_name for n in ["Elena", "Sarah", "Marcus", "Dave"])
            if has_western:
                user.full_name = generic_names[i % len(generic_names)]
        db.commit()
        print("Updated users to Indian names.")

        # 2. Update or Seed Administrative Areas
        existing_areas = (
            db.execute(select(AdministrativeArea).order_by(AdministrativeArea.id)).scalars().all()
        )
        updated_areas: list[AdministrativeArea] = []
        for i, area_data in enumerate(INDIAN_AREAS):
            wkt = make_multipolygon_wkt(area_data["polygon"])
            if i < len(existing_areas):
                area = existing_areas[i]
                area.code = area_data["code"]
                area.name = area_data["name"]
                area.area_type = area_data["area_type"]
                area.boundary = WKTElement(wkt, srid=4326)
                area.properties = {
                    "city": "Bengaluru",
                    "state": "Karnataka",
                    "zone": "BBMP",
                }
                updated_areas.append(area)
            else:
                area = AdministrativeArea(
                    code=area_data["code"],
                    name=area_data["name"],
                    area_type=area_data["area_type"],
                    boundary=WKTElement(wkt, srid=4326),
                    properties={
                        "city": "Bengaluru",
                        "state": "Karnataka",
                        "zone": "BBMP",
                    },
                )
                db.add(area)
                db.flush()
                updated_areas.append(area)
        db.commit()
        print("Updated administrative areas to Bengaluru, India wards.")

        # 3. Update Reports to Indian addresses & coordinates
        reports = db.execute(select(Report).order_by(Report.id)).scalars().all()
        for i, rep in enumerate(reports):
            rep_data = INDIAN_REPORTS[i % len(INDIAN_REPORTS)]
            rep.title = rep_data["title"]
            rep.description = rep_data["description"]
            rep.address_text = rep_data["address"]
            rep.location = WKTElement(create_point_wkt(rep_data["lon"], rep_data["lat"]), srid=4326)
            if updated_areas:
                rep.administrative_area_id = updated_areas[i % len(updated_areas)].id
        db.commit()
        print(f"Updated {len(reports)} reports to Indian addresses and coordinates.")

        # 4. Recalculate SDI and Priority for all updated areas
        for area in updated_areas:
            try:
                calculate_area_sdi(db, area.id)
                calculate_area_inspection_priority(db, area.id)
            except Exception as e:
                print(f"Recalculation notice for area {area.name}: {e}")

        db.commit()
        print("Recalculated SDI and Priority scores successfully.")

    finally:
        db.close()


if __name__ == "__main__":
    apply_indian_updates()
