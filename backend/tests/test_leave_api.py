"""
Integration tests for the leave workflow (apply -> persist -> manager
approves -> balance updates) — the proposal's Module 2 + QA §10.2
"Integration — Self-Service Workflows" requirement.
"""
from datetime import date, datetime, timedelta


def _next_weekday(d):
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def test_apply_approve_and_balance_persist_correctly(client, seeded, db_session):
    from app.models import LeaveType, EmployeeLeaveBalance

    leave_type = LeaveType(org_id=seeded.org.org_id, leave_type_name="Casual Leave",
                            leave_code="CL", annual_quota=10, carryover_allowed=False, half_day_allowed=True)
    db_session.add(leave_type); db_session.flush()

    year = date.today().year
    balance = EmployeeLeaveBalance(
        employee_id=seeded.employee.employee_id, leave_type_id=leave_type.leave_type_id,
        year=year, total_allotted=10, carried_over=0, used_days=0, pending_days=0,
        last_updated=datetime.utcnow(),
    )
    db_session.add(balance); db_session.commit()

    emp_token = seeded.token_for(seeded.employee)
    mgr_token = seeded.token_for(seeded.manager)

    start = _next_weekday(date.today() + timedelta(days=5))
    res = client.post(
        "/leave/requests",
        json={"leave_type_id": leave_type.leave_type_id, "start_date": str(start),
              "end_date": str(start), "reason": "Personal work", "is_half_day": False},
        headers={"Authorization": f"Bearer {emp_token}"},
    )
    assert res.status_code == 201, res.text
    leave_request_id = res.json()["leave_request_id"]
    assert res.json()["status"] == "pending"

    db_session.refresh(balance)
    assert float(balance.pending_days) == 1.0

    res = client.post(
        f"/leave/requests/{leave_request_id}/decision",
        json={"decision": "approved", "comments": "Approved"},
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "approved"

    db_session.refresh(balance)
    assert float(balance.pending_days) == 0.0
    assert float(balance.used_days) == 1.0

    # Persistence check: re-fetch from a fresh query, matching what was submitted.
    from app.models import LeaveRequest
    stored = db_session.query(LeaveRequest).filter(LeaveRequest.leave_request_id == leave_request_id).first()
    assert stored.status == "approved"
    assert stored.start_date == start


def test_manager_cannot_approve_non_direct_report(client, seeded, db_session):
    """Data-integrity guard: a manager can only act on their own reports' requests."""
    from app.models import Employee, LeaveType, EmployeeLeaveBalance, LeaveRequest

    other_manager = Employee(
        org_id=seeded.org.org_id, employee_code="M2", entra_object_id="oid-m2",
        email="othermanager@test.com", full_name="Other Manager", first_name="Other", last_name="Manager",
        department_id=seeded.dept.department_id, role="manager", is_active=True,
        created_at=__import__("datetime").datetime.utcnow(), updated_at=__import__("datetime").datetime.utcnow(),
    )
    db_session.add(other_manager); db_session.flush()

    leave_type = LeaveType(org_id=seeded.org.org_id, leave_type_name="Sick Leave",
                            leave_code="SL", annual_quota=10, carryover_allowed=False, half_day_allowed=True)
    db_session.add(leave_type); db_session.flush()

    lr = LeaveRequest(
        employee_id=seeded.employee.employee_id, leave_type_id=leave_type.leave_type_id,
        start_date=date.today(), end_date=date.today(), number_of_days=1,
        reason="x", status="pending", applied_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    db_session.add(lr); db_session.commit()

    token = seeded.token_for(other_manager)
    res = client.post(
        f"/leave/requests/{lr.leave_request_id}/decision",
        json={"decision": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_employee_cannot_view_another_employees_payslip(client, seeded, db_session):
    """Cross-user record access must be denied (403) — QA §10.4 data validation requirement."""
    from app.models import Employee, MonthlyPayroll, Payslip

    other = Employee(
        org_id=seeded.org.org_id, employee_code="E2", entra_object_id="oid-e2",
        email="other@test.com", full_name="Other Employee", first_name="Other", last_name="Employee",
        department_id=seeded.dept.department_id, role="employee", is_active=True,
        created_at=__import__("datetime").datetime.utcnow(), updated_at=__import__("datetime").datetime.utcnow(),
    )
    db_session.add(other); db_session.flush()

    payroll = MonthlyPayroll(employee_id=other.employee_id, payroll_month=date.today().replace(day=1),
                              basic_salary=30000, hra=12000, transport_allowance=1600)
    db_session.add(payroll); db_session.flush()
    payslip = Payslip(employee_id=other.employee_id, payroll_id=payroll.payroll_id,
                       payslip_month=date.today().replace(day=1), pdf_path="x.pdf", is_published=True,
                       generated_at=datetime.utcnow())
    db_session.add(payslip); db_session.commit()

    token = seeded.token_for(seeded.employee)
    res = client.get(f"/payslips/{payslip.payslip_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
