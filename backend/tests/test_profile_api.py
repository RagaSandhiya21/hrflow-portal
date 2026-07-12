"""
Integration tests for app/routers/profile.py — including a regression test
for a route-ordering bug: GET/PUT /profile/{employee_id} (HR Admin's direct
employee editor) was registered BEFORE the fixed-path routes
(/profile/change-requests, etc.), so FastAPI's in-order route matching
swallowed every request to /profile/change-requests into the
{employee_id}-shaped route instead, wrongly 403'ing real employees calling
their own personal endpoints. The fix is route ordering (fixed paths before
parameterized ones); these tests pin that behavior down.
"""


def test_get_my_profile_works_for_real_employee(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.get("/profile/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    assert res.json()["employee"]["email"] == seeded.employee.email


def test_my_change_requests_not_swallowed_by_employee_id_route(client, seeded):
    """Regression test: this must return 200 (a normal employee's own list),
    not 403 (which is what happens if the /{employee_id} route wrongly
    matches "change-requests" as an employee_id path segment)."""
    token = seeded.token_for(seeded.employee)
    res = client.get("/profile/change-requests", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    assert res.json() == []


def test_pending_change_requests_not_swallowed_by_employee_id_route(client, seeded):
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.get("/profile/change-requests/pending", headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 200, res.text


def test_employee_cannot_list_pending_change_requests(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.get("/profile/change-requests/pending", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_submit_change_request_not_swallowed_by_employee_id_route(client, seeded, db_session):
    token = seeded.token_for(seeded.employee)
    res = client.post(
        "/profile/change-requests",
        json={"field_group": "bank", "field_name": "bank_ifsc", "new_value": "HDFC0001234", "reason": "New account"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201, res.text
    assert res.json()["field_name"] == "bank_ifsc"


def test_shared_admin_cannot_use_personal_profile_endpoint(client, seeded):
    token = seeded.token_for(seeded.hr_admin)
    res = client.get("/profile/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_profile_shows_department_and_designation_names(client, seeded, db_session):
    from app.models import Designation
    desig = Designation(org_id=seeded.org.org_id, title="Software Engineer", level="junior")
    db_session.add(desig); db_session.flush()
    seeded.employee.designation_id = desig.designation_id
    db_session.commit()

    token = seeded.token_for(seeded.employee)
    res = client.get("/profile/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    emp = res.json()["employee"]
    assert emp["department_name"] == seeded.dept.department_name
    assert emp["designation_title"] == "Software Engineer"


def test_add_edit_and_delete_emergency_contact(client, seeded):
    token = seeded.token_for(seeded.employee)

    add_res = client.post(
        "/profile/me/emergency-contacts",
        json={"contact_name": "Meena Iyer", "relationship": "mother", "phone": "+91-90000-11111", "is_primary": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert add_res.status_code == 201, add_res.text
    contact_id = add_res.json()["contact_id"]

    edit_res = client.put(
        f"/profile/me/emergency-contacts/{contact_id}",
        json={"contact_name": "Meena Iyer", "relationship": "mother", "phone": "+91-90000-99999", "is_primary": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert edit_res.status_code == 200, edit_res.text
    assert edit_res.json()["phone"] == "+91-90000-99999"

    delete_res = client.delete(
        f"/profile/me/emergency-contacts/{contact_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_res.status_code == 200

    profile_res = client.get("/profile/me", headers={"Authorization": f"Bearer {token}"})
    assert profile_res.json()["emergency_contacts"] == []


def test_employee_cannot_edit_another_employees_emergency_contact(client, seeded, db_session):
    from app.models import Employee, EmergencyContact
    other = Employee(
        org_id=seeded.org.org_id, employee_code="E4", entra_object_id="oid-e4",
        email="other4@test.com", full_name="Other Person", first_name="Other", last_name="Person",
        department_id=seeded.dept.department_id, role="employee", is_active=True,
        created_at=__import__("datetime").datetime.utcnow(), updated_at=__import__("datetime").datetime.utcnow(),
    )
    db_session.add(other); db_session.flush()
    contact = EmergencyContact(employee_id=other.employee_id, contact_name="X", phone="123", is_primary=True, updated_at=__import__("datetime").datetime.utcnow())
    db_session.add(contact); db_session.commit()

    token = seeded.token_for(seeded.employee)
    res = client.put(
        f"/profile/me/emergency-contacts/{contact.contact_id}",
        json={"contact_name": "Hacked", "phone": "000"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


def test_profile_shows_team_name(client, seeded, db_session):
    from app.models import Team
    team = Team(org_id=seeded.org.org_id, department_id=seeded.dept.department_id,
                team_name="Platform Engineering", team_code="PLAT-1")
    db_session.add(team); db_session.flush()
    seeded.employee.team_id = team.team_id
    db_session.commit()

    token = seeded.token_for(seeded.employee)
    res = client.get("/profile/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["employee"]["team_name"] == "Platform Engineering"
