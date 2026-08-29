"""
Integration tests for app/routers/payslips.py — previously only the PDF
template itself (app/payslip_pdf.py) had test coverage; the router's
ownership checks, publish gate, and PDF-download endpoint did not.
"""
from datetime import date


def _make_payroll_and_payslip(db_session, employee_id, published=True):
    from datetime import datetime
    from app.models import MonthlyPayroll, Payslip
    payroll = MonthlyPayroll(
        employee_id=employee_id, payroll_month=date(2026, 6, 1),
        basic_salary=38000, hra=15200, transport_allowance=1600, medical_allowance=1250,
        pf_employee=4560, professional_tax=200, days_worked=22, total_working_days=22,
        payroll_status="paid",
    )
    db_session.add(payroll); db_session.flush()
    payslip = Payslip(
        employee_id=employee_id, payroll_id=payroll.payroll_id, payslip_month=date(2026, 6, 1),
        pdf_path="generated-on-demand/test.pdf", generated_at=datetime.utcnow(), is_published=published,
    )
    db_session.add(payslip); db_session.commit(); db_session.refresh(payslip)
    return payroll, payslip


def test_employee_can_list_and_view_own_published_payslip(client, seeded, db_session):
    _, payslip = _make_payroll_and_payslip(db_session, seeded.employee.employee_id)
    token = seeded.token_for(seeded.employee)

    list_res = client.get("/payslips", headers={"Authorization": f"Bearer {token}"})
    assert list_res.status_code == 200
    assert any(p["payslip_id"] == payslip.payslip_id for p in list_res.json())

    detail_res = client.get(f"/payslips/{payslip.payslip_id}", headers={"Authorization": f"Bearer {token}"})
    assert detail_res.status_code == 200, detail_res.text
    assert detail_res.json()["net_salary"] > 0


def test_employee_cannot_view_unpublished_payslip(client, seeded, db_session):
    _, payslip = _make_payroll_and_payslip(db_session, seeded.employee.employee_id, published=False)
    token = seeded.token_for(seeded.employee)

    res = client.get(f"/payslips/{payslip.payslip_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404


def test_employee_cannot_view_another_employees_payslip(client, seeded, db_session):
    from datetime import datetime
    from app.models import Employee
    other = Employee(
        org_id=seeded.org.org_id, employee_code="E3", entra_object_id="oid-e3",
        email="other-pay@test.com", full_name="Other Employee", first_name="Other", last_name="Employee",
        department_id=seeded.dept.department_id, role="employee", is_active=True,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    db_session.add(other); db_session.flush()
    _, payslip = _make_payroll_and_payslip(db_session, other.employee_id)

    token = seeded.token_for(seeded.employee)
    res = client.get(f"/payslips/{payslip.payslip_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_hr_admin_can_view_any_employees_payslip_including_unpublished(client, seeded, db_session):
    _, payslip = _make_payroll_and_payslip(db_session, seeded.employee.employee_id, published=False)
    hr_token = seeded.token_for(seeded.hr_admin)

    res = client.get(f"/payslips/{payslip.payslip_id}", headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 200, res.text


def test_hr_admin_can_list_another_employees_payslips_via_query_param(client, seeded, db_session):
    _make_payroll_and_payslip(db_session, seeded.employee.employee_id)
    hr_token = seeded.token_for(seeded.hr_admin)

    res = client.get("/payslips", params={"employee_id": seeded.employee.employee_id},
                      headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_employee_cannot_list_another_employees_payslips(client, seeded, db_session):
    _make_payroll_and_payslip(db_session, seeded.manager.employee_id)
    token = seeded.token_for(seeded.employee)

    res = client.get("/payslips", params={"employee_id": seeded.manager.employee_id},
                      headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_shared_admin_account_has_no_personal_payslips(client, seeded):
    hr_token = seeded.token_for(seeded.hr_admin)
    res = client.get("/payslips", headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 403


def test_download_payslip_pdf_returns_valid_pdf_and_increments_count(client, seeded, db_session):
    _, payslip = _make_payroll_and_payslip(db_session, seeded.employee.employee_id)
    token = seeded.token_for(seeded.employee)

    res = client.get(f"/payslips/{payslip.payslip_id}/pdf", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:4] == b"%PDF"

    db_session.refresh(payslip)
    assert payslip.download_count == 1
    assert payslip.last_downloaded_at is not None


def test_hr_admin_can_publish_a_payslip(client, seeded, db_session):
    _, payslip = _make_payroll_and_payslip(db_session, seeded.employee.employee_id, published=False)
    hr_token = seeded.token_for(seeded.hr_admin)

    res = client.post(f"/payslips/{payslip.payslip_id}/publish", headers={"Authorization": f"Bearer {hr_token}"})
    assert res.status_code == 200, res.text
    assert res.json()["is_published"] is True

    db_session.refresh(payslip)
    assert payslip.is_published is True
    assert payslip.published_at is not None


def test_employee_cannot_publish_a_payslip(client, seeded, db_session):
    _, payslip = _make_payroll_and_payslip(db_session, seeded.employee.employee_id, published=False)
    token = seeded.token_for(seeded.employee)

    res = client.post(f"/payslips/{payslip.payslip_id}/publish", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_viewing_nonexistent_payslip_returns_404(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.get("/payslips/999999", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404
