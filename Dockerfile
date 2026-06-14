FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

ENV DUCKDB_HOME=/tmp/duckdb_home
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "src.overture_mcp.server:app", "--host", "0.0.0.0", "--port", "8000"]
