"""Geospatial helper utilities for PostGIS geometry serialization and parsing."""

import re
import struct
from typing import Any

from geoalchemy2.elements import WKBElement, WKTElement


def parse_point_geometry(geom: Any) -> tuple[float, float]:
    """Extract (longitude, latitude) from a PostGIS point geometry.

    Supports GeoAlchemy2 WKTElement, WKBElement (EWKB format), and sequences.

    Args:
        geom: Geometry representation from GeoAlchemy2 or database row.

    Returns:
        tuple[float, float]: (longitude, latitude) coordinates in degrees.

    Raises:
        ValueError: If the geometry string cannot be parsed.
        TypeError: If an unsupported geometry type is encountered.
    """
    if isinstance(geom, WKTElement):
        match = re.search(
            r"POINT\s*\(\s*([^\s]+)\s+([^\s\)]+)\s*\)",
            str(geom.data or geom.desc),
            re.IGNORECASE,
        )
        if match:
            return float(match.group(1)), float(match.group(2))
        raise ValueError(f"Unable to parse WKT Point representation: {geom}")

    if isinstance(geom, WKBElement):
        raw = bytes(geom.data)
        byte_order = raw[0]
        fmt = "<" if byte_order == 1 else ">"
        geom_type = struct.unpack(fmt + "I", raw[1:5])[0]
        # In EWKB, the SRID flag is 0x20000000
        has_srid = bool(geom_type & 0x20000000)
        offset = 9 if has_srid else 5
        x, y = struct.unpack(fmt + "dd", raw[offset : offset + 16])
        return x, y

    if isinstance(geom, (tuple, list)) and len(geom) == 2:
        return float(geom[0]), float(geom[1])

    raise TypeError(f"Unsupported geometry object type for coordinate extraction: {type(geom)}")


def create_point_wkt(longitude: float, latitude: float) -> str:
    """Construct an EWKT string for a Point in WGS 84 (EPSG:4326).

    Args:
        longitude: X coordinate in degrees [-180, 180].
        latitude: Y coordinate in degrees [-90, 90].

    Returns:
        str: EWKT representation, e.g. 'SRID=4326;POINT(-73.9857 40.7484)'.
    """
    return f"SRID=4326;POINT({longitude} {latitude})"
