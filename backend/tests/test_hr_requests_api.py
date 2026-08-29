"""
Integration tests for app/routers/hr_requests.py — previously had zero
dedicated test coverage.
"""


def _make_category(db_session):
    from app.models import HRRequestCategory
    cat = HRRequestCategory(category_name="Document Request", default_priority="normal", sla_hours=48)
    db_session.add(cat); db_session.commit()
    return cat


def test_employee_can_raise_and_view_own_hr_request(client, seeded, db_session):
    cat = _make_category(db_session)
    token = seeded.token_for(seeded.employee)
    res = client.post(
        "/hr-requests",
        json={"category_id": cat.category_id, "subject": "Need a salary certificate",
              "description": "For a visa application.", "priority": "normal"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201, res.text
    req_id = res.json()["hr_request_id"]
    assert res.json()["category_name"] == "Document Request"

    mine_res = client.get("/hr-requests", headers={"Authorization": f"Bearer {token}"})
    assert any(r["hr_request_id"] == req_id for r in mine_res.json())


def test_raising_request_with_unknown_category_fails(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.post(
        "/hr-requests",
        json={"category_id": 999999, "subject": "x", "description": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


def test_hr_admin_sees_open_requests_in_queue_but_not_resolved(client, seeded, db_session):
    cat = _make_category(db_session)
    token = seeded.token_for(seeded.employee)
    hr_token = seeded.token_for(seeded.hr_admin)

    open_res = client.post("/hr-requests",
                            json={"category_id": cat.category_id, "subject": "Open one", "description": "d"},
                            headers={"Authorization": f"Bearer {token}"})
    open_id = open_res.json()["hr_request_id"]

    resolved_res = client.post("/hr-requests",
                                json={"category_id": cat.category_id, "subject": "Resolved one", "description": "d"},
                                headers={"Authorization": f"Bearer {token}"})
    resolved_id = resolved_res.json()["hr_request_id"]
    client.patch(f"/hr-requests/{resolved_id}/status",
                 json={"status": "resolved", "resolution_notes": "Done."},
                 headers={"Authorization": f"Bearer {hr_token}"})

    queue_res = client.get("/hr-requests/queue", headers={"Authorization": f"Bearer {hr_token}"})
    queue_ids = [r["hr_request_id"] for r in queue_res.json()]
    assert open_id in queue_ids
    assert resolved_id not in queue_ids


def test_employee_cannot_see_hr_queue(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.get("/hr-requests/queue", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_employee_cannot_update_request_status(client, seeded, db_session):
    cat = _make_category(db_session)
    token = seeded.token_for(seeded.employee)
    create_res = client.post("/hr-requests",
                              json={"category_id": cat.category_id, "subject": "x", "description": "d"},
                              headers={"Authorization": f"Bearer {token}"})
    req_id = create_res.json()["hr_request_id"]

    res = client.patch(f"/hr-requests/{req_id}/status", json={"status": "resolved"},
                        headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_full_hr_request_lifecycle_raise_comment_resolve(client, seeded, db_session):
    """E2E-style flow within one test: raise -> HR views -> comments
    exchanged -> HR resolves -> employee sees resolution."""
    cat = _make_category(db_session)
    token = seeded.token_for(seeded.employee)
    hr_token = seeded.token_for(seeded.hr_admin)

    create_res = client.post(
        "/hr-requests",
        json={"category_id": cat.category_id, "subject": "Bank detail update", "description": "New IFSC code."},
        headers={"Authorization": f"Bearer {token}"},
    )
    req_id = create_res.json()["hr_request_id"]

    comment_res = client.post(f"/hr-requests/{req_id}/comments",
                               json={"comment_text": "Can you share the new IFSC code?", "is_internal": False},
                               headers={"Authorization": f"Bearer {hr_token}"})
    assert comment_res.status_code == 201, comment_res.text

    employee_reply = client.post(f"/hr-requests/{req_id}/comments",
                                  json={"comment_text": "It's HDFC0001234."},
                                  headers={"Authorization": f"Bearer {token}"})
    assert employee_reply.status_code == 201

    resolve_res = client.patch(f"/hr-requests/{req_id}/status",
                                json={"status": "resolved", "resolution_notes": "Bank details updated."},
                                headers={"Authorization": f"Bearer {hr_token}"})
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "resolved"

    comments_res = client.get(f"/hr-requests/{req_id}/comments", headers={"Authorization": f"Bearer {token}"})
    assert len(comments_res.json()) == 2


def test_internal_comments_are_hidden_from_the_employee(client, seeded, db_session):
    cat = _make_category(db_session)
    token = seeded.token_for(seeded.employee)
    hr_token = seeded.token_for(seeded.hr_admin)

    create_res = client.post("/hr-requests",
                              json={"category_id": cat.category_id, "subject": "x", "description": "d"},
                              headers={"Authorization": f"Bearer {token}"})
    req_id = create_res.json()["hr_request_id"]

    client.post(f"/hr-requests/{req_id}/comments",
                json={"comment_text": "Internal note: escalate to payroll team.", "is_internal": True},
                headers={"Authorization": f"Bearer {hr_token}"})

    employee_view = client.get(f"/hr-requests/{req_id}/comments", headers={"Authorization": f"Bearer {token}"})
    assert employee_view.json() == []

    hr_view = client.get(f"/hr-requests/{req_id}/comments", headers={"Authorization": f"Bearer {hr_token}"})
    assert len(hr_view.json()) == 1


def test_employee_cannot_comment_on_another_employees_request(client, seeded, db_session):
    from datetime import datetime
    from app.models import Employee
    cat = _make_category(db_session)
    other = Employee(
        org_id=seeded.org.org_id, employee_code="E2", entra_object_id="oid-e2",
        email="other@test.com", full_name="Other Employee", first_name="Other", last_name="Employee",
        department_id=seeded.dept.department_id, role="employee", is_active=True,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    db_session.add(other); db_session.commit()

    owner_token = seeded.token_for(seeded.employee)
    create_res = client.post("/hr-requests",
                              json={"category_id": cat.category_id, "subject": "x", "description": "d"},
                              headers={"Authorization": f"Bearer {owner_token}"})
    req_id = create_res.json()["hr_request_id"]

    other_token = seeded.token_for(other)
    res = client.post(f"/hr-requests/{req_id}/comments", json={"comment_text": "not yours"},
                       headers={"Authorization": f"Bearer {other_token}"})
    assert res.status_code == 403
