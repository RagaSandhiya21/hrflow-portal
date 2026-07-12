"""
Seed script — populates a demo dataset so the frontend has something real
to show immediately after setup.

Usage (from backend/):
    python seed.py

Safe-guard: refuses to run if organisations already has rows, so you don't
accidentally double-seed. Truncate the DB (re-run db/schema.sql against a
fresh database) if you want to reseed from scratch.

Demo login emails (see printed table at the end) all work with the mock
SSO login — no password needed, see app/security.py for why.
"""
import sys
from datetime import date, datetime, timedelta, time as dtime
import random

sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models import (
    Organisation, Department, Team, Designation, Location, Employee,
    EmployeeAddress, EmergencyContact, EmployeeIdentityInfo,
    LeaveType, HolidayCalendar, EmployeeLeaveBalance, LeaveRequest, LeaveApproval,
    SalaryComponent, EmployeeSalaryStructure, MonthlyPayroll, Payslip,
    HRRequestCategory, HRRequest,
    ITRequest,
    AttendanceRecord, AttendanceMonthlySummary,
    HRPolicyDocument, RagDocumentChunk,
)

db = SessionLocal()

if db.query(Organisation).count() > 0:
    print("organisations already has data — refusing to reseed. "
          "Re-run db/schema.sql against a fresh database if you want a clean reseed.")
    sys.exit(1)


def now():
    return datetime.utcnow()


print("Seeding HRFlow demo data...")

# ---------------------------------------------------------------- A. ORG ---

org = Organisation(org_name="Psiog Digital", org_code="PSIOG", currency_code="INR")
db.add(org)
db.flush()

loc_chennai = Location(org_id=org.org_id, location_name="Chennai HQ", city="Chennai", state="Tamil Nadu", country="India")
loc_bangalore = Location(org_id=org.org_id, location_name="Bangalore Office", city="Bangalore", state="Karnataka", country="India")
db.add_all([loc_chennai, loc_bangalore])
db.flush()

dept_eng = Department(org_id=org.org_id, department_name="Engineering", department_code="ENG")
dept_hr = Department(org_id=org.org_id, department_name="Human Resources", department_code="HR")
dept_it = Department(org_id=org.org_id, department_name="IT Services", department_code="IT")
db.add_all([dept_eng, dept_hr, dept_it])
db.flush()

team_platform = Team(org_id=org.org_id, department_id=dept_eng.department_id, team_name="Platform Engineering", team_code="ENG-PLAT")
db.add(team_platform)
db.flush()

desig_swe = Designation(org_id=org.org_id, title="Software Engineer", level="junior")
desig_sr_swe = Designation(org_id=org.org_id, title="Senior Software Engineer", level="senior")
desig_eng_mgr = Designation(org_id=org.org_id, title="Engineering Manager", level="manager")
desig_hr_admin = Designation(org_id=org.org_id, title="HR Administrator", level="lead")
desig_it_admin = Designation(org_id=org.org_id, title="IT Administrator", level="lead")
db.add_all([desig_swe, desig_sr_swe, desig_eng_mgr, desig_hr_admin, desig_it_admin])
db.flush()

# ----------------------------------------------------------- EMPLOYEES ---

def make_employee(code, first, last, email, role, designation_id, department_id,
                   team_id, location_id, manager_id=None, dob=None, doj=None):
    e = Employee(
        org_id=org.org_id,
        employee_code=code,
        entra_object_id=f"mock-oid-{code}",
        email=email,
        full_name=f"{first} {last}",
        first_name=first,
        last_name=last,
        display_name=first,
        phone="+91-90000-00000",
        gender="prefer_not_to_say",
        date_of_birth=dob,
        marital_status="single",
        designation_id=designation_id,
        department_id=department_id,
        team_id=team_id,
        location_id=location_id,
        manager_id=manager_id,
        date_of_joining=doj,
        employment_type="full_time",
        employment_status="active",
        role=role,
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add(e)
    db.flush()
    return e

def make_shared_admin(code, role, email, display_name, designation_id, department_id, entra_group_id):
    """
    HR Admin / IT Admin are FUNCTIONAL role accounts, not people — see
    schema.sql's comment on employees.is_shared_admin. Multiple real staff
    share access to this single row via membership of `entra_group_id` in
    Entra ID; no personal data (DOB, phone, gender, marital status,
    address, bank/PAN, leave, payslips, attendance) is ever attached to it.
    """
    e = Employee(
        org_id=org.org_id,
        employee_code=code,
        entra_object_id=None,     # no single fixed person owns this account
        email=email,
        full_name=display_name,
        first_name=display_name.split(" ")[0],
        last_name=display_name.split(" ", 1)[1] if " " in display_name else "",
        display_name=display_name,
        designation_id=designation_id,
        department_id=department_id,
        employment_type="full_time",
        employment_status="active",
        role=role,
        is_shared_admin=True,
        entra_group_id=entra_group_id,
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add(e)
    db.flush()
    return e


kavya = make_employee("P103", "Kavya", "Subramaniam", "kavya.manager@psiog.com", "manager",
                       desig_eng_mgr.designation_id, dept_eng.department_id, team_platform.team_id,
                       loc_chennai.location_id, dob=date(1988, 4, 12), doj=date(2019, 6, 1))

# HR Admin / IT Admin: shared functional accounts, not people. In production,
# real Entra ID groups (env vars ENTRA_HR_ADMIN_GROUP_ID / ENTRA_IT_ADMIN_GROUP_ID)
# determine who is let into these — see app/routers/auth.py `sso_login`.
priya = make_shared_admin("HRADMIN", "hr_admin", "hr.admin@psiog.com", "HR Admin",
                           desig_hr_admin.designation_id, dept_hr.department_id,
                           entra_group_id="dev-placeholder-hr-admins-group")

arjun = make_shared_admin("ITADMIN", "it_admin", "it.admin@psiog.com", "IT Admin",
                           desig_it_admin.designation_id, dept_it.department_id,
                           entra_group_id="dev-placeholder-it-admins-group")

rohan = make_employee("P104", "Rohan", "Iyer", "rohan.employee@psiog.com", "employee",
                       desig_swe.designation_id, dept_eng.department_id, team_platform.team_id,
                       loc_chennai.location_id, manager_id=kavya.employee_id,
                       dob=date(1996, 7, 19), doj=date(2022, 8, 1))

sneha = make_employee("P105", "Sneha", "Nair", "sneha.employee@psiog.com", "employee",
                       desig_sr_swe.designation_id, dept_eng.department_id, team_platform.team_id,
                       loc_bangalore.location_id, manager_id=kavya.employee_id,
                       dob=date(1994, 11, 3), doj=date(2021, 2, 14))

db.flush()
dept_eng.head_employee_id = kavya.employee_id
team_platform.lead_employee_id = kavya.employee_id

# Real, individual people only. priya/arjun are shared admin accounts (see
# make_shared_admin above) — they never get personal profile/leave/payroll/
# attendance rows, since they represent a role, not a person.
ALL_EMPLOYEES = [kavya, rohan, sneha]
SHARED_ADMIN_ACCOUNTS = [priya, arjun]

# Profile details for a couple of employees (enough to demo the screens)
db.add_all([
    EmployeeAddress(employee_id=rohan.employee_id, address_type="current", address_line1="12 Anna Salai",
                     city="Chennai", state="Tamil Nadu", country="India", pincode="600002", updated_at=now()),
    EmployeeAddress(employee_id=sneha.employee_id, address_type="current", address_line1="45 MG Road",
                     city="Bangalore", state="Karnataka", country="India", pincode="560001", updated_at=now()),
])
db.add_all([
    EmergencyContact(employee_id=rohan.employee_id, contact_name="Meena Iyer", relationship_="mother",
                      phone="+91-90000-11111", is_primary=True, updated_at=now()),
    EmergencyContact(employee_id=sneha.employee_id, contact_name="Arvind Nair", relationship_="spouse",
                      phone="+91-90000-22222", is_primary=True, updated_at=now()),
])
db.add_all([
    EmployeeIdentityInfo(employee_id=e.employee_id, pan_number=f"ABCDE{1000+i}F", aadhaar_number=f"{900000000000+i}",
                          bank_account_number=f"5000123400{i}", bank_name="HDFC Bank", bank_ifsc="HDFC0001234",
                          bank_branch="Chennai Main", bank_account_type="savings", updated_at=now())
    for i, e in enumerate(ALL_EMPLOYEES)
])

# ------------------------------------------------------ D. LEAVE MGMT ---

leave_types = {
    "CL": LeaveType(org_id=org.org_id, leave_type_name="Casual Leave", leave_code="CL", annual_quota=10,
                     carryover_allowed=False, half_day_allowed=True),
    "SL": LeaveType(org_id=org.org_id, leave_type_name="Sick Leave", leave_code="SL", annual_quota=10,
                     carryover_allowed=False, half_day_allowed=True, requires_document=True),
    "PL": LeaveType(org_id=org.org_id, leave_type_name="Privilege Leave", leave_code="PL", annual_quota=12,
                     carryover_allowed=True, max_carryover_days=6, half_day_allowed=False),
    "COMP": LeaveType(org_id=org.org_id, leave_type_name="Compensatory Off", leave_code="COMP", annual_quota=0,
                       carryover_allowed=False, half_day_allowed=True),
    "WFH": LeaveType(org_id=org.org_id, leave_type_name="Work From Home", leave_code="WFH", annual_quota=24,
                      monthly_quota=2, carryover_allowed=False, half_day_allowed=False),
}
db.add_all(leave_types.values())
db.flush()

THIS_YEAR = date.today().year
db.add_all([
    HolidayCalendar(org_id=org.org_id, holiday_date=date(THIS_YEAR, 1, 26), holiday_name="Republic Day"),
    HolidayCalendar(org_id=org.org_id, holiday_date=date(THIS_YEAR, 8, 15), holiday_name="Independence Day"),
    HolidayCalendar(org_id=org.org_id, holiday_date=date(THIS_YEAR, 10, 2), holiday_name="Gandhi Jayanti"),
    HolidayCalendar(org_id=org.org_id, holiday_date=date(THIS_YEAR, 12, 25), holiday_name="Christmas"),
])

for e in ALL_EMPLOYEES:
    for code, lt in leave_types.items():
        db.add(EmployeeLeaveBalance(
            employee_id=e.employee_id, leave_type_id=lt.leave_type_id, year=THIS_YEAR,
            total_allotted=lt.annual_quota, carried_over=2 if code == "PL" else 0,
            used_days=random.choice([0, 1, 2]) if code in ("CL", "SL") else 0,
            last_updated=now(),
        ))
db.flush()

# A couple of sample leave requests so the screens aren't empty
db.add(LeaveRequest(
    employee_id=rohan.employee_id, leave_type_id=leave_types["CL"].leave_type_id,
    start_date=date.today() + timedelta(days=5), end_date=date.today() + timedelta(days=5),
    number_of_days=1, reason="Personal work", status="pending", applied_at=now(), updated_at=now(),
))
approved_lr = LeaveRequest(
    employee_id=sneha.employee_id, leave_type_id=leave_types["SL"].leave_type_id,
    start_date=date.today() - timedelta(days=10), end_date=date.today() - timedelta(days=9),
    number_of_days=2, reason="Fever", status="approved", applied_at=now() - timedelta(days=11), updated_at=now() - timedelta(days=10),
)
db.add(approved_lr)
db.flush()
db.add(LeaveApproval(leave_request_id=approved_lr.leave_request_id, approver_id=kavya.employee_id,
                      approval_level=1, action="approved", comments="Get well soon", actioned_at=now() - timedelta(days=10)))

# ------------------------------------------------------ F. PAYROLL ---

components = {
    "BASIC": SalaryComponent(org_id=org.org_id, component_name="Basic Salary", component_code="BASIC", component_type="earning"),
    "HRA": SalaryComponent(org_id=org.org_id, component_name="HRA", component_code="HRA", component_type="earning"),
    "TA": SalaryComponent(org_id=org.org_id, component_name="Transport Allowance", component_code="TA", component_type="earning"),
}
db.add_all(components.values())
db.flush()

SALARY_TABLE = {  # employee_code -> (basic, hra, transport)
    "P101": (45000, 18000, 1600), "P102": (42000, 16800, 1600), "P103": (75000, 30000, 1600),
    "P104": (38000, 15200, 1600), "P105": (52000, 20800, 1600),
}

for e in ALL_EMPLOYEES:
    basic, hra, ta = SALARY_TABLE[e.employee_code]
    db.add(EmployeeSalaryStructure(employee_id=e.employee_id, component_id=components["BASIC"].component_id,
                                    amount=basic, effective_from=e.date_of_joining or date(THIS_YEAR, 1, 1), created_at=now()))
    db.add(EmployeeSalaryStructure(employee_id=e.employee_id, component_id=components["HRA"].component_id,
                                    amount=hra, effective_from=e.date_of_joining or date(THIS_YEAR, 1, 1), created_at=now()))
    db.add(EmployeeSalaryStructure(employee_id=e.employee_id, component_id=components["TA"].component_id,
                                    amount=ta, effective_from=e.date_of_joining or date(THIS_YEAR, 1, 1), created_at=now()))

# Generate the last 3 months of payroll + payslips, published except the latest
today = date.today()
for months_back in range(2, -1, -1):
    month_date = (today.replace(day=1) - timedelta(days=30 * months_back)).replace(day=1)
    for e in ALL_EMPLOYEES:
        basic, hra, ta = SALARY_TABLE[e.employee_code]
        pf = round(basic * 0.12, 2)
        prof_tax = 200
        payroll = MonthlyPayroll(
            employee_id=e.employee_id, payroll_month=month_date,
            basic_salary=basic, hra=hra, transport_allowance=ta, medical_allowance=1250,
            special_allowance=0, performance_bonus=0, other_earnings=0,
            pf_employee=pf, esi_employee=0, professional_tax=prof_tax, tds=0,
            loan_deduction=0, loss_of_pay=0, other_deductions=0,
            total_working_days=22, days_worked=22, days_on_lop=0,
            payroll_status="paid", payment_date=month_date.replace(day=28),
        )
        db.add(payroll)
        db.flush()
        is_published = months_back > 0  # current month stays unpublished, like a real cycle
        db.add(Payslip(
            employee_id=e.employee_id, payroll_id=payroll.payroll_id, payslip_month=month_date,
            pdf_path=f"generated-on-demand/{e.employee_code}/{month_date.isoformat()}.pdf",
            generated_at=now(), is_published=is_published,
            published_at=now() if is_published else None,
        ))

# --------------------------------------------------------- G/H. REQUESTS ---

categories = [
    HRRequestCategory(category_name="Document Request", default_priority="normal", sla_hours=48),
    HRRequestCategory(category_name="Leave Encashment", default_priority="normal", sla_hours=72),
    HRRequestCategory(category_name="Policy Clarification", default_priority="low", sla_hours=48),
    HRRequestCategory(category_name="Grievance", default_priority="high", sla_hours=24),
    HRRequestCategory(category_name="Onboarding Support", default_priority="normal", sla_hours=48),
    HRRequestCategory(category_name="Exit Formalities", default_priority="high", sla_hours=24),
]
db.add_all(categories)
db.flush()

db.add(HRRequest(
    employee_id=rohan.employee_id, category_id=categories[0].category_id,
    subject="Need an employment verification letter",
    description="Applying for a personal loan, need a salary + employment verification letter addressed to HDFC Bank.",
    priority="normal", status="open", raised_at=now(), updated_at=now(),
    assigned_to=priya.employee_id,  # routed to the shared HR Admin account, not a named person
))

db.add(ITRequest(
    employee_id=sneha.employee_id, request_type="software_install",
    subject="Need Docker Desktop installed",
    description="Requesting Docker Desktop for local container builds on my work laptop.",
    priority="normal", status="open", raised_at=now(), updated_at=now(),
    assigned_to=arjun.employee_id,  # routed to the shared IT Admin account, not a named person
))

# --------------------------------------------------- K. CHATBOT POLICY DOCS

POLICY_DOCS = {
    "Leave Policy 2026": ("leave_policy", [
        "Employees are entitled to 10 days of Casual Leave (CL) and 10 days of Sick Leave (SL) per calendar "
        "year. Casual Leave can be taken for personal reasons with at least 1 day's notice where possible. "
        "Sick Leave taken for more than 2 consecutive days requires a medical certificate.",
        "Privilege Leave (PL) accrues at 1 day per month, up to 12 days per year, and up to 6 unused days "
        "may be carried over into the next calendar year. Unused PL beyond the carryover cap lapses on "
        "December 31st.",
        "Employees may work from home (WFH) up to 2 days per month with manager approval. WFH days do not "
        "count against Casual or Privilege Leave balances.",
        "Leave cannot be applied for company-declared public holidays or weekends — these days are excluded "
        "automatically from the number of days deducted from your balance.",
    ]),
    "Code of Conduct": ("code_of_conduct", [
        "All employees are expected to treat colleagues, clients, and vendors with respect. Harassment, "
        "discrimination, or retaliation of any kind will not be tolerated and may result in disciplinary "
        "action up to and including termination.",
        "Employees must avoid conflicts of interest. Any outside employment, financial interest, or "
        "relationship that could conflict with Psiog's interests must be disclosed to HR.",
    ]),
    "Compensation & Benefits Policy": ("compensation_policy", [
        "Salaries are credited on the last working day of each month via bank transfer. Payslips are "
        "published on the employee portal once payroll processing is complete, typically by the 2nd "
        "working day of the following month.",
        "Provident Fund (PF) is deducted at 12% of Basic Salary as the employee contribution, matched by "
        "an equal employer contribution, in line with EPF Act requirements.",
        "Professional Tax is deducted as per Tamil Nadu / Karnataka state slabs depending on work location.",
    ]),
    "IT & Asset Usage Policy": ("it_policy", [
        "Company laptops and peripherals remain company property and must be returned on separation. "
        "Report lost or stolen devices to IT immediately via an IT Request ticket marked Urgent.",
        "Software installation requests for anything outside the standard image must be raised as an IT "
        "Request with business justification and will be reviewed within 48 hours.",
        "VPN access is mandatory when connecting to internal systems from outside the office network.",
    ]),
    "Attendance & Working Hours Policy": ("other", [
        "Standard working hours are 9:30 AM to 6:30 PM, Monday through Friday, with a 15-minute grace "
        "period for check-in. Arrivals beyond the grace period are marked late.",
        "Employees who believe their attendance was recorded incorrectly may raise a regularisation request "
        "from the Attendance screen, which routes to their manager for approval.",
    ]),
}

chunk_counter = 0
for doc_name, (doc_type, paragraphs) in POLICY_DOCS.items():
    doc = HRPolicyDocument(
        org_id=org.org_id, document_name=doc_name, document_type=doc_type,
        file_path=f"policy-docs/{doc_name.lower().replace(' ', '_')}.pdf",
        is_active=True, indexed_in_chromadb=False,  # True once you wire up the real ChromaDB pipeline
    )
    db.add(doc)
    db.flush()
    for idx, para in enumerate(paragraphs):
        chunk_counter += 1
        db.add(RagDocumentChunk(
            document_id=doc.document_id, chunk_index=idx, chunk_text=para,
            chromadb_chunk_id=f"mock-chunk-{chunk_counter:04d}",
            token_count=len(para.split()),
        ))

# -------------------------------------------------------- E. ATTENDANCE ---

month_start = today.replace(day=1)
for e in ALL_EMPLOYEES:
    present = absent = wfh = on_leave = late = 0
    total_hours = 0.0
    d = month_start
    while d <= today:
        if d.weekday() >= 5:
            d += timedelta(days=1)
            continue
        roll = random.random()
        if roll < 0.78:
            status, is_late = "present", random.random() < 0.1
            check_in = datetime.combine(d, dtime(9, 30 + (20 if is_late else 0)))
            check_out = datetime.combine(d, dtime(18, 30))
            present += 1
            late += 1 if is_late else 0
            total_hours += 9.0
        elif roll < 0.90:
            status, is_late = "wfh", False
            check_in = datetime.combine(d, dtime(9, 30))
            check_out = datetime.combine(d, dtime(18, 30))
            wfh += 1
            total_hours += 9.0
        elif roll < 0.96:
            status, is_late, check_in, check_out = "on_leave", False, None, None
            on_leave += 1
        else:
            status, is_late, check_in, check_out = "absent", False, None, None
            absent += 1

        db.add(AttendanceRecord(
            employee_id=e.employee_id, attendance_date=d, check_in_time=check_in,
            check_out_time=check_out, status=status, is_late=is_late, source="system",
        ))
        d += timedelta(days=1)

    db.add(AttendanceMonthlySummary(
        employee_id=e.employee_id, year=today.year, month=today.month,
        total_working_days=present + absent + wfh + on_leave,
        days_present=present, days_absent=absent, days_wfh=wfh, days_on_leave=on_leave,
        late_arrivals=late, total_hours_worked=round(total_hours, 2), last_computed_at=now(),
    ))

personal_logins = [(e.full_name, e.role, e.email) for e in [kavya, rohan, sneha]]
shared_logins   = [(e.full_name, e.role, e.email) for e in [priya, arjun]]

db.commit()
db.close()

print("\nDone. Demo logins (mock SSO — any of these emails work, no password, see app/security.py):\n")
print("Individual accounts (personal HR data — leave/payslips/attendance):")
print(f"  {'Name':<20} {'Role':<12} {'Email'}")
for full_name, role, email in personal_logins:
    print(f"  {full_name:<20} {role:<12} {email}")

print("\nShared functional accounts (NOT people — see employees.is_shared_admin):")
print(f"  {'Name':<20} {'Role':<12} {'Email'}")
for full_name, role, email in shared_logins:
    print(f"  {full_name:<20} {role:<12} {email}")
print("  In production these are reached via Entra ID group membership (any HR/IT")
print("  staff member added to the mapped group), not a single named login — see")
print("  ENTRA_HR_ADMIN_GROUP_ID / ENTRA_IT_ADMIN_GROUP_ID in backend/.env.example.")
print("\nLog in with any of the above emails on the Login screen.")
