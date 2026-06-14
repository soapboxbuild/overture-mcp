FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-install DuckDB extensions so they don't need to download at runtime
RUN python3 -c "import duckdb; c=duckdb.connect(); c.execute('INSTALL httpfs; INSTALL spatial;'); print('DuckDB extensions installed')"

COPY src/ src/

ENV DUCKDB_HOME=/tmp/duckdb_home
ENV PYTHONPATH=/app

EXPOSE 8000

# Shell form so $PORT is expanded
CMD uvicorn src.overture_mcp.server:app --host 0.0.0.0 --port ${PORT:-8000}
