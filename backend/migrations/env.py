"""
Alembic environment — wired to the same DATABASE_URL the app itself reads
(app.config.settings), so there's one source of truth for the connection
string, not a second copy hardcoded into alembic.ini.

Replaces the previous approach of applying db/schema.sql by hand via
`psql -f` / Postgres's docker-entrypoint-initdb.d — that worked for a fresh
container but gave no way to version, review, or incrementally evolve the
schema. From here on, `alembic upgrade head` is the only supported way to
apply schema changes (see migrations/versions/0001_baseline.py for how the
existing schema.sql was captured as the starting point).
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `app.*` importable when Alembic is invoked from backend/ (matches how
# the app itself is run, e.g. `uvicorn app.main:app` from the same directory).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402
import app.models  # noqa: E402,F401  (import registers all tables on Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Respect an explicitly-provided URL (e.g. a caller doing
# `alembic_cfg.set_main_option("sqlalchemy.url", ...)` before invoking
# Alembic programmatically, as the test suite does to target a scratch
# database) — only fall back to the app's own settings.DATABASE_URL when
# nothing more specific was supplied. Unconditionally overriding here was a
# real bug: it silently redirected every programmatic `command.upgrade()`
# call to whatever DATABASE_URL happened to be in the environment,
# regardless of what the caller asked for.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection (`alembic upgrade head --sql`)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    # NullPool means no connections are held between checkouts, but disposing
    # explicitly is cheap and removes any doubt — callers that immediately
    # DROP DATABASE the target right after (e.g. test fixtures) shouldn't see
    # a stale connection block that with "database is being accessed by
    # other users".
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
