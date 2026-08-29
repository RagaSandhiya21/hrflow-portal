"""
Integration tests for app/routers/it_requests.py — previously had zero
dedicated test coverage.
"""


def _it_admin(db_session, org_id, dept_id):
    from datetime import datetime
    from app.models import Employee
    it_admin = Employee(
        org_id=org_id, employee_code="ITADMIN", entra_object_id=None,
        email="it.admin@test.com", full_name="IT Admin", first_name="IT", last_name="Admin",
        department_id=dept_id, role="it_admin", is_shared_admin=True,
        entra_group_id="test-it-group", is_active=True,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    db_session.add(it_admin); db_session.commit()
    return it_admin


def test_employee_can_raise_and_view_own_it_request(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.post(
        "/it-requests",
        json={"request_type": "hardware_issue", "subject": "Laptop won't turn on",
              "description": "Black screen since this morning.", "priority": "high"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201, res.text
    req_id = res.json()["it_request_id"]
    assert res.json()["status"] == "open"

    mine_res = client.get("/it-requests", headers={"Authorization": f"Bearer {token}"})
    assert any(r["it_request_id"] == req_id for r in mine_res.json())


def test_it_admin_can_see_queue_hr_admin_can_view_readonly(client, seeded, db_session):
    """Per Module 7: 'HR Admin can view IT requests in read-only mode for
    cross-function visibility' — HR Admin should be able to hit the /queue
    endpoint (a GET), even though only IT Admin can change status."""
    it_admin = _it_admin(db_session, seeded.org.org_id, seeded.dept.department_id)
    token = seeded.token_for(seeded.employee)
    hr_token = seeded.token_for(seeded.hr_admin)
    it_token = seeded.token_for(it_admin)

    create_res = client.post("/it-requests",
                              json={"request_type": "software_install", "subject": "Need VS Code",
                                    "description": "For development work."},
                              headers={"Authorization": f"Bearer {token}"})
    req_id = create_res.json()["it_request_id"]

    it_queue = client.get("/it-requests/queue", headers={"Authorization": f"Bearer {it_token}"})
    assert it_queue.status_code == 200
    assert any(r["it_request_id"] == req_id for r in it_queue.json())

    hr_queue = client.get("/it-requests/queue", headers={"Authorization": f"Bearer {hr_token}"})
    assert hr_queue.status_code == 200


def test_employee_cannot_see_it_queue(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.get("/it-requests/queue", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_full_it_request_lifecycle_raise_progress_resolve(client, seeded, db_session):
    from app.models import ITRequestStatusHistory
    it_admin = _it_admin(db_session, seeded.org.org_id, seeded.dept.department_id)
    token = seeded.token_for(seeded.employee)
    it_token = seeded.token_for(it_admin)

    create_res = client.post("/it-requests",
                              json={"request_type": "access_provisioning", "subject": "Need VPN access",
                                    "description": "Working remote next week."},
                              headers={"Authorization": f"Bearer {token}"})
    req_id = create_res.json()["it_request_id"]

    progress_res = client.patch(f"/it-requests/{req_id}/status",
                                 json={"status": "in_progress", "notes": "Provisioning VPN cert."},
                                 headers={"Authorization": f"Bearer {it_token}"})
    assert progress_res.status_code == 200, progress_res.text
    assert progress_res.json()["status"] == "in_progress"

    resolve_res = client.patch(f"/it-requests/{req_id}/status",
                                json={"status": "resolved", "notes": "VPN access granted."},
                                headers={"Authorization": f"Bearer {it_token}"})
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "resolved"

    history = (
        db_session.query(ITRequestStatusHistory)
        .filter(ITRequestStatusHistory.it_request_id == req_id)
        .order_by(ITRequestStatusHistory.changed_at.asc())
        .all()
    )
    # open -> in_progress -> resolved: 1 (creation) + 2 (status changes) = 3 rows
    assert len(history) == 3
    assert history[-1].new_status == "resolved"


def test_employee_cannot_update_it_request_status(client, seeded):
    token = seeded.token_for(seeded.employee)
    create_res = client.post("/it-requests",
                              json={"request_type": "hardware_issue", "subject": "x", "description": "d"},
                              headers={"Authorization": f"Bearer {token}"})
    req_id = create_res.json()["it_request_id"]

    res = client.patch(f"/it-requests/{req_id}/status", json={"status": "resolved"},
                        headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_hr_admin_cannot_update_it_request_status(client, seeded, db_session):
    """HR Admin's IT-request access is explicitly read-only (queue view
    only, per Module 7) — status changes stay IT Admin-only."""
    token = seeded.token_for(seeded.employee)
    hr_token = seeded.token_for(seeded.hr_admin)
    create_res = client.post("/it-requests",
                              json={"request_type": "hardware_issue", "subject": "x", "description": "d"},
                              headers={"Authorization": f"Bearer {token}"})
    req_id = create_res.json()["it_request_id"]

    res = client.patch(f"/it-requests/{req_id}/status", json={"status": "resolved"},
                        headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 403


def test_invalid_status_value_rejected(client, seeded, db_session):
    it_admin = _it_admin(db_session, seeded.org.org_id, seeded.dept.department_id)
    token = seeded.token_for(seeded.employee)
    it_token = seeded.token_for(it_admin)
    create_res = client.post("/it-requests",
                              json={"request_type": "hardware_issue", "subject": "x", "description": "d"},
                              headers={"Authorization": f"Bearer {token}"})
    req_id = create_res.json()["it_request_id"]

    res = client.patch(f"/it-requests/{req_id}/status", json={"status": "not_a_real_status"},
                        headers={"Authorization": f"Bearer {it_token}"})
    assert res.status_code == 422
