import os
import uvicorn

port = int(os.environ.get("PORT", 8000))
print(f"Starting Overture MCP on port {port}")
uvicorn.run("overture_mcp.server:app", host="0.0.0.0", port=port, log_level="info")
