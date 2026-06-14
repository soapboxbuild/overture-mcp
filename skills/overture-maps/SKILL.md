# Overture Maps Skill

Use these tools when you need building footprint data, spatial analysis,
or need to geocode an address and retrieve its physical building shape.

## When to use

- User asks about a building's height, footprint, floor count, or structure class
- You need GeoJSON geometry for a building to do spatial calculations
- You need to find all buildings within a radius (campus, block, site)
- You are creating or enriching a building record and need Overture data
- You are computing carbon emissions, energy use, or area and need the footprint

## Workflow: address → building footprint

1. **Call `address_search`** with the human address first.
   - Returns lat/lon + display_name so you can confirm the right location.
2. **Call `get_building`** with the lat/lon from step 1.
   - Use `radius_m=100` for a point address; increase to 200–500 for vague locations.
   - Returns the building polygon (GeoJSON), height, num_floors, class/subtype.
3. If you already have an Overture ID (from a previous call or a database),
   use **`get_building_by_id`** with lat/lon hints for speed.

## Tool reference

### address_search(query, limit=5)
Geocodes a free-text address using Nominatim (OpenStreetMap).
- Returns: `[{display_name, lat, lon, importance, type}]`
- Always use this before `get_building` unless you already have coordinates.

### get_building(lat, lon, radius_m=100)
Finds the building at or nearest to a point within `radius_m` metres.
- Prefers buildings that *contain* the point (footprint match).
- Falls back to nearest building in the bounding box.
- Returns `None` if nothing found in the radius — try increasing `radius_m`.
- Key fields: `id`, `geometry_geojson` (Polygon/MultiPolygon), `height`,
  `class`, `subtype`, `num_floors`, `sources[].confidence`

### get_building_by_id(overture_id, lat_hint=None, lon_hint=None, radius_hint_m=5000)
Fetches a specific building by its Overture GERS ID.
- **Always provide lat_hint + lon_hint** — without them, the tool scans the
  global 2.5B-row dataset and may time out.
- Returns `None` if the ID is not found.

### nearby_buildings(lat, lon, radius_m=200, limit=10)
Returns up to `limit` buildings within `radius_m` metres, sorted by distance.
- Use for campus/block/site analysis.
- Keep `radius_m` under 1000 for reasonable response times.

## Tips

- The Overture dataset is updated monthly. The current release is baked into
  the server — no configuration needed.
- `class` and `subtype` follow the Overture buildings schema:
  subtype examples: `residential`, `commercial`, `industrial`, `agricultural`
  class examples: `house`, `apartments`, `office`, `retail`, `warehouse`
- `height` is in metres; `num_floors` is an integer (often null for older data).
- `geometry_geojson` is a GeoJSON string (Polygon or MultiPolygon, WGS84).
  Parse with `json.loads()` and pass to any GeoJSON-aware library.
- Confidence scores live in `sources[0].confidence` (0.0–1.0).
