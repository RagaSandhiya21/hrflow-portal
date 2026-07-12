# HRFlow backend — FastAPI (per RFP §Infrastructure: "Backend API running in Docker")
FROM python:3.11-slim

WORKDIR /app

# psycopg2-binary needs libpq at build time on slim images; keep the image
# small by cleaning apt lists afterward.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

# Container-internal port — mapped to the host in docker-compose.yml
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

# entrypoint.sh waits for the DB, runs `alembic upgrade head` (applying the
# baseline schema + any migrations layered on top), then starts uvicorn —
# see migrations/versions/0001_baseline_schema.py for how this replaced the
# old docker-entrypoint-initdb.d approach.
CMD ["./entrypoint.sh"]
