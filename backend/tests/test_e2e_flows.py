"""
5 critical E2E scenarios, as an isolated automated suite — proposal §10.2:
'E2E Tests: Full flows: SSO login -> leave apply -> manager approves ->
employee notified. Employee query -> RAG chatbot -> policy answer ->
escalate -> HR Admin ticket resolved.' and the mid-term doc's own §9
("What Is NOT Completed Yet"): 'E2E test scenarios as a distinctly isolated
suite (5 critical flows per QA strategy) ... Current tests are
unit/integration-level per router; E2E flows are exercised manually ...
but not yet codified as an isolated automated suite.'

Each test below chains multiple routers in one flow (not just one
endpoint), and asserts on side effects (notifications, audit trails, state
transitions) at every step — that's what makes these E2E rather than a
router-level integration test. Uses the same `client`/`seeded`/`db_session`
fixtures as the rest of the suite (real Postgres, real Alembic schema).
"""
from datetime import date


def _leave_type_and_balance(db_session, org_id, employee_id, half_day_allowed=True):
    from datetime import datetime
    from app.models import LeaveType, EmployeeLeaveBalance
    lt = LeaveType(org_id=org_id, leave_type_name="Casual Leave", leave_code="CL",
                    annual_quota=10, half_day_allowed=half_day_allowed)
    db_session.add(lt); db_session.flush()
    bal = EmployeeLeaveBalance(
        employee_id=employee_id, leave_type_id=lt.leave_type_id, year=date.today().year,
        total_allotted=10, carried_over=0, used_days=0, pending_days=0,
        last_updated=datetime.utcnow(),
    )
    db_session.add(bal); db_session.commit()
    return lt


# ── Scenario 1: SSO login -> leave apply -> manager approves -> employee notified ──

def test_e2e_login_apply_leave_approve_notify(client, seeded, db_session):
    lt = _leave_type_and_balance(db_session, seeded.org.org_id, seeded.employee.employee_id)
    lt_id = lt.leave_type_id

    # Step 1: SSO/mock login as the employee.
    login_res = client.post("/auth/login", json={"email": seeded.employee.email})
    assert login_res.status_code == 200, login_res.text
    employee_token = login_res.json()["access_token"]
    emp_headers = {"Authorization": f"Bearer {employee_token}"}

    # Step 2: employee applies for a half-day of Casual Leave.
    apply_res = client.post(
        "/leave/requests",
        json={"leave_type_id": lt_id, "start_date": str(date.today()), "end_date": str(date.today()),
              "is_half_day": True, "half_day_slot": "morning", "reason": "Personal errand"},
        headers=emp_headers,
    )
    assert apply_res.status_code == 201, apply_res.text
    leave_request_id = apply_res.json()["leave_request_id"]
    assert apply_res.json()["status"] == "pending"

    # Step 3: manager logs in and sees it queued for approval.
    manager_login = client.post("/auth/login", json={"email": seeded.manager.email})
    manager_headers = {"Authorization": f"Bearer {manager_login.json()['access_token']}"}
    team_res = client.get("/leave/requests/team", headers=manager_headers)
    assert any(r["leave_request_id"] == leave_request_id for r in team_res.json())

    # Step 4: manager approves.
    decision_res = client.post(
        f"/leave/requests/{leave_request_id}/decision",
        json={"decision": "approved", "comments": "Approved."},
        headers=manager_headers,
    )
    assert decision_res.status_code == 200, decision_res.text
    assert decision_res.json()["status"] == "approved"

    # Step 5: employee sees the updated status AND a notification.
    my_requests = client.get("/leave/requests", headers=emp_headers)
    assert any(r["leave_request_id"] == leave_request_id and r["status"] == "approved"
               for r in my_requests.json())

    notif_res = client.get("/notifications", headers=emp_headers)
    assert any(n["notification_type"] == "leave_decision" for n in notif_res.json())


# ── Scenario 2: chatbot query -> low confidence -> escalate -> HR resolves ────────

def test_e2e_chatbot_query_escalate_hr_resolves(client, seeded, db_session):
    from app.models import HRPolicyDocument, RagDocumentChunk
    doc = HRPolicyDocument(org_id=seeded.org.org_id, document_name="Code of Conduct",
                            document_type="code_of_conduct", file_path="coc.pdf", is_active=True)
    db_session.add(doc); db_session.flush()
    db_session.add(RagDocumentChunk(document_id=doc.document_id, chunk_index=0,
                                     chunk_text="Employees must treat colleagues with respect.",
                                     chromadb_chunk_id="e2e-coc-0"))
    db_session.commit()

    token = seeded.token_for(seeded.employee)
    headers = {"Authorization": f"Bearer {token}"}

    # Step 1: employee asks an out-of-scope question — nothing in the corpus grounds it.
    query_res = client.post("/chatbot/query", json={"query_text": "What's the weather like today?"},
                             headers=headers)
    assert query_res.status_code == 200, query_res.text
    assert query_res.json()["is_grounded"] is False
    query_id = query_res.json()["query_id"]

    # Step 2: employee escalates to HR.
    escalate_res = client.post("/chatbot/escalate", json={"query_id": query_id, "reason": "low_confidence"},
                                headers=headers)
    assert escalate_res.status_code == 201, escalate_res.text
    escalation_id = escalate_res.json()["escalation_id"]

    # Step 3: HR Admin sees it in the queue.
    hr_headers = {"Authorization": f"Bearer {seeded.token_for(seeded.hr_admin)}"}
    queue_res = client.get("/chatbot/escalations/queue", headers=hr_headers)
    assert any(t["escalation_id"] == escalation_id for t in queue_res.json())

    # Step 4: HR Admin resolves it with a direct answer.
    respond_res = client.post(
        f"/chatbot/escalations/{escalation_id}/respond",
        data={"response_text": "It's sunny today, but more importantly, ask IT for weather widgets :)"},
        headers=hr_headers,
    )
    assert respond_res.status_code == 200, respond_res.text
    assert respond_res.json()["status"] == "resolved"

    # Step 5: employee sees the resolution reflected in their own escalations,
    # AND a notification about it.
    mine_res = client.get("/chatbot/escalations/mine", headers=headers)
    assert any(t["escalation_id"] == escalation_id and t["status"] == "resolved" for t in mine_res.json())

    notif_res = client.get("/notifications", headers=headers)
    assert any(n["notification_type"] == "escalation_resolved" for n in notif_res.json())


# ── Scenario 3: HR request raise -> HR Admin resolves -> employee notified ────────

def test_e2e_hr_request_raise_resolve_notify(client, seeded, db_session):
    from app.models import HRRequestCategory
    cat = HRRequestCategory(category_name="Grievance", default_priority="high", sla_hours=24)
    db_session.add(cat); db_session.commit()

    token = seeded.token_for(seeded.employee)
    hr_token = seeded.token_for(seeded.hr_admin)

    raise_res = client.post(
        "/hr-requests",
        json={"category_id": cat.category_id, "subject": "Workplace concern",
              "description": "Raising a concern about team scheduling.", "priority": "high"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert raise_res.status_code == 201, raise_res.text
    req_id = raise_res.json()["hr_request_id"]

    queue_res = client.get("/hr-requests/queue", headers={"Authorization": f"Bearer {hr_token}"})
    assert any(r["hr_request_id"] == req_id for r in queue_res.json())

    resolve_res = client.patch(
        f"/hr-requests/{req_id}/status",
        json={"status": "resolved", "resolution_notes": "Scheduling adjusted; discussed with manager."},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert resolve_res.status_code == 200, resolve_res.text
    assert resolve_res.json()["status"] == "resolved"

    my_res = client.get("/hr-requests", headers={"Authorization": f"Bearer {token}"})
    assert any(r["hr_request_id"] == req_id and r["status"] == "resolved" for r in my_res.json())

    notif_res = client.get("/notifications", headers={"Authorization": f"Bearer {token}"})
    assert any(n["notification_type"] == "hr_request_status" for n in notif_res.json())


# ── Scenario 4: IT/Asset request raise -> IT Admin resolves -> employee notified ──

def test_e2e_it_request_raise_resolve_notify(client, seeded, db_session):
    from datetime import datetime
    from app.models import Employee
    it_admin = Employee(
        org_id=seeded.org.org_id, employee_code="ITADMIN", entra_object_id=None,
        email="it.admin.e2e@test.com", full_name="IT Admin", first_name="IT", last_name="Admin",
        department_id=seeded.dept.department_id, role="it_admin", is_shared_admin=True,
        entra_group_id="test-it-group-e2e", is_active=True,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    db_session.add(it_admin); db_session.commit()

    token = seeded.token_for(seeded.employee)
    it_token = seeded.token_for(it_admin)

    raise_res = client.post(
        "/it-requests",
        json={"request_type": "hardware_issue", "subject": "Monitor flickering",
              "description": "External monitor flickers intermittently.", "priority": "normal"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert raise_res.status_code == 201, raise_res.text
    req_id = raise_res.json()["it_request_id"]

    progress_res = client.patch(
        f"/it-requests/{req_id}/status",
        json={"status": "in_progress", "notes": "Dispatching a replacement cable."},
        headers={"Authorization": f"Bearer {it_token}"},
    )
    assert progress_res.status_code == 200

    resolve_res = client.patch(
        f"/it-requests/{req_id}/status",
        json={"status": "resolved", "notes": "Cable replaced; issue confirmed fixed."},
        headers={"Authorization": f"Bearer {it_token}"},
    )
    assert resolve_res.status_code == 200, resolve_res.text
    assert resolve_res.json()["status"] == "resolved"

    my_res = client.get("/it-requests", headers={"Authorization": f"Bearer {token}"})
    assert any(r["it_request_id"] == req_id and r["status"] == "resolved" for r in my_res.json())

    notif_res = client.get("/notifications", headers={"Authorization": f"Bearer {token}"})
    assert any(n["notification_type"] == "it_request_status" for n in notif_res.json())


# ── Scenario 5: HR Admin publishes payslip -> employee downloads PDF ─────────────

def test_e2e_payslip_publish_then_employee_downloads(client, seeded, db_session):
    from datetime import datetime
    from app.models import MonthlyPayroll, Payslip
    payroll = MonthlyPayroll(
        employee_id=seeded.employee.employee_id, payroll_month=date(2026, 6, 1),
        basic_salary=38000, hra=15200, transport_allowance=1600, medical_allowance=1250,
        pf_employee=4560, professional_tax=200, days_worked=22, total_working_days=22,
        payroll_status="paid",
    )
    db_session.add(payroll); db_session.flush()
    payslip = Payslip(
        employee_id=seeded.employee.employee_id, payroll_id=payroll.payroll_id,
        payslip_month=date(2026, 6, 1), pdf_path="generated-on-demand/e2e.pdf",
        generated_at=datetime.utcnow(), is_published=False,
    )
    db_session.add(payslip); db_session.commit(); db_session.refresh(payslip)

    employee_headers = {"Authorization": f"Bearer {seeded.token_for(seeded.employee)}"}
    hr_headers = {"Authorization": f"Bearer {seeded.token_for(seeded.hr_admin)}"}

    # Step 1: before publishing, employee cannot see it.
    blocked_res = client.get(f"/payslips/{payslip.payslip_id}", headers=employee_headers)
    assert blocked_res.status_code == 404

    # Step 2: HR Admin publishes it.
    publish_res = client.post(f"/payslips/{payslip.payslip_id}/publish", headers=hr_headers)
    assert publish_res.status_code == 200, publish_res.text
    assert publish_res.json()["is_published"] is True

    # Step 3: employee can now see it in their list.
    list_res = client.get("/payslips", headers=employee_headers)
    assert any(p["payslip_id"] == payslip.payslip_id for p in list_res.json())

    # Step 4: employee downloads the PDF.
    pdf_res = client.get(f"/payslips/{payslip.payslip_id}/pdf", headers=employee_headers)
    assert pdf_res.status_code == 200, pdf_res.text
    assert pdf_res.content[:4] == b"%PDF"

    db_session.refresh(payslip)
    assert payslip.download_count == 1
