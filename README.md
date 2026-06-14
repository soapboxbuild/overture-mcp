# Overture Maps MCP

Python MCP server (2025-03-26 spec, streamable HTTP) for querying
[Overture Maps](https://overturemaps.org/) building footprint data.

## Tools

| Tool | Description |
|------|-------------|
| `address_search(query, limit=5)` | Geocode addresses via Nominatim |
| `get_building(lat, lon, radius_m=100)` | Get building footprint at a coordinate |
| `get_building_by_id(id, lat_hint, lon_hint)` | Fetch building by Overture GERS ID |
| `nearby_buildings(lat, lon, radius_m=200, limit=10)` | List nearby buildings |

## Deployment

### Railway (recommended)

1. Fork this repo or connect it to Railway
2. Set environment variables:
   - `MCP_SERVER_SECRET` — bearer token for API auth
   - `PORT` — automatically set by Railway (default 8000)
3. Railway builds the Dockerfile and deploys

### Docker

```bash
docker build -t overture-mcp .
docker run -p 8000:8000 -e MCP_SERVER_SECRET=your-secret overture-mcp
```

### Local development

```bash
pip install -e ".[dev]"
uvicorn src.overture_mcp.server:app --reload
```

## API

- `GET /health` — health check (no auth required)
- `POST /mcp` — MCP streamable HTTP endpoint (requires `Authorization: Bearer <token>`)

## Auth

Set `MCP_SERVER_SECRET` to require a bearer token on all MCP requests.
Leave unset to disable auth (development only).

## Data

Queries the Overture Maps `2026-05-20.0` release (~2.5B buildings globally)
stored on AWS S3 (`s3://overturemaps-us-west-2`). DuckDB reads parquet files
directly — no data is downloaded to the server.

Each query uses a bounding-box predicate for partition pruning, so typical
requests scan only a small fraction of the dataset.

## Connecting to Claude

Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "overture-maps": {
      "transport": "streamable-http",
      "url": "https://your-deployment.railway.app/mcp",
      "headers": {
        "Authorization": "Bearer your-secret"
      }
    }
  }
}
```
