---
name: overture-maps
description: >
  Use when working with property addresses, building locations, or spatial data.
  Geocodes addresses to coordinates and fetches building footprints (GeoJSON polygons
  with height, floors, class) from Overture Maps — 2.3B+ global buildings.
  Triggers on: address lookup, building footprint, property location, geocode,
  "find the building at", "get coordinates for", creating a new asset, spatial analysis.
version: 1.1.0
requires:
  - overture-maps-mcp
---

# Overture Maps

Use the Overture Maps tools for address resolution and building geometry.

---

## address_search(query)

Geocode a free-text address to coordinates using Nominatim (OpenStreetMap).

**When to use:** Any time a user mentions an address, property location, or asks to find a building.

**Returns:** Ranked list of `{ display_name, lat, lon, importance, type }`.

Always use this first before `get_building` when starting from an address string.

---

## get_building(lat, lon, radius_m=100)

Fetch the building footprint at a coordinate from the Overture Maps dataset.

**When to use:**
- Creating a new asset — get the footprint immediately after geocoding the address
- Spatial analysis — calculating floor plate size, orientation, footprint area
- Verifying a property location

**Returns:** `{ id, geometry_geojson, height_m, num_floors, class, subtype, primary_name, source }`

The `geometry_geojson` is a GeoJSON Polygon — use it for display or area calculations.

---

## nearby_buildings(lat, lon, radius_m=200, limit=10)

List buildings near a coordinate, sorted by distance.

**When to use:**
- Site context — "what's around this building?"
- Density analysis
- Finding adjacent properties

---

## Workflow: create a new asset

```
1. address_search(user_provided_address)
   → select best candidate → lat, lon

2. get_building(lat, lon)
   → GeoJSON polygon, height, floor count, class

3. Present findings to user:
   "Found: [building name] at [address]
    Height: [X]m, Floors: [N], Class: [office/residential/etc.]
    Footprint: [area]m²"

4. On confirmation → create asset with coordinates stored
```

---

## Rules

- Always call address_search before get_building when starting from text
- If get_building returns null (no footprint found), inform the user — not all buildings are in Overture yet
- Use the Overture `id` (GERS ID) to reference buildings across tool calls
- Heights and floor counts come from Overture's community data — flag if missing
