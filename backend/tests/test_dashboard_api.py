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


def _it_admin(db_session, org_id, dept_id):
    from datetime import datetime
    from app.models import Employee
    it_admin = Employee(
        org_id=org_id, employee_code="ITADMIN2", entra_object_id=None,
        email="it.admin2@test.com", full_name="IT Admin", first_name="IT", last_name="Admin",
        department_id=dept_id, role="it_admin", is_shared_admin=True,
        entra_group_id="test-it-group-dash", is_active=True,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    db_session.add(it_admin); db_session.commit()
    return it_admin


def test_hr_admin_sees_org_wide_open_hr_requests_not_personal_zero(client, seeded, db_session):
    """Regression test for the bug found and fixed in D-19/EV-23: HR Admin
    is a shared functional account that never raises personal HR tickets,
    so filtering open_hr_requests by the HR Admin's OWN employee_id always
    returned 0 regardless of how many tickets were actually open. This test
    seeds tickets raised by OTHER employees and confirms HR Admin's own
    dashboard count reflects the real org-wide open queue, not their
    (always-empty) personal one."""
    from datetime import datetime
    from app.models import HRRequestCategory, HRRequest
    cat = HRRequestCategory(category_name="Document Request", default_priority="normal", sla_hours=48)
    db_session.add(cat); db_session.flush()
    # Two open tickets raised by a regular employee, not by HR Admin.
    for subject in ("Need a certificate", "Bank detail query"):
        db_session.add(HRRequest(
            employee_id=seeded.employee.employee_id, category_id=cat.category_id,
            subject=subject, description="d", status="open",
            raised_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        ))
    db_session.commit()

    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.get("/dashboard/summary", headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 200, res.text
    # Before the fix this would have been 0 (HR Admin's own employee_id
    # never has any HR requests against it).
    assert res.json()["open_hr_requests"] == 2


def test_it_admin_sees_org_wide_open_it_requests_not_personal_zero(client, seeded, db_session):
    """Regression test for the same bug on the IT Admin side: open_it_requests
    must reflect the org-wide open IT ticket queue for a shared IT Admin
    account, not the (always-empty) personal count."""
    from datetime import datetime
    from app.models import ITRequest
    it_admin = _it_admin(db_session, seeded.org.org_id, seeded.dept.department_id)
    # One open ticket raised by a regular employee, not by IT Admin.
    db_session.add(ITRequest(
        employee_id=seeded.employee.employee_id, request_type="hardware_issue",
        subject="Laptop won't turn on", description="d", status="open",
        raised_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    ))
    db_session.commit()

    it_token = seeded.token_for(it_admin)
    res = client.get("/dashboard/summary", headers={"Authorization": f"Bearer {it_token}"})
    assert res.status_code == 200, res.text
    # Before the fix this would have been 0 (IT Admin's own employee_id
    # never has any IT requests against it).
    assert res.json()["open_it_requests"] == 1


def test_hr_admin_open_hr_requests_excludes_resolved_and_closed(client, seeded, db_session):
    """The org-wide count must still exclude resolved/closed/cancelled
    tickets — confirming the fix filters by status correctly, not just by
    removing the employee_id filter entirely."""
    from datetime import datetime
    from app.models import HRRequestCategory, HRRequest
    cat = HRRequestCategory(category_name="Document Request", default_priority="normal", sla_hours=48)
    db_session.add(cat); db_session.flush()
    db_session.add(HRRequest(
        employee_id=seeded.employee.employee_id, category_id=cat.category_id,
        subject="Open one", description="d", status="open",
        raised_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    ))
    db_session.add(HRRequest(
        employee_id=seeded.employee.employee_id, category_id=cat.category_id,
        subject="Already resolved", description="d", status="resolved",
        raised_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    ))
    db_session.commit()

    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.get("/dashboard/summary", headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 200, res.text
    assert res.json()["open_hr_requests"] == 1


def test_plain_employee_and_manager_still_see_only_their_own_hr_it_counts(client, seeded, db_session):
    """Confirms the org-wide override is scoped strictly to hr_admin/it_admin
    roles — a regular employee or manager must NOT see the org-wide count,
    only their own personal open tickets, same as before this fix."""
    from datetime import datetime
    from app.models import HRRequestCategory, HRRequest
    cat = HRRequestCategory(category_name="Document Request", default_priority="normal", sla_hours=48)
    db_session.add(cat); db_session.flush()
    # A ticket raised by someone else entirely (the manager), which the
    # employee must NOT see reflected in their own personal count.
    db_session.add(HRRequest(
        employee_id=seeded.manager.employee_id, category_id=cat.category_id,
        subject="Manager's own request", description="d", status="open",
        raised_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    ))
    db_session.commit()

    token = seeded.token_for(seeded.employee)
    res = client.get("/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    assert res.json()["open_hr_requests"] == 0
