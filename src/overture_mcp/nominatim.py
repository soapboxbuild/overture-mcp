"""Nominatim address search via OpenStreetMap."""

from __future__ import annotations

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "overture-mcp/1.0 (github.com/soapboxbuild/overture-mcp)"


async def address_search(query: str, limit: int = 5) -> list[dict]:
    """Search for addresses using Nominatim.

    Args:
        query: Free-text address query.
        limit: Maximum number of results (default 5).

    Returns:
        List of dicts with display_name, lat, lon, importance, type.
    """
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": min(limit, 20),
        "addressdetails": "0",
    }
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=10.0
    ) as client:
        resp = client.build_request("GET", NOMINATIM_URL, params=params)
        response = await client.send(resp)
        response.raise_for_status()
        data = response.json()

    results = []
    for item in data:
        results.append(
            {
                "display_name": item.get("display_name", ""),
                "lat": float(item.get("lat", 0)),
                "lon": float(item.get("lon", 0)),
                "importance": item.get("importance", 0),
                "type": item.get("type", ""),
                "osm_type": item.get("osm_type", ""),
                "place_id": item.get("place_id"),
            }
        )
    return results
