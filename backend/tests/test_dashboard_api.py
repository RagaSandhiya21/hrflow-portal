"""
Integration tests for app/routers/dashboard.py — previously had zero
dedicated test coverage.
"""
from datetime import date


def test_employee_dashboard_summary_shape(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.get("/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["employee"]["employee_id"] == seeded.employee.employee_id
    assert body["leave_balances"] == []          # no leave types seeded in this fixture
    assert body["pending_leave_requests"] == 0
    assert body["open_hr_requests"] == 0
    assert body["open_it_requests"] == 0
    assert body["pending_approvals"] == 0        # plain employees never have approvals
    assert body["pending_change_requests"] == 0  # only populated for HR Admin


def test_manager_sees_pending_leave_approvals_count(client, seeded, db_session):
    from datetime import datetime
    from app.models import LeaveType, LeaveRequest
    lt = LeaveType(org_id=seeded.org.org_id, leave_type_name="Casual Leave", leave_code="CL", annual_quota=10)
    db_session.add(lt); db_session.flush()
    db_session.add(LeaveRequest(
        employee_id=seeded.employee.employee_id, leave_type_id=lt.leave_type_id,
        start_date=date.today(), end_date=date.today(), number_of_days=1, status="pending",
        applied_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    ))
    db_session.commit()

    manager_token = seeded.token_for(seeded.manager)
    res = client.get("/dashboard/summary", headers={"Authorization": f"Bearer {manager_token}"})
    assert res.status_code == 200, res.text
    assert res.json()["pending_approvals"] == 1


def test_hr_admin_sees_pending_profile_change_requests_count(client, seeded, db_session):
    from app.models import ProfileChangeRequest
    db_session.add(ProfileChangeRequest(
        employee_id=seeded.employee.employee_id, field_group="bank",
        field_name="bank_account_number", old_value="1234", new_value="5678", status="pending",
        requested_at=date.today(),
    ))
    db_session.commit()

    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.get("/dashboard/summary", headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 200, res.text
    assert res.json()["pending_change_requests"] == 1


def test_dashboard_reflects_open_hr_and_it_request_counts(client, seeded, db_session):
    from datetime import datetime
    from app.models import HRRequestCategory, HRRequest, ITRequest
    cat = HRRequestCategory(category_name="Document Request", default_priority="normal", sla_hours=48)
    db_session.add(cat); db_session.flush()
    db_session.add(HRRequest(
        employee_id=seeded.employee.employee_id, category_id=cat.category_id,
        subject="x", description="d", status="open",
        raised_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    ))
    db_session.add(ITRequest(
        employee_id=seeded.employee.employee_id, request_type="hardware_issue",
        subject="x", description="d", status="open",
        raised_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    ))
    db_session.commit()

    token = seeded.token_for(seeded.employee)
    res = client.get("/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["open_hr_requests"] == 1
    assert body["open_it_requests"] == 1


def test_dashboard_requires_authentication(client):
    res = client.get("/dashboard/summary")
    assert res.status_code == 401
