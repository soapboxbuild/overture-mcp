#!/bin/sh
set -e
echo "=== Overture MCP Starting ==="
echo "PORT=${PORT:-8000}, PYTHONPATH=$PYTHONPATH, PWD=$PWD"
echo "Python: $(python3 --version)"
echo "Testing imports..."
python3 -c "from overture_mcp.server import app; print('Import OK:', app)"
echo "Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn overture_mcp.server:app --host 0.0.0.0 --port "${PORT:-8000}" --log-level info
