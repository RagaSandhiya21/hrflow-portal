"""
Integration tests for authentication & the shared HR/IT Admin account model
(app/routers/auth.py). Requires a real Postgres test DB — see conftest.py;
auto-skipped if one isn't reachable.
"""


def test_dev_mock_login_succeeds_for_active_employee(client, seeded):
    res = client.post("/auth/login", json={"email": seeded.employee.email})
    assert res.status_code == 200
    body = res.json()
    assert body["employee"]["role"] == "employee"
    assert body["employee"]["is_shared_admin"] is False


def test_dev_mock_login_rejects_unknown_email(client, seeded):
    res = client.post("/auth/login", json={"email": "nobody@nowhere.com"})
    assert res.status_code == 401


def test_shared_hr_admin_login_has_no_personal_data_and_logs_access(client, seeded, db_session):
    """The core of the requested fix: logging into the shared HR Admin
    account must not expose (or require) any personal employee data, and
    must record who actually logged in for accountability."""
    res = client.post("/auth/login", json={"email": seeded.hr_admin.email})
    assert res.status_code == 200
    body = res.json()
    assert body["employee"]["is_shared_admin"] is True
    assert body["employee"]["employee_code"] == "HRADMIN"

    from app.models import AdminAccountAccessLog
    logs = db_session.query(AdminAccountAccessLog).filter(
        AdminAccountAccessLog.admin_employee_id == seeded.hr_admin.employee_id
    ).all()
    assert len(logs) == 1
    assert logs[0].acting_email == seeded.hr_admin.email


def test_get_me_requires_bearer_token(client, seeded):
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_get_me_returns_current_identity(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == seeded.employee.email


def test_expired_or_tampered_token_rejected(client, seeded):
    token = seeded.token_for(seeded.employee)
    tampered = token[:-3] + ("xyz" if not token.endswith("xyz") else "abc")
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert res.status_code == 401


def test_cross_role_endpoint_access_denied(client, seeded):
    """An employee must not be able to reach an hr_admin-only endpoint."""
    token = seeded.token_for(seeded.employee)
    res = client.post(
        "/org/departments",
        json={"department_name": "New Dept", "department_code": "NEW"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_shared_admin_account_blocked_from_personal_leave_endpoint(client, seeded):
    """A shared admin account has no personal HR record, so personal-data
    endpoints (require_personal_employee) must reject it."""
    token = seeded.token_for(seeded.hr_admin)
    res = client.get("/leave/balances", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
