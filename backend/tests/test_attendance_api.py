"""
Integration tests for app/routers/attendance.py — previously had zero
dedicated test coverage (attendance was one of the routers named in the
mid-term doc's own coverage gap, alongside hr_requests/it_requests/
notifications/dashboard/payslips).
"""
from datetime import date, datetime


def test_employee_can_view_own_attendance(client, seeded, db_session):
    from app.models import AttendanceRecord
    today = date.today()
    db_session.add(AttendanceRecord(
        employee_id=seeded.employee.employee_id, attendance_date=today,
        status="present", check_in_time=datetime(today.year, today.month, today.day, 9, 30),
        check_out_time=datetime(today.year, today.month, today.day, 18, 30),
    ))
    db_session.commit()

    token = seeded.token_for(seeded.employee)
    res = client.get(f"/attendance/me?year={today.year}&month={today.month}",
                      headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    assert any(r["attendance_date"] == today.isoformat() for r in res.json())


def test_shared_admin_cannot_view_own_attendance(client, seeded):
    """Shared HR Admin/IT Admin accounts have no personal attendance —
    require_personal_employee should block this."""
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.get("/attendance/me", headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 403


def test_hr_admin_can_view_any_employees_attendance(client, seeded, db_session):
    from app.models import AttendanceRecord
    today = date.today()
    db_session.add(AttendanceRecord(
        employee_id=seeded.employee.employee_id, attendance_date=today, status="wfh",
    ))
    db_session.commit()

    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.get(f"/attendance/admin/{seeded.employee.employee_id}?year={today.year}&month={today.month}",
                      headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 200, res.text
    assert any(r["status"] == "wfh" for r in res.json())


def test_employee_cannot_view_admin_attendance_endpoint(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.get(f"/attendance/admin/{seeded.employee.employee_id}",
                      headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_hr_admin_can_directly_edit_attendance_with_audit_log(client, seeded, db_session):
    from app.models import AttendanceEditLog
    today = date.today()
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.post(
        "/attendance/admin/edit",
        json={
            "employee_id": seeded.employee.employee_id,
            "attendance_date": today.isoformat(),
            "new_status": "present",
            "reason": "Biometric device was down; confirmed via manager.",
        },
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "present"

    # A fresh record with no prior existing row shouldn't log an edit
    # (nothing to diff against) — but should still be created correctly.
    log_count = db_session.query(AttendanceEditLog).count()
    assert log_count == 0


def test_hr_admin_edit_of_existing_record_writes_audit_log(client, seeded, db_session):
    """The audit trail (Module 6 requirement) only fires when correcting an
    EXISTING attendance record, not when creating a fresh one — this is the
    case that previously silently failed to write anything (see
    app/models.py AttendanceEditLog docstring for why)."""
    from app.models import AttendanceRecord, AttendanceEditLog
    today = date.today()
    db_session.add(AttendanceRecord(
        employee_id=seeded.employee.employee_id, attendance_date=today, status="absent",
    ))
    db_session.commit()

    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.post(
        "/attendance/admin/edit",
        json={
            "employee_id": seeded.employee.employee_id,
            "attendance_date": today.isoformat(),
            "new_status": "present",
            "reason": "Biometric device was down; confirmed via manager.",
        },
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "present"

    log = db_session.query(AttendanceEditLog).filter(
        AttendanceEditLog.attendance_id == res.json()["attendance_id"]
    ).first()
    assert log is not None, "attendance correction must write an audit log entry"
    assert log.old_status == "absent"
    assert log.new_status == "present"
    assert log.edited_by == seeded.hr_admin.employee_id
    assert log.reason == "Biometric device was down; confirmed via manager."


def test_hr_admin_edit_rejects_invalid_status(client, seeded):
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.post(
        "/attendance/admin/edit",
        json={
            "employee_id": seeded.employee.employee_id,
            "attendance_date": date.today().isoformat(),
            "new_status": "on_vacation_forever",
            "reason": "bad status",
        },
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert res.status_code == 400


def test_employee_cannot_directly_edit_attendance(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.post(
        "/attendance/admin/edit",
        json={
            "employee_id": seeded.employee.employee_id,
            "attendance_date": date.today().isoformat(),
            "new_status": "present",
            "reason": "trying to self-edit",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_regularisation_request_and_manager_approval_flow(client, seeded):
    token = seeded.token_for(seeded.employee)
    create_res = client.post(
        "/attendance/regularisation",
        json={
            "attendance_date": date.today().isoformat(),
            "requested_status": "present",
            "reason": "Forgot to check in due to a client call.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_res.status_code == 201, create_res.text
    reg_id = create_res.json()["regularisation_id"]

    manager_token = seeded.token_for(seeded.manager)
    queue_res = client.get("/attendance/regularisation/queue",
                            headers={"Authorization": f"Bearer {manager_token}"})
    assert queue_res.status_code == 200
    assert any(r["regularisation_id"] == reg_id for r in queue_res.json())

    decision_res = client.post(
        f"/attendance/regularisation/{reg_id}/decision",
        json={"decision": "approved", "reviewer_comments": "Confirmed with client calendar."},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert decision_res.status_code == 200, decision_res.text
    assert decision_res.json()["status"] == "approved"


def test_regularisation_decision_cannot_be_applied_twice(client, seeded):
    token = seeded.token_for(seeded.employee)
    create_res = client.post(
        "/attendance/regularisation",
        json={"attendance_date": date.today().isoformat(), "requested_status": "present", "reason": "test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    reg_id = create_res.json()["regularisation_id"]

    manager_token = seeded.token_for(seeded.manager)
    client.post(f"/attendance/regularisation/{reg_id}/decision",
                json={"decision": "approved"},
                headers={"Authorization": f"Bearer {manager_token}"})

    second_res = client.post(f"/attendance/regularisation/{reg_id}/decision",
                              json={"decision": "rejected"},
                              headers={"Authorization": f"Bearer {manager_token}"})
    assert second_res.status_code == 400


def test_hr_admin_can_manage_holiday_calendar(client, seeded):
    hr_token = seeded.token_for(seeded.hr_admin)
    year = date.today().year
    res = client.post(
        "/attendance/holidays",
        json={"holiday_date": f"{year}-11-01", "holiday_name": "Test Holiday", "holiday_type": "public"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert res.status_code == 201, res.text
    holiday_id = res.json()["holiday_id"]

    list_res = client.get(f"/attendance/holidays?year={year}",
                           headers={"Authorization": f"Bearer {hr_token}"})
    assert any(h["holiday_id"] == holiday_id for h in list_res.json())

    delete_res = client.delete(f"/attendance/holidays/{holiday_id}",
                                headers={"Authorization": f"Bearer {hr_token}"})
    assert delete_res.status_code == 200


def test_employee_cannot_add_holiday(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.post(
        "/attendance/holidays",
        json={"holiday_date": "2027-01-01", "holiday_name": "New Year"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
