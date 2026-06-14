FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Force unbuffered output so logs appear in Railway even if container crashes
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Pre-install DuckDB extensions so they don't need to download at runtime
RUN python3 -c "import duckdb; c=duckdb.connect(); c.execute('INSTALL httpfs; INSTALL spatial;'); print('DuckDB extensions installed')"

COPY src/ src/
COPY run.py .

# Verify the server imports correctly at build time
RUN python3 -c "from overture_mcp.server import app; print('Server import OK:', app)"

EXPOSE 8000

CMD ["python3", "run.py"]
