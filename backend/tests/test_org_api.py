"""
Integration tests for org-hierarchy management (app/routers/org.py) — this
was previously entirely missing (departments/teams were read-only).
"""


def test_hr_admin_can_create_and_list_department(client, seeded):
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.post("/org/departments", json={"department_name": "Finance", "department_code": "FIN"},
                       headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 201, res.text
    dept_id = res.json()["department_id"]

    list_res = client.get("/org/departments", headers={"Authorization": f"Bearer {hr_token}"})
    assert list_res.status_code == 200
    assert any(d["department_id"] == dept_id for d in list_res.json())


def test_employee_cannot_create_department(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.post("/org/departments", json={"department_name": "Finance", "department_code": "FIN2"},
                       headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_hr_admin_can_create_team_under_department(client, seeded):
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.post(
        "/org/teams",
        json={"department_id": seeded.dept.department_id, "team_name": "Platform", "team_code": "PLAT1"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert res.status_code == 201, res.text
    assert res.json()["department_id"] == seeded.dept.department_id


def test_hr_admin_can_reassign_employee_department(client, seeded, db_session):
    from app.models import Department
    new_dept = Department(org_id=seeded.org.org_id, department_name="Sales", department_code="SAL")
    db_session.add(new_dept); db_session.commit()

    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.put(
        f"/org/employees/{seeded.employee.employee_id}/assignment",
        params={"department_id": new_dept.department_id},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert res.status_code == 200

    db_session.refresh(seeded.employee)
    assert seeded.employee.department_id == new_dept.department_id


def test_cannot_assign_shared_admin_account_into_org_hierarchy(client, seeded):
    """Shared admin accounts represent a role, not a person on the org
    chart — they should not be reassignable like a personal employee."""
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.put(
        f"/org/employees/{seeded.hr_admin.employee_id}/assignment",
        params={"department_id": seeded.dept.department_id},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert res.status_code == 400


def test_hr_admin_can_assign_manager_to_employee(client, seeded, db_session):
    """Core of 'HR allocates the manager to the employee' requirement."""
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.put(
        f"/org/employees/{seeded.employee.employee_id}/assignment",
        params={"manager_id": seeded.manager.employee_id},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert res.status_code == 200

    db_session.refresh(seeded.employee)
    assert seeded.employee.manager_id == seeded.manager.employee_id


def test_managers_list_excludes_shared_admin_accounts(client, seeded):
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.get("/org/managers", headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 200
    names = [m["full_name"] for m in res.json()]
    assert seeded.manager.full_name in names
    assert seeded.hr_admin.full_name not in names


def test_employee_directory_search_returns_manager_and_department_names(client, seeded, db_session):
    from app.models import Employee
    from datetime import datetime
    seeded.employee.manager_id = seeded.manager.employee_id
    db_session.commit()

    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.get("/org/employees", params={"q": seeded.employee.full_name.split()[0]},
                      headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 200
    match = next(e for e in res.json() if e["employee_id"] == seeded.employee.employee_id)
    assert match["manager_name"] == seeded.manager.full_name
    assert match["department_name"] == seeded.dept.department_name


def test_employee_cannot_search_employee_directory(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.get("/org/employees", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_hr_admin_can_directly_edit_employee_profile_with_audit_log(client, seeded, db_session):
    """'HR Admin should have an option to edit any of the employees profiles' —
    and every change must be logged for audit purposes."""
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.put(
        f"/profile/{seeded.employee.employee_id}/hr-edit",
        json={"phone": "+91-99999-00000", "address_line1": "12 Anna Salai", "city": "Chennai", "state": "Tamil Nadu"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["phone"] == "+91-99999-00000"

    from app.models import ProfileChangeRequest
    logs = db_session.query(ProfileChangeRequest).filter(
        ProfileChangeRequest.employee_id == seeded.employee.employee_id
    ).all()
    assert any(l.field_name == "phone" and l.new_value == "+91-99999-00000" for l in logs)
    assert all(l.status == "approved" for l in logs)
    assert all(l.reviewed_by == seeded.hr_admin.employee_id for l in logs)


def test_employee_cannot_edit_another_employees_profile(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.put(
        f"/profile/{seeded.manager.employee_id}/hr-edit",
        json={"phone": "+91-00000-00000"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_hr_admin_cannot_edit_shared_admin_account_profile(client, seeded):
    """Shared admin accounts have no personal profile to edit."""
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.put(
        f"/profile/{seeded.hr_admin.employee_id}/hr-edit",
        json={"phone": "+91-11111-11111"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert res.status_code == 404


def test_managers_list_includes_plain_employees_as_candidates(client, seeded):
    """Multiple projects/teams means HR should be able to designate any
    active employee as a manager, not just people already role='manager'."""
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.get("/org/managers", headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 200
    names = [m["full_name"] for m in res.json()]
    assert seeded.employee.full_name in names


def test_assigning_a_plain_employee_as_manager_elevates_their_role(client, seeded, db_session):
    """Assigning a plain employee as someone's manager must grant them
    manager permissions (auto-elevate role) so they can actually approve
    leave etc. for their new direct report."""
    from app.models import Employee
    other = Employee(
        org_id=seeded.org.org_id, employee_code="E3", entra_object_id="oid-e3",
        email="other3@test.com", full_name="Future Manager", first_name="Future", last_name="Manager",
        department_id=seeded.dept.department_id, role="employee", is_active=True,
        created_at=__import__("datetime").datetime.utcnow(), updated_at=__import__("datetime").datetime.utcnow(),
    )
    db_session.add(other); db_session.commit()

    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.put(
        f"/org/employees/{seeded.employee.employee_id}/assignment",
        params={"manager_id": other.employee_id},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert res.status_code == 200

    db_session.refresh(other)
    assert other.role == "manager"


def test_employee_cannot_be_assigned_as_their_own_manager(client, seeded):
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.put(
        f"/org/employees/{seeded.employee.employee_id}/assignment",
        params={"manager_id": seeded.employee.employee_id},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert res.status_code == 400


def test_shared_admin_account_cannot_be_assigned_as_a_manager(client, seeded):
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.put(
        f"/org/employees/{seeded.employee.employee_id}/assignment",
        params={"manager_id": seeded.hr_admin.employee_id},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert res.status_code == 400


def test_hr_admin_can_create_designation(client, seeded):
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.post("/org/designations", json={"title": "Staff Engineer", "level": "senior"},
                       headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 201, res.text

    list_res = client.get("/org/designations", headers={"Authorization": f"Bearer {hr_token}"})
    assert any(d["title"] == "Staff Engineer" for d in list_res.json())


def test_employee_cannot_create_designation(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.post("/org/designations", json={"title": "Hacker"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_hr_admin_can_update_designation(client, seeded, db_session):
    from app.models import Designation
    desig = Designation(org_id=seeded.org.org_id, title="Junior Engineer", level="junior")
    db_session.add(desig); db_session.commit()

    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.put(f"/org/designations/{desig.designation_id}",
                      json={"title": "Senior Engineer", "level": "senior"},
                      headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 200, res.text
    assert res.json()["title"] == "Senior Engineer"


def test_hr_admin_can_deactivate_employee(client, seeded, db_session):
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.delete(f"/org/employees/{seeded.employee.employee_id}",
                         headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 200, res.text

    db_session.refresh(seeded.employee)
    assert seeded.employee.is_active is False
    assert seeded.employee.employment_status == "terminated"

    # Deactivated employee should drop out of the directory search.
    list_res = client.get("/org/employees", headers={"Authorization": f"Bearer {hr_token}"})
    assert not any(e["employee_id"] == seeded.employee.employee_id for e in list_res.json())


def test_deactivated_employee_cannot_log_in(client, seeded, db_session):
    hr_token = seeded.token_for(seeded.hr_admin)
    client.delete(f"/org/employees/{seeded.employee.employee_id}",
                  headers={"Authorization": f"Bearer {hr_token}"})

    login_res = client.post("/auth/login", json={"email": seeded.employee.email})
    assert login_res.status_code == 401


def test_hr_admin_cannot_deactivate_shared_admin_account(client, seeded):
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.delete(f"/org/employees/{seeded.hr_admin.employee_id}",
                         headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 400


def test_hr_admin_cannot_deactivate_self():
    pass  # covered by the shared-admin-account test above (hr_admin IS the shared account)


def test_employee_cannot_deactivate_another_employee(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.delete(f"/org/employees/{seeded.manager.employee_id}",
                         headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
