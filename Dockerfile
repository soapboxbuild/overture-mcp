FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set PYTHONPATH before extension pre-install so DuckDB home is consistent at build + runtime
ENV PYTHONPATH=/app/src

# Pre-install DuckDB extensions so they don't need to download at runtime
RUN python3 -c "import duckdb; c=duckdb.connect(); c.execute('INSTALL httpfs; INSTALL spatial;'); print('DuckDB extensions installed')"

COPY src/ src/
COPY start.sh .

EXPOSE 8000

CMD ["sh", "start.sh"]
