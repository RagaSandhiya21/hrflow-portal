#!/bin/sh
# Applies any pending Alembic migrations (including the baseline schema on a
# brand-new database) before starting the API — replaces the old approach of
# Postgres auto-running db/schema.sql once via docker-entrypoint-initdb.d,
# which had no version history and no way to layer on future schema changes.
set -e

echo "Waiting for database..."
python3 - <<'PYEOF'
import os, time
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
for attempt in range(30):
    try:
        create_engine(url).connect().close()
        print("Database is ready.")
        break
    except Exception as e:
        print(f"  ...not ready yet ({e.__class__.__name__}), retrying")
        time.sleep(2)
else:
    raise SystemExit("Database never became ready after 60s")
PYEOF

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
