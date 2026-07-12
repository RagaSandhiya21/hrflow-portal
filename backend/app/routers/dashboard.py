from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_employee
from app.models import (
    Employee, EmployeeLeaveBalance, LeaveType, LeaveRequest, Payslip,
    HRRequest, ITRequest, Notification, AttendanceMonthlySummary,
    ProfileChangeRequest,
)
from app.schemas import DashboardSummary, EmployeeOut, LeaveBalanceMini

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db), current: Employee = Depends(get_current_employee)):
    year  = date.today().year
    month = date.today().month

    # Leave balances
    balances = (
        db.query(EmployeeLeaveBalance, LeaveType)
        .join(LeaveType, LeaveType.leave_type_id == EmployeeLeaveBalance.leave_type_id)
        .filter(EmployeeLeaveBalance.employee_id == current.employee_id,
                EmployeeLeaveBalance.year == year)
        .all()
    )
    leave_balances = [
        LeaveBalanceMini(
            leave_type_name=lt.leave_type_name,
            leave_code=lt.leave_code,
            available_days=float(bal.available_days or 0),
        )
        for bal, lt in balances
    ]

    pending_leave = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.employee_id == current.employee_id,
                LeaveRequest.status == "pending")
        .count()
    )

    latest_payslip = (
        db.query(Payslip)
        .filter(Payslip.employee_id == current.employee_id, Payslip.is_published.is_(True))
        .order_by(Payslip.payslip_month.desc())
        .first()
    )

    open_hr = (
        db.query(HRRequest)
        .filter(HRRequest.employee_id == current.employee_id,
                HRRequest.status.notin_(["resolved", "closed", "cancelled"]))
        .count()
    )
    open_it = (
        db.query(ITRequest)
        .filter(ITRequest.employee_id == current.employee_id,
                ITRequest.status.notin_(["resolved", "closed"]))
        .count()
    )

    # Pending approvals
    pending_approvals = 0
    if current.role == "manager":
        report_ids = [
            e.employee_id for e in
            db.query(Employee.employee_id).filter(Employee.manager_id == current.employee_id).all()
        ]
        pending_approvals = (
            db.query(LeaveRequest)
            .filter(LeaveRequest.employee_id.in_(report_ids or [-1]),
                    LeaveRequest.status == "pending")
            .count()
        )
    elif current.role == "hr_admin":
        pending_approvals = db.query(LeaveRequest).filter(LeaveRequest.status == "pending").count()

    # Unread notifications
    unread = (
        db.query(Notification)
        .filter(Notification.recipient_id == current.employee_id,
                Notification.is_read.is_(False))
        .count()
    )

    # Attendance summary for current month
    att = (
        db.query(AttendanceMonthlySummary)
        .filter(
            AttendanceMonthlySummary.employee_id == current.employee_id,
            AttendanceMonthlySummary.year  == year,
            AttendanceMonthlySummary.month == month,
        )
        .first()
    )
    attendance_summary = {
        "days_present":       att.days_present       if att else 0,
        "days_absent":        att.days_absent         if att else 0,
        "days_wfh":           att.days_wfh            if att else 0,
        "days_on_leave":      att.days_on_leave       if att else 0,
        "late_arrivals":      att.late_arrivals       if att else 0,
        "total_hours_worked": float(att.total_hours_worked or 0) if att else 0,
    }

    # HR Admin: pending profile change requests count
    pending_change_requests = 0
    if current.role in ("hr_admin", "super_admin"):
        pending_change_requests = (
            db.query(ProfileChangeRequest)
            .filter(ProfileChangeRequest.status == "pending")
            .count()
        )

    return DashboardSummary(
        employee=EmployeeOut.model_validate(current),
        leave_balances=leave_balances,
        pending_leave_requests=pending_leave,
        latest_payslip_month=latest_payslip.payslip_month.strftime("%B %Y") if latest_payslip else None,
        open_hr_requests=open_hr,
        open_it_requests=open_it,
        pending_approvals=pending_approvals,
        unread_notifications=unread,
        attendance_summary=attendance_summary,
        pending_change_requests=pending_change_requests,
    )
