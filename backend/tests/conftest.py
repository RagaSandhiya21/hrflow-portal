"""
Test fixtures.

Integration tests need a real Postgres database (the schema uses
Postgres-specific features — generated/computed columns, ARRAY columns,
CHECK constraints — that don't translate to SQLite). They run against
TEST_DATABASE_URL (default: a local `hrflow_test` DB) and are automatically
skipped if that database isn't reachable, so `pytest` still runs the
pure-unit-test suite (security/deps/rag_pipeline/payslip_pdf) anywhere.

CI (.github/workflows/ci.yml) spins up a real Postgres service container
and points TEST_DATABASE_URL at it, so integration tests always run there.

Schema setup runs through Alembic (`alembic upgrade head`), not a direct
`schema.sql` execution — this means every test run also exercises the same
migration path used in production (see migrations/versions/
0001_baseline_schema.py), rather than assuming it works.
"""
import os
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://hrflow_user:hrflow_pass@localhost:5432/hrflow_test",
)

os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("USE_MOCK_SSO", "true")

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")


def _db_reachable(url: str) -> bool:
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def db_available():
    return _db_reachable(TEST_DATABASE_URL)


@pytest.fixture(scope="session", autouse=True)
def _prepare_schema(db_available):
    """Runs `alembic upgrade head` against the test DB once per session —
    idempotent, since Alembic tracks the applied revision in alembic_version
    and no-ops if everything is already up to date."""
    if not db_available:
        yield
        return
    alembic_cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(alembic_cfg, "head")
    yield


@pytest.fixture()
def db_session(db_available):
    if not db_available:
        pytest.skip(f"Test Postgres DB not reachable at {TEST_DATABASE_URL} — skipping integration test.")
    from app.database import Base
    engine = create_engine(TEST_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Wipe all app tables between tests for isolation (cheap enough for the
    # small schema here; TRUNCATE ... CASCADE handles FK ordering for us).
    with engine.connect() as conn:
        tables = conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        )).scalars().all()
        if tables:
            conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
            conn.commit()
    yield session
    session.close()


@pytest.fixture()
def seeded(db_session):
    """
    Minimal fixture data for integration tests: one org, one department, one
    real manager + employee, and one SHARED hr_admin account (is_shared_admin
    = True, no personal fields) — mirroring the real seed.py structure so
    tests exercise the same shared-admin model the app runs in production.
    """
    from app.models import Organisation, Department, Employee
    from app.security import create_access_token
    from datetime import datetime

    org = Organisation(org_name="Test Org", org_code="TESTORG", currency_code="INR")
    db_session.add(org); db_session.flush()

    dept = Department(org_id=org.org_id, department_name="Engineering", department_code="ENG")
    db_session.add(dept); db_session.flush()

    now = datetime.utcnow()
    manager = Employee(
        org_id=org.org_id, employee_code="M1", entra_object_id="oid-m1",
        email="manager@test.com", full_name="Test Manager", first_name="Test", last_name="Manager",
        department_id=dept.department_id, role="manager", is_active=True,
        created_at=now, updated_at=now,
    )
    employee = Employee(
        org_id=org.org_id, employee_code="E1", entra_object_id="oid-e1",
        email="employee@test.com", full_name="Test Employee", first_name="Test", last_name="Employee",
        department_id=dept.department_id, role="employee", is_active=True,
        created_at=now, updated_at=now,
    )
    hr_admin = Employee(
        org_id=org.org_id, employee_code="HRADMIN", entra_object_id=None,
        email="hr.admin@test.com", full_name="HR Admin", first_name="HR", last_name="Admin",
        department_id=dept.department_id, role="hr_admin", is_shared_admin=True,
        entra_group_id="test-hr-group", is_active=True,
        created_at=now, updated_at=now,
    )
    db_session.add_all([manager, employee, hr_admin])
    db_session.flush()
    employee.manager_id = manager.employee_id
    db_session.commit()

    def token_for(emp):
        return create_access_token(emp.employee_id, emp.role, emp.email, is_shared_admin=emp.is_shared_admin)

    return SimpleNamespace(org=org, dept=dept, manager=manager, employee=employee,
                           hr_admin=hr_admin, token_for=token_for)


@pytest.fixture()
def client(db_session, monkeypatch):
    """FastAPI TestClient wired to the same test DB session/engine."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
