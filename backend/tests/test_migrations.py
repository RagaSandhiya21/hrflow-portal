"""
Regression test for the Alembic migration path itself (Wk 4 deliverable:
"Alembic DB migrations", replacing the old ad-hoc `psql -f schema.sql`
approach). Applies the baseline migration to a throwaway database and
confirms it lands in a sane, fully-versioned state — independent of
whatever conftest.py's session-scoped fixture already did for the shared
test DB, so this catches migration-script regressions specifically.
"""
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_MIGRATION_TESTS"),
    reason="Creates/drops its own database — opt in with RUN_MIGRATION_TESTS=1 "
           "to avoid surprising a shared CI Postgres instance.",
)

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
ADMIN_URL = os.environ.get(
    "TEST_DATABASE_ADMIN_URL",
    "postgresql+psycopg2://hrflow_user:hrflow_pass@localhost:5432/postgres",
)
SCRATCH_DB = "hrflow_migration_scratch"
SCRATCH_URL = ADMIN_URL.rsplit("/", 1)[0] + f"/{SCRATCH_DB}"


@pytest.fixture()
def scratch_db():
    admin_engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH_DB}"))
        conn.execute(text(f"CREATE DATABASE {SCRATCH_DB}"))
    admin_engine.dispose()
    yield SCRATCH_URL
    admin_engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH_DB}"))
    admin_engine.dispose()


def _alembic_config(db_url: str) -> Config:
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_alembic_upgrade_head_creates_full_schema(scratch_db):
    command.upgrade(_alembic_config(scratch_db), "head")

    engine = create_engine(scratch_db)
    with engine.connect() as conn:
        table_count = conn.execute(text(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
        )).scalar()
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    engine.dispose()

    assert table_count > 50  # the full 53-table schema, plus alembic_version
    assert version == "0001"


def test_alembic_upgrade_head_is_idempotent(scratch_db):
    """Running `alembic upgrade head` twice must not error — this is exactly
    what happens on every container restart against an already-migrated DB."""
    cfg = _alembic_config(scratch_db)
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")  # must be a no-op, not an error


def test_alembic_downgrade_drops_everything(scratch_db):
    cfg = _alembic_config(scratch_db)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = create_engine(scratch_db)
    with engine.connect() as conn:
        table_count = conn.execute(text(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
        )).scalar()
        version_rows = conn.execute(text("SELECT count(*) FROM alembic_version")).scalar()
    engine.dispose()
    # alembic_version itself is expected to survive (Alembic manages its own
    # lifecycle) — but empty, and every app table this baseline created must
    # be gone.
    assert table_count == 1
    assert version_rows == 0
