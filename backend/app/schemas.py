from datetime import date, datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


# ------------------------------------------------------------------ AUTH ---

class LoginRequest(BaseModel):
    """Dev-only mock-SSO login (see security.py). Ignored when USE_MOCK_SSO=false."""
    email: str


class SSOLoginRequest(BaseModel):
    """Real Microsoft Entra ID login: the id_token MSAL.js returns after sign-in."""
    id_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    employee: "EmployeeOut"
    # Populated when the signed-in identity is a shared HR Admin / IT Admin
    # account, so the frontend can show "Signed in as HR Admin (acting: you@x.com)"
    # instead of implying the account itself is a person.
    acting_display_name: Optional[str] = None
    acting_email: Optional[str] = None


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    employee_id: int
    employee_code: str
    email: str
    full_name: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    profile_photo_url: Optional[str] = None
    role: str
    is_shared_admin: bool = False
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    manager_id: Optional[int] = None
    manager_name: Optional[str] = None
    designation_id: Optional[int] = None
    designation_title: Optional[str] = None
    date_of_joining: Optional[date] = None
    employment_status: Optional[str] = None


# -------------------------------------------------------------- DASHBOARD ---

class LeaveBalanceMini(BaseModel):
    leave_type_name: str
    leave_code: str
    available_days: float


class DashboardSummary(BaseModel):
    employee: EmployeeOut
    leave_balances: List[LeaveBalanceMini]
    pending_leave_requests: int
    latest_payslip_month: Optional[str] = None
    open_hr_requests: int
    open_it_requests: int
    pending_approvals: int = 0
    unread_notifications: int = 0
    attendance_summary: dict = {}
    pending_change_requests: int = 0


# ------------------------------------------------------------------ LEAVE ---

class LeaveTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    leave_type_id: int
    leave_type_name: str
    leave_code: str
    annual_quota: float
    half_day_allowed: bool
    requires_document: bool


class LeaveBalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    leave_type_id: int
    leave_type_name: Optional[str] = None
    leave_code: Optional[str] = None
    year: int
    total_allotted: float
    carried_over: float
    used_days: float
    pending_days: float
    available_days: Optional[float] = None


class LeaveRequestCreate(BaseModel):
    leave_type_id: int
    start_date: date
    end_date: date
    is_half_day: bool = False
    half_day_slot: Optional[str] = None
    reason: Optional[str] = None


class LeaveRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    leave_request_id: int
    employee_id: int
    employee_name: Optional[str] = None
    leave_type_name: Optional[str] = None
    start_date: date
    end_date: date
    number_of_days: float
    is_half_day: bool
    status: str
    reason: Optional[str] = None
    applied_at: Optional[datetime] = None


class LeaveDecision(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    comments: Optional[str] = None


# --------------------------------------------------------------- PAYSLIPS ---

class PayslipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    payslip_id: int
    payroll_id: int
    payslip_month: date
    is_published: bool
    generated_at: Optional[datetime] = None


class PayslipDetail(BaseModel):
    payslip_id: int
    payslip_month: date
    employee_name: str
    employee_code: str
    designation: Optional[str] = None
    department: Optional[str] = None
    basic_salary: float
    hra: float
    transport_allowance: float
    medical_allowance: float
    special_allowance: float
    performance_bonus: float
    other_earnings: float
    gross_earnings: float
    pf_employee: float
    esi_employee: float
    professional_tax: float
    tds: float
    loan_deduction: float
    loss_of_pay: float
    other_deductions: float
    total_deductions: float
    net_salary: float
    days_worked: Optional[int] = None
    payroll_status: str


# ---------------------------------------------------------------- PROFILE ---

class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    address_type: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    country: str
    pincode: Optional[str] = None


class AddressUpdate(BaseModel):
    address_type: str = Field(pattern="^(permanent|current|other)$")
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    country: str = "India"
    pincode: Optional[str] = None


class EmergencyContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    contact_id: int
    contact_name: str
    relationship_: Optional[str] = Field(default=None, alias="relationship")
    phone: str
    alternate_phone: Optional[str] = None
    is_primary: bool

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class EmergencyContactCreate(BaseModel):
    contact_name: str
    relationship: Optional[str] = None
    phone: str
    alternate_phone: Optional[str] = None
    is_primary: bool = False


class ProfileOut(BaseModel):
    employee: EmployeeOut
    addresses: List[AddressOut]
    emergency_contacts: List[EmergencyContactOut]
    identity_masked: dict  # PAN/bank shown masked — see profile.py


class ContactUpdate(BaseModel):
    phone: Optional[str] = None
    profile_photo_url: Optional[str] = None


class HREmployeeEdit(BaseModel):
    """
    HR Admin direct edit of ANY employee's profile — unlike the self-service
    change-request flow (which routes sensitive fields to HR for approval),
    HR Admin itself has direct authority to correct records. Every changed
    field is still written to profile_change_requests (auto-approved, with
    the HR admin as reviewer) so there's a full audit trail of who changed
    what and when, per the proposal's Module 4 requirement.
    """
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    designation_id: Optional[int] = None
    department_id: Optional[int] = None
    team_id: Optional[int] = None
    manager_id: Optional[int] = None
    bank_account_number: Optional[str] = None
    bank_name: Optional[str] = None
    bank_ifsc: Optional[str] = None
    pan_number: Optional[str] = None
    aadhaar_number: Optional[str] = None


class ChangeRequestCreate(BaseModel):
    field_group: str = Field(pattern="^(identity|bank|designation|department|other)$")
    field_name: str
    new_value: str
    reason: Optional[str] = None


class ChangeRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    change_request_id: int
    employee_id: int
    employee_name: Optional[str] = None
    field_group: str
    field_name: str
    old_value: Optional[str] = None
    new_value: str
    reason: Optional[str] = None
    status: str
    requested_at: Optional[datetime] = None


class ChangeRequestDecision(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    reviewer_notes: Optional[str] = None


# ------------------------------------------------------------- HR REQUESTS ---

class HRCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    category_id: int
    category_name: str
    default_priority: str
    sla_hours: int


class HRRequestCreate(BaseModel):
    category_id: int
    subject: str
    description: str
    priority: str = "normal"


class HRRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    hr_request_id: int
    employee_id: int
    employee_name: Optional[str] = None
    category_name: Optional[str] = None
    subject: str
    description: str
    priority: str
    status: str
    raised_at: Optional[datetime] = None


class HRRequestStatusUpdate(BaseModel):
    status: str = Field(pattern="^(open|in_progress|pending_info|resolved|closed|cancelled)$")
    resolution_notes: Optional[str] = None


class HRCommentCreate(BaseModel):
    comment_text: str
    is_internal: bool = False


class HRCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    comment_id: int
    commenter_id: int
    commenter_name: Optional[str] = None
    comment_text: str
    is_internal: bool
    created_at: Optional[datetime] = None


# -------------------------------------------------------------- ATTENDANCE ---

class AttendanceDayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    attendance_date: date
    status: str
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    total_hours: Optional[float] = None
    is_regularised: bool


class AttendanceSummaryOut(BaseModel):
    year: int
    month: int
    total_working_days: int
    days_present: int
    days_absent: int
    days_wfh: int
    days_on_leave: int
    late_arrivals: int
    total_hours_worked: float


class RegularisationCreate(BaseModel):
    attendance_date: date
    requested_check_in: Optional[datetime] = None
    requested_check_out: Optional[datetime] = None
    requested_status: Optional[str] = None
    reason: str


class RegularisationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    regularisation_id: int
    employee_id: int
    employee_name: Optional[str] = None
    attendance_date: date
    reason: str
    status: str
    requested_at: Optional[datetime] = None


class RegularisationDecision(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    reviewer_comments: Optional[str] = None


# -------------------------------------------------------------- IT REQUESTS ---

class ITRequestCreate(BaseModel):
    request_type: str
    subject: str
    description: str
    priority: str = "normal"


class ITRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    it_request_id: int
    employee_id: int
    employee_name: Optional[str] = None
    request_type: str
    subject: str
    description: str
    priority: str
    status: str
    raised_at: Optional[datetime] = None


class ITRequestStatusUpdate(BaseModel):
    status: str = Field(pattern="^(open|in_progress|on_hold|resolved|closed)$")
    notes: Optional[str] = None


# ----------------------------------------------------------------- CHATBOT ---

class ChatQueryCreate(BaseModel):
    session_id: Optional[int] = None
    query_text: str


class ChatQueryOut(BaseModel):
    session_id: int
    query_id: int
    answer: str
    confidence_score: float
    is_grounded: bool
    query_category: Optional[str] = None
    source_documents: List[str] = []


class EscalateRequest(BaseModel):
    query_id: int
    reason: str = "low_confidence"


class EscalationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    escalation_id: int
    query_id: int
    employee_id: int
    employee_name: Optional[str] = None
    escalated_query: Optional[str] = None
    escalation_reason: Optional[str] = None
    status: str
    escalated_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None


# ------------------------------------------------------------- NOTIFICATIONS

class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    notification_id: int
    notification_type: str
    title: str
    message: str
    deep_link: Optional[str] = None
    is_read: bool
    created_at: Optional[datetime] = None


# ------------------------------------------------------ ORG HIERARCHY ---
# Department -> Team -> Employee, managed exclusively by HR Admin
# (per the proposal's Module 1: "Org hierarchy managed exclusively by HR Admin").

class DepartmentIn(BaseModel):
    department_name: str
    department_code: str
    head_employee_id: Optional[int] = None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    department_id: int
    department_name: str
    department_code: str
    head_employee_id: Optional[int] = None
    is_active: bool


class TeamIn(BaseModel):
    department_id: int
    team_name: str
    team_code: str
    lead_employee_id: Optional[int] = None


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    team_id: int
    department_id: int
    team_name: str
    team_code: str
    lead_employee_id: Optional[int] = None
    is_active: bool


class DesignationIn(BaseModel):
    title: str
    level: Optional[str] = None


class DesignationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    designation_id: int
    title: str
    level: Optional[str] = None
    is_active: bool


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    location_id: int
    location_name: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    is_active: bool
