"""Overture Maps MCP server with streamable HTTP transport.

Implements the MCP 2025-03-26 spec over streamable HTTP.
Auth: Bearer token from MCP_SERVER_SECRET env var.
Port: from PORT env var (default 8000).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from typing import Annotated

from mcp.server.transport_security import TransportSecuritySettings
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

import asyncio
import json

from overture_mcp import nominatim, overture

# ---------------------------------------------------------------------------
# MCP server definition
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Overture Maps",
    instructions=(
        "Tools for geocoding addresses and querying Overture Maps building "
        "footprint data from global OpenStreetMap-derived parquet files on S3."
    ),
    stateless_http=True,
    json_response=True,
    # Disable DNS-rebinding protection — this MCP is only called server-side
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
async def address_search(
    query: Annotated[str, "Free-text address or place name to geocode"],
    limit: Annotated[int, "Maximum number of results (1–20)"] = 5,
) -> list[dict]:
    """Search for addresses or places using Nominatim (OpenStreetMap).

    Returns a list of matches with display_name, lat, lon, importance, and type.
    Use this before get_building to turn a human address into coordinates.
    """
    return await nominatim.address_search(query, limit=limit)


@mcp.tool()
async def get_building(
    lat: Annotated[float, "Latitude (WGS84)"],
    lon: Annotated[float, "Longitude (WGS84)"],
    radius_m: Annotated[int, "Search radius in metres (default 100)"] = 100,
) -> dict | None:
    """Get the building at or nearest to a coordinate within radius_m metres.

    Queries Overture Maps global building dataset (~2.5B footprints).
    Returns the building that contains the point, or else the nearest one.

    Returns None if no building is found within the radius.

    Result includes: id, geometry_geojson, height, class, subtype, names,
    sources (with confidence), level, num_floors, facade/roof attributes.
    """
    return await asyncio.to_thread(overture.get_building, lat, lon, radius_m)


@mcp.tool()
async def get_building_by_id(
    overture_id: Annotated[str, "Overture GERS building ID"],
    lat_hint: Annotated[float | None, "Optional latitude hint for faster lookup"] = None,
    lon_hint: Annotated[float | None, "Optional longitude hint for faster lookup"] = None,
    radius_hint_m: Annotated[int, "Search radius around hint coords (default 5000m)"] = 5000,
) -> dict | None:
    """Fetch a specific building by its Overture GERS ID.

    WARNING: Without lat_hint + lon_hint this performs a full global scan
    and can take several minutes. Always provide coordinate hints when possible.

    Returns None if the building ID is not found.
    """
    return await asyncio.to_thread(
        overture.get_building_by_id, overture_id, lat_hint, lon_hint, radius_hint_m
    )


@mcp.tool()
async def nearby_buildings(
    lat: Annotated[float, "Latitude (WGS84)"],
    lon: Annotated[float, "Longitude (WGS84)"],
    radius_m: Annotated[int, "Search radius in metres (default 200)"] = 200,
    limit: Annotated[int, "Maximum number of buildings to return (default 10)"] = 10,
) -> list[dict]:
    """List buildings within radius_m metres of a coordinate, nearest first.

    Useful for finding all structures in an area — e.g., a city block,
    campus, or site boundary. Returns up to `limit` buildings sorted by
    distance from the query point.
    """
    return await asyncio.to_thread(overture.nearby_buildings, lat, lon, radius_m, limit)


@mcp.tool()
async def nearby_segments(
    lat: Annotated[float, "Latitude (WGS84)"],
    lon: Annotated[float, "Longitude (WGS84)"],
    radius_m: Annotated[int, "Search radius in metres (default 350)"] = 350,
    limit: Annotated[int, "Maximum number of segments to return (default 300)"] = 300,
) -> list[dict]:
    """Return road segment LineStrings within radius_m metres of a coordinate.

    Returns GeoJSON LineString geometries for the surrounding road network.
    Intended for client-side polygonization into city-block polygons.
    Each result includes: id, geometry_geojson (LineString), class, subtype.
    Footpaths, steps, cycleways, and rail are excluded.
    """
    return await asyncio.to_thread(overture.nearby_segments, lat, lon, radius_m, limit)


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------

MCP_SERVER_SECRET = os.getenv("MCP_SERVER_SECRET", "")


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Validate Authorization: Bearer <token> on all non-health routes."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Health check is always public
        if request.url.path == "/health":
            return await call_next(request)

        # If no secret is configured, allow all requests (dev mode)
        if not MCP_SERVER_SECRET:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"error": "Missing or invalid Authorization header"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header[len("Bearer "):]
        if token != MCP_SERVER_SECRET:
            return JSONResponse(
                {"error": "Invalid bearer token"},
                status_code=403,
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# Direct REST endpoints — bypass JSON-RPC for maximum throughput
# Returns flat JSON arrays with no MCP protocol wrapping.
# ---------------------------------------------------------------------------

def _parse_float(request: Request, key: str) -> float | None:
    v = request.query_params.get(key)
    try:
        return float(v) if v is not None else None
    except ValueError:
        return None

def _parse_int(request: Request, key: str, default: int) -> int:
    v = request.query_params.get(key)
    try:
        return int(v) if v is not None else default
    except ValueError:
        return default


async def rest_buildings(request: Request) -> Response:
    """GET /buildings?lat=&lon=&radius=&limit=
    Returns a flat JSON array of building dicts, nearest-first.
    Uses a single DuckDB scan — no MCP wrapper, no sequential fallback.
    """
    lat = _parse_float(request, "lat")
    lon = _parse_float(request, "lon")
    if lat is None or lon is None:
        return JSONResponse({"error": "lat and lon required"}, status_code=400)

    radius = _parse_int(request, "radius", 200)
    limit = _parse_int(request, "limit", 50)

    results = await asyncio.to_thread(overture.nearby_buildings, lat, lon, radius, limit)
    return Response(
        content=json.dumps(results),
        media_type="application/json",
    )


async def rest_segments(request: Request) -> Response:
    """GET /segments?lat=&lon=&radius=&limit=
    Returns a flat JSON array of road segment dicts for block polygonization.
    """
    lat = _parse_float(request, "lat")
    lon = _parse_float(request, "lon")
    if lat is None or lon is None:
        return JSONResponse({"error": "lat and lon required"}, status_code=400)

    radius = _parse_int(request, "radius", 350)
    limit = _parse_int(request, "limit", 300)

    results = await asyncio.to_thread(overture.nearby_segments, lat, lon, radius, limit)
    return Response(
        content=json.dumps(results),
        media_type="application/json",
    )


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# App assembly
# ---------------------------------------------------------------------------

mcp_starlette = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app: Starlette):
    # Forward lifespan to the inner MCP app so its task group initialises
    async with mcp_starlette.router.lifespan_context(mcp_starlette):
        yield


app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/health", health),
        Route("/buildings", rest_buildings),
        Route("/segments", rest_segments),
        Mount("/", app=mcp_starlette),
    ],
    middleware=[
        Middleware(BearerAuthMiddleware),
    ],
)
