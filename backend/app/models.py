"""
SQLAlchemy models mapped onto the tables created by db/schema.sql.

IMPORTANT: this file does NOT create tables. Run db/schema.sql against your
Postgres database first (see README), then these models read/write the
tables it defines. This keeps the hand-tuned CHECK constraints, generated
columns, and ON DELETE rules in the schema as the single source of truth
instead of duplicating (and risking drifting from) them here.

Scope note: this maps the Tier 1 + Tier 2 tables from the schema's "Build
Priority Guide" (auth, leave, payroll/payslips, profile, HR requests,
attendance, IT requests, chatbot/RAG, notifications) — the tables the
frontend in this zip actually uses. Tier 3 tables (announcements, assets,
education/work-experience, documents, system_config) exist in the DB but
have no models/endpoints here; add them the same way if you build those
screens out.
"""
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, Date, DateTime,
    Numeric, SmallInteger, ForeignKey, Computed,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from app.database import Base


# ---------------------------------------------------------------- A. ORG ---

class Organisation(Base):
    __tablename__ = "organisations"
    org_id = Column(Integer, primary_key=True)
    org_name = Column(String(150), nullable=False)
    org_code = Column(String(30), nullable=False, unique=True)
    currency_code = Column(String(3))


class Department(Base):
    __tablename__ = "departments"
    department_id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.org_id"), nullable=False)
    department_name = Column(String(100), nullable=False)
    department_code = Column(String(20), nullable=False)
    head_employee_id = Column(Integer, ForeignKey("employees.employee_id"))
    is_active = Column(Boolean, default=True)


class Team(Base):
    __tablename__ = "teams"
    team_id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.org_id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.department_id"), nullable=False)
    team_name = Column(String(100), nullable=False)
    team_code = Column(String(20), nullable=False, unique=True)
    lead_employee_id = Column(Integer, ForeignKey("employees.employee_id"))
    is_active = Column(Boolean, default=True)


class Designation(Base):
    __tablename__ = "designations"
    designation_id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.org_id"), nullable=False)
    title = Column(String(100), nullable=False)
    level = Column(String(30))
    is_active = Column(Boolean, default=True)


class Location(Base):
    __tablename__ = "locations"
    location_id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.org_id"), nullable=False)
    location_name = Column(String(100), nullable=False)
    city = Column(String(80))
    state = Column(String(80))
    country = Column(String(80))
    is_active = Column(Boolean, default=True)


class Employee(Base):
    __tablename__ = "employees"
    employee_id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.org_id"), nullable=False)
    employee_code = Column(String(30), nullable=False, unique=True)
    entra_object_id = Column(String(128), unique=True)  # NULL for shared admin accounts
    email = Column(String(255), nullable=False, unique=True)
    work_email = Column(String(255), unique=True)
    full_name = Column(String(150), nullable=False)
    first_name = Column(String(75), nullable=False)
    last_name = Column(String(75), nullable=False)
    display_name = Column(String(100))
    phone = Column(String(20))
    work_phone = Column(String(20))
    gender = Column(String(20))
    date_of_birth = Column(Date)
    marital_status = Column(String(15))
    profile_photo_url = Column(Text)
    designation_id = Column(Integer, ForeignKey("designations.designation_id"))
    department_id = Column(Integer, ForeignKey("departments.department_id"))
    team_id = Column(Integer, ForeignKey("teams.team_id"))
    location_id = Column(Integer, ForeignKey("locations.location_id"))
    manager_id = Column(Integer, ForeignKey("employees.employee_id"))
    date_of_joining = Column(Date)
    date_of_confirmation = Column(Date)
    employment_type = Column(String(20), default="full_time")
    employment_status = Column(String(20), default="active")
    role = Column(String(20), nullable=False, default="employee")
    last_working_day = Column(Date)
    # Shared functional-role accounts (HR Admin / IT Admin) — see schema.sql
    # comment on employees.is_shared_admin. These rows represent a ROLE that
    # multiple real people share access to (via Entra ID group membership),
    # not an individual employee, and must never carry personal HR data.
    is_shared_admin = Column(Boolean, nullable=False, default=False)
    entra_group_id = Column(String(128))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    department = relationship("Department", foreign_keys=[department_id])
    team = relationship("Team", foreign_keys=[team_id])
    designation = relationship("Designation", foreign_keys=[designation_id])
    manager = relationship("Employee", remote_side=[employee_id])


class AdminAccountAccessLog(Base):
    """
    Accountability trail for the shared HR Admin / IT Admin accounts.
    Every SSO login into a shared account writes a row here capturing WHO
    (the real logged-in person, straight off their Entra ID token) used it,
    when, and from where — independent of any personal employee record.
    """
    __tablename__ = "admin_account_access_log"
    access_log_id = Column(BigInteger, primary_key=True)
    admin_employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    acting_entra_oid = Column(String(128), nullable=False)
    acting_email = Column(String(255), nullable=False)
    acting_display_name = Column(String(150))
    ip_address = Column(String(45))
    user_agent = Column(Text)
    logged_in_at = Column(DateTime)


# ------------------------------------------------------------ C. PROFILE ---

class EmployeeAddress(Base):
    __tablename__ = "employee_addresses"
    address_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    address_type = Column(String(20), nullable=False)
    address_line1 = Column(Text, nullable=False)
    address_line2 = Column(Text)
    city = Column(String(80), nullable=False)
    state = Column(String(80), nullable=False)
    country = Column(String(80), default="India")
    pincode = Column(String(20))
    updated_at = Column(DateTime)


class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"
    contact_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    contact_name = Column(String(150), nullable=False)
    relationship_ = Column("relationship", String(50))
    phone = Column(String(20), nullable=False)
    alternate_phone = Column(String(20))
    email = Column(String(255))
    is_primary = Column(Boolean, default=False)
    updated_at = Column(DateTime)


class EmployeeIdentityInfo(Base):
    __tablename__ = "employee_identity_info"
    identity_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False, unique=True)
    pan_number = Column(String(15))
    aadhaar_number = Column(String(20))
    passport_number = Column(String(20))
    uan_number = Column(String(20))
    esi_number = Column(String(20))
    bank_account_number = Column(String(30))
    bank_name = Column(String(100))
    bank_ifsc = Column(String(20))
    bank_branch = Column(String(100))
    bank_account_type = Column(String(20), default="savings")
    updated_at = Column(DateTime)
    updated_by = Column(Integer, ForeignKey("employees.employee_id"))


class ProfileChangeRequest(Base):
    __tablename__ = "profile_change_requests"
    change_request_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    field_group = Column(String(30), nullable=False)
    field_name = Column(String(60), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text, nullable=False)
    reason = Column(Text)
    status = Column(String(20), default="pending")
    requested_at = Column(DateTime)
    reviewed_by = Column(Integer, ForeignKey("employees.employee_id"))
    reviewed_at = Column(DateTime)
    reviewer_notes = Column(Text)


# -------------------------------------------------------- D. LEAVE MGMT ---

class LeaveType(Base):
    __tablename__ = "leave_types"
    leave_type_id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.org_id"), nullable=False)
    leave_type_name = Column(String(60), nullable=False)
    leave_code = Column(String(10), nullable=False)
    description = Column(Text)
    annual_quota = Column(Numeric(5, 1), nullable=False)
    monthly_quota = Column(Numeric(4, 1))
    carryover_allowed = Column(Boolean, default=False)
    max_carryover_days = Column(Numeric(5, 1), default=0)
    half_day_allowed = Column(Boolean, default=True)
    requires_document = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)


class HolidayCalendar(Base):
    __tablename__ = "holiday_calendar"
    holiday_id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.org_id"), nullable=False)
    holiday_date = Column(Date, nullable=False)
    holiday_name = Column(String(100), nullable=False)
    holiday_type = Column(String(20), default="public")


class EmployeeLeaveBalance(Base):
    __tablename__ = "employee_leave_balances"
    balance_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    leave_type_id = Column(Integer, ForeignKey("leave_types.leave_type_id"), nullable=False)
    year = Column(SmallInteger, nullable=False)
    total_allotted = Column(Numeric(5, 1), nullable=False)
    carried_over = Column(Numeric(5, 1), default=0)
    used_days = Column(Numeric(5, 1), default=0)
    pending_days = Column(Numeric(5, 1), default=0)
    lapsed_days = Column(Numeric(5, 1), default=0)
    available_days = Column(Numeric(5, 1), Computed(
        "total_allotted + carried_over - used_days - pending_days", persisted=True
    ))
    last_updated = Column(DateTime)


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    leave_request_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    leave_type_id = Column(Integer, ForeignKey("leave_types.leave_type_id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    number_of_days = Column(Numeric(4, 1), nullable=False)
    is_half_day = Column(Boolean, default=False)
    half_day_slot = Column(String(10))
    reason = Column(Text)
    status = Column(String(20), default="pending")
    applied_at = Column(DateTime)
    updated_at = Column(DateTime)


class LeaveApproval(Base):
    __tablename__ = "leave_approvals"
    approval_id = Column(Integer, primary_key=True)
    leave_request_id = Column(Integer, ForeignKey("leave_requests.leave_request_id"), nullable=False)
    approver_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    approval_level = Column(SmallInteger, default=1)
    action = Column(String(20), nullable=False)
    comments = Column(Text)
    actioned_at = Column(DateTime)


# ----------------------------------------------------------- E. ATTENDANCE

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    attendance_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    attendance_date = Column(Date, nullable=False)
    check_in_time = Column(DateTime)
    check_out_time = Column(DateTime)
    total_hours = Column(Numeric(4, 2), Computed(
        "EXTRACT(EPOCH FROM (check_out_time - check_in_time))/3600.0", persisted=True
    ))
    status = Column(String(20), nullable=False)
    is_late = Column(Boolean, default=False)
    is_early_exit = Column(Boolean, default=False)
    source = Column(String(20), default="system")
    remarks = Column(Text)
    is_regularised = Column(Boolean, default=False)


class AttendanceRegularisation(Base):
    __tablename__ = "attendance_regularisation"
    regularisation_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    attendance_date = Column(Date, nullable=False)
    requested_check_in = Column(DateTime)
    requested_check_out = Column(DateTime)
    requested_status = Column(String(20))
    reason = Column(Text, nullable=False)
    status = Column(String(20), default="pending")
    requested_at = Column(DateTime)
    reviewed_by = Column(Integer, ForeignKey("employees.employee_id"))
    reviewed_at = Column(DateTime)
    reviewer_comments = Column(Text)


class AttendanceMonthlySummary(Base):
    __tablename__ = "attendance_monthly_summary"
    summary_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    year = Column(SmallInteger, nullable=False)
    month = Column(SmallInteger, nullable=False)
    total_working_days = Column(SmallInteger, default=0)
    days_present = Column(SmallInteger, default=0)
    days_absent = Column(SmallInteger, default=0)
    days_wfh = Column(SmallInteger, default=0)
    days_on_leave = Column(SmallInteger, default=0)
    late_arrivals = Column(SmallInteger, default=0)
    total_hours_worked = Column(Numeric(6, 2), default=0)
    last_computed_at = Column(DateTime)


# ------------------------------------------------------ F. PAYROLL & PAY ---

class SalaryComponent(Base):
    __tablename__ = "salary_components"
    component_id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.org_id"), nullable=False)
    component_name = Column(String(80), nullable=False)
    component_code = Column(String(20), nullable=False)
    component_type = Column(String(25), nullable=False)


class EmployeeSalaryStructure(Base):
    __tablename__ = "employee_salary_structure"
    structure_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    component_id = Column(Integer, ForeignKey("salary_components.component_id"), nullable=False)
    amount = Column(Numeric(12, 2), default=0)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    created_at = Column(DateTime)


class MonthlyPayroll(Base):
    __tablename__ = "monthly_payroll"
    payroll_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    payroll_month = Column(Date, nullable=False)
    basic_salary = Column(Numeric(12, 2), default=0)
    hra = Column(Numeric(12, 2), default=0)
    transport_allowance = Column(Numeric(12, 2), default=0)
    medical_allowance = Column(Numeric(12, 2), default=0)
    special_allowance = Column(Numeric(12, 2), default=0)
    performance_bonus = Column(Numeric(12, 2), default=0)
    other_earnings = Column(Numeric(12, 2), default=0)
    gross_earnings = Column(Numeric(12, 2), Computed(
        "basic_salary + hra + transport_allowance + medical_allowance + "
        "special_allowance + performance_bonus + other_earnings", persisted=True
    ))
    pf_employee = Column(Numeric(12, 2), default=0)
    esi_employee = Column(Numeric(12, 2), default=0)
    professional_tax = Column(Numeric(12, 2), default=0)
    tds = Column(Numeric(12, 2), default=0)
    loan_deduction = Column(Numeric(12, 2), default=0)
    loss_of_pay = Column(Numeric(12, 2), default=0)
    other_deductions = Column(Numeric(12, 2), default=0)
    total_deductions = Column(Numeric(12, 2), Computed(
        "pf_employee + esi_employee + professional_tax + tds + loan_deduction + "
        "loss_of_pay + other_deductions", persisted=True
    ))
    net_salary = Column(Numeric(12, 2), Computed(
        "basic_salary + hra + transport_allowance + medical_allowance + special_allowance + "
        "performance_bonus + other_earnings - pf_employee - esi_employee - professional_tax - "
        "tds - loan_deduction - loss_of_pay - other_deductions", persisted=True
    ))
    days_worked = Column(SmallInteger)
    total_working_days = Column(SmallInteger)
    days_on_lop = Column(SmallInteger, default=0)
    payroll_status = Column(String(20), default="draft")
    payment_date = Column(Date)


class Payslip(Base):
    __tablename__ = "payslips"
    payslip_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    payroll_id = Column(Integer, ForeignKey("monthly_payroll.payroll_id"), nullable=False)
    payslip_month = Column(Date, nullable=False)
    pdf_path = Column(Text, nullable=False)
    generated_at = Column(DateTime)
    last_downloaded_at = Column(DateTime)
    download_count = Column(Integer, default=0)
    is_published = Column(Boolean, default=False)
    published_at = Column(DateTime)


# --------------------------------------------------------- G. HR REQUESTS ---

class HRRequestCategory(Base):
    __tablename__ = "hr_request_categories"
    category_id = Column(Integer, primary_key=True)
    category_name = Column(String(80), nullable=False, unique=True)
    description = Column(Text)
    default_priority = Column(String(10), default="normal")
    sla_hours = Column(SmallInteger, default=48)
    is_active = Column(Boolean, default=True)


class HRRequest(Base):
    __tablename__ = "hr_requests"
    hr_request_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    category_id = Column(Integer, ForeignKey("hr_request_categories.category_id"), nullable=False)
    subject = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(10), default="normal")
    status = Column(String(20), default="open")
    raised_at = Column(DateTime)
    updated_at = Column(DateTime)
    assigned_to = Column(Integer, ForeignKey("employees.employee_id"))
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)


class HRRequestComment(Base):
    __tablename__ = "hr_request_comments"
    comment_id = Column(Integer, primary_key=True)
    hr_request_id = Column(Integer, ForeignKey("hr_requests.hr_request_id"), nullable=False)
    commenter_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    comment_text = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False)
    created_at = Column(DateTime)


# --------------------------------------------------------- H. IT REQUESTS ---

class ITRequest(Base):
    __tablename__ = "it_requests"
    it_request_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    request_type = Column(String(40), nullable=False)
    subject = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(10), default="normal")
    status = Column(String(20), default="open")
    raised_at = Column(DateTime)
    updated_at = Column(DateTime)
    assigned_to = Column(Integer, ForeignKey("employees.employee_id"))
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)


class ITRequestStatusHistory(Base):
    __tablename__ = "it_request_status_history"
    history_id = Column(Integer, primary_key=True)
    it_request_id = Column(Integer, ForeignKey("it_requests.it_request_id"), nullable=False)
    old_status = Column(String(20))
    new_status = Column(String(20), nullable=False)
    changed_by = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    notes = Column(Text)
    changed_at = Column(DateTime)


# ------------------------------------------------------ K. CHATBOT & RAG ---

class HRPolicyDocument(Base):
    __tablename__ = "hr_policy_documents"
    document_id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.org_id"), nullable=False)
    document_name = Column(String(255), nullable=False)
    document_type = Column(String(40), nullable=False)
    file_path = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    indexed_in_chromadb = Column(Boolean, default=False)


class RagDocumentChunk(Base):
    __tablename__ = "rag_document_chunks"
    chunk_id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("hr_policy_documents.document_id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    token_count = Column(Integer)
    chromadb_chunk_id = Column(String(128), nullable=False, unique=True)


class ChatbotSession(Base):
    __tablename__ = "chatbot_sessions"
    session_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    total_messages = Column(Integer, default=0)


class ChatbotQueryLog(Base):
    __tablename__ = "chatbot_query_log"
    query_id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("chatbot_sessions.session_id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    query_text = Column(Text, nullable=False)
    query_category = Column(String(40))
    retrieved_chunk_ids = Column(ARRAY(String))
    source_documents = Column(ARRAY(String))
    llm_model_used = Column(String(60))
    llm_response = Column(Text)
    confidence_score = Column(Numeric(4, 3))
    is_grounded = Column(Boolean)
    is_escalated = Column(Boolean, default=False)
    asked_at = Column(DateTime)
    response_latency_ms = Column(Integer)
    user_feedback = Column(SmallInteger)


class EscalationTicket(Base):
    __tablename__ = "escalation_tickets"
    escalation_id = Column(Integer, primary_key=True)
    query_id = Column(Integer, ForeignKey("chatbot_query_log.query_id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    escalated_query = Column(Text, nullable=False)
    escalation_reason = Column(String(50), default="low_confidence")
    status = Column(String(20), default="open")
    assigned_to = Column(Integer, ForeignKey("employees.employee_id"))
    escalated_at = Column(DateTime)
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)


# --------------------------------------------------------- L. NOTIFICATIONS

class Notification(Base):
    __tablename__ = "notifications"
    notification_id = Column(BigInteger, primary_key=True)
    recipient_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    notification_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    deep_link = Column(Text)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime)
    created_at = Column(DateTime)
