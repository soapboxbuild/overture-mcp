"""DuckDB queries against Overture Maps S3 parquet files."""

from __future__ import annotations

import math
from typing import Any

import duckdb

# Latest Overture release — update when a new release drops
OVERTURE_RELEASE = "2026-05-20.0"
OVERTURE_BUILDINGS = (
    f"s3://overturemaps-us-west-2/release/{OVERTURE_RELEASE}"
    "/theme=buildings/type=building/*"
)
OVERTURE_SEGMENTS = (
    f"s3://overturemaps-us-west-2/release/{OVERTURE_RELEASE}"
    "/theme=transportation/type=segment/*"
)


# Cached connection — avoids repeated extension loading + S3 metadata fetches per request
_conn: duckdb.DuckDBPyConnection | None = None


def _get_conn() -> duckdb.DuckDBPyConnection:
    """Return the module-level DuckDB connection, creating it if needed."""
    global _conn
    if _conn is None:
        _conn = duckdb.connect()
        _conn.execute("LOAD httpfs; LOAD spatial;")
        _conn.execute("SET s3_region='us-west-2';")
        _conn.execute("SET http_keep_alive=true;")
    return _conn


def _meters_to_deg(radius_m: float, lat: float) -> tuple[float, float]:
    """Convert radius in metres to (delta_lat, delta_lon) in degrees."""
    delta_lat = radius_m / 111_320.0
    delta_lon = radius_m / (111_320.0 * math.cos(math.radians(lat)))
    return delta_lat, delta_lon


def _row_to_dict(row: tuple, dist_m: float | None = None) -> dict[str, Any]:
    """Map a query result row to a building dict. dist_m is optional."""
    (
        building_id,
        geometry,
        height,
        building_class,
        subtype,
        primary_name,
        source_dataset,
        confidence,
        level,
        num_floors,
        facade_color,
        facade_material,
        roof_material,
        roof_shape,
        min_height,
        is_underground,
        *rest
    ) = row
    d = {
        "id": building_id,
        "geometry_geojson": geometry,
        "height": height,
        "min_height": min_height,
        "class": building_class,
        "subtype": subtype,
        "names": {"primary": primary_name},
        "sources": [{"dataset": source_dataset, "confidence": confidence}],
        "level": level,
        "num_floors": num_floors,
        "facade_color": facade_color,
        "facade_material": facade_material,
        "roof_material": roof_material,
        "roof_shape": roof_shape,
        "is_underground": is_underground,
    }
    # Include dist_m if provided or present as the 17th column
    effective_dist = dist_m if dist_m is not None else (rest[0] if rest else None)
    if effective_dist is not None:
        d["dist_m"] = effective_dist
    return d


# Standard 16-column select — no raw_geometry
_SELECT_COLS = """
    id,
    ST_AsGeoJSON(geometry) as geometry,
    height,
    class,
    subtype,
    names."primary" as primary_name,
    sources[1].dataset as source_dataset,
    sources[1].confidence as confidence,
    level,
    num_floors,
    facade_color,
    facade_material,
    roof_material,
    roof_shape,
    min_height,
    is_underground
"""

# Extended select for get_building — includes raw_geometry for ST_Contains
_SELECT_COLS_WITH_RAW = _SELECT_COLS.rstrip() + ",\n    geometry as raw_geometry\n"


def get_building(lat: float, lon: float, radius_m: int = 100) -> dict | None:
    """Return the building at/nearest to (lat, lon) within radius_m metres.

    Tries ST_Contains first (point inside footprint), then falls back to the
    geometrically nearest building in the bounding box.

    Returns None if no building found within the radius.
    """
    conn = _get_conn()
    delta_lat, delta_lon = _meters_to_deg(radius_m, lat)

    rows = conn.execute(
        f"""
        WITH candidates AS (
            SELECT {_SELECT_COLS_WITH_RAW},
                ST_Distance(
                    ST_Transform(geometry, 'EPSG:4326', 'EPSG:3857'),
                    ST_Transform(ST_Point(?, ?), 'EPSG:4326', 'EPSG:3857')
                ) AS dist_m
            FROM read_parquet('{OVERTURE_BUILDINGS}', hive_partitioning=1)
            WHERE bbox.xmin >= ? AND bbox.xmax <= ?
            AND bbox.ymin >= ? AND bbox.ymax <= ?
        )
        SELECT * EXCLUDE (dist_m, raw_geometry)
        FROM candidates
        WHERE dist_m <= ?
        ORDER BY
            CASE WHEN ST_Contains(raw_geometry, ST_Point(?, ?)) THEN 0 ELSE 1 END,
            dist_m
        LIMIT 1
        """,
        [
            lon, lat,
            lon - delta_lon, lon + delta_lon,
            lat - delta_lat, lat + delta_lat,
            float(radius_m),
            lon, lat,
        ],
    ).fetchall()

    if not rows:
        return None
    return _row_to_dict(rows[0])


def get_building_by_id(
    overture_id: str,
    lat_hint: float | None = None,
    lon_hint: float | None = None,
    radius_hint_m: int = 5000,
) -> dict | None:
    """Fetch a building by its Overture GERS id.

    WARNING: Without lat/lon hints this scans the full global dataset and will
    be very slow. Provide lat_hint + lon_hint for a fast bounded search.
    """
    conn = _get_conn()
    if lat_hint is not None and lon_hint is not None:
        delta_lat, delta_lon = _meters_to_deg(radius_hint_m, lat_hint)
        rows = conn.execute(
            f"""
            SELECT {_SELECT_COLS}
            FROM read_parquet('{OVERTURE_BUILDINGS}', hive_partitioning=1)
            WHERE id = ?
            AND bbox.xmin >= ? AND bbox.xmax <= ?
            AND bbox.ymin >= ? AND bbox.ymax <= ?
            LIMIT 1
            """,
            [
                overture_id,
                lon_hint - delta_lon, lon_hint + delta_lon,
                lat_hint - delta_lat, lat_hint + delta_lat,
            ],
        ).fetchall()
    else:
        # Full scan — slow but correct
        rows = conn.execute(
            f"""
            SELECT {_SELECT_COLS}
            FROM read_parquet('{OVERTURE_BUILDINGS}', hive_partitioning=1)
            WHERE id = ?
            LIMIT 1
            """,
            [overture_id],
        ).fetchall()

    if not rows:
        return None
    return _row_to_dict(rows[0])


def nearby_buildings(
    lat: float, lon: float, radius_m: int = 200, limit: int = 10
) -> list[dict]:
    """Return buildings within radius_m metres of (lat, lon), nearest first.

    dist_m is included in each result so callers can filter by proximity.
    """
    conn = _get_conn()
    delta_lat, delta_lon = _meters_to_deg(radius_m, lat)

    rows = conn.execute(
        f"""
        WITH candidates AS (
            SELECT {_SELECT_COLS},
                ROUND(ST_Distance(
                    ST_Transform(geometry, 'EPSG:4326', 'EPSG:3857'),
                    ST_Transform(ST_Point(?, ?), 'EPSG:4326', 'EPSG:3857')
                ), 1) AS dist_m
            FROM read_parquet('{OVERTURE_BUILDINGS}', hive_partitioning=1)
            WHERE bbox.xmin >= ? AND bbox.xmax <= ?
            AND bbox.ymin >= ? AND bbox.ymax <= ?
        )
        SELECT *
        FROM candidates
        WHERE dist_m <= ?
        ORDER BY dist_m
        LIMIT ?
        """,
        [
            lon, lat,
            lon - delta_lon, lon + delta_lon,
            lat - delta_lat, lat + delta_lat,
            float(radius_m),
            limit,
        ],
    ).fetchall()

    return [_row_to_dict(r) for r in rows]


# Road classes that form meaningful block boundaries (exclude minor paths)
_BLOCK_CLASSES = (
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "residential", "living_street", "unclassified", "pedestrian",
    "service",
)
_BLOCK_CLASS_LIST = ", ".join(f"'{c}'" for c in _BLOCK_CLASSES)


def nearby_segments(
    lat: float, lon: float, radius_m: int = 350, limit: int = 300
) -> list[dict]:
    """Return road segment LineStrings within radius_m metres of (lat, lon).

    Returns GeoJSON LineString geometries for the road network.
    Intended for client-side polygonization into city-block polygons.
    Excludes footpaths, steps, cycle lanes, and rail to keep block topology clean.
    """
    conn = _get_conn()
    delta_lat, delta_lon = _meters_to_deg(radius_m, lat)

    rows = conn.execute(
        f"""
        SELECT
            id,
            ST_AsGeoJSON(geometry) AS geometry_geojson,
            class,
            subtype
        FROM read_parquet('{OVERTURE_SEGMENTS}', hive_partitioning=1)
        WHERE bbox.xmin >= ? AND bbox.xmax <= ?
          AND bbox.ymin >= ? AND bbox.ymax <= ?
          AND subtype = 'road'
          AND class IN ({_BLOCK_CLASS_LIST})
        LIMIT ?
        """,
        [
            lon - delta_lon, lon + delta_lon,
            lat - delta_lat, lat + delta_lat,
            limit,
        ],
    ).fetchall()

    return [
        {"id": row[0], "geometry_geojson": row[1], "class": row[2], "subtype": row[3]}
        for row in rows
    ]
