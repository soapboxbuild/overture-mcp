FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for DuckDB spatial
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ src/
COPY pyproject.toml .

# Install the package itself
RUN pip install --no-cache-dir -e .

# DuckDB will cache extensions here
ENV DUCKDB_HOME=/tmp/duckdb_home

EXPOSE 8000

CMD ["uvicorn", "src.overture_mcp.server:app", "--host", "0.0.0.0", "--port", "8000"]
