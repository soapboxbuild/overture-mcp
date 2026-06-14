import os
import uvicorn
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

port = int(os.environ.get("PORT", 8000))
print(f"Starting Overture MCP on port {port}")

# Import AFTER we know the port so any import-time prints appear first
from overture_mcp.server import mcp, BearerAuthMiddleware
from starlette.middleware import Middleware

# Build the MCP app directly — uvicorn must own its lifespan (not a wrapper)
app = mcp.streamable_http_app()

# Inject health route before MCP routes so it short-circuits before auth
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})

app.router.routes.insert(0, Route("/health", health))

# Run directly — uvicorn properly handles FastMCP's task-group lifespan
uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
