from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_employee, require_personal_employee, require_role
from app.models import (
    Employee, LeaveType, LeaveRequest, LeaveApproval, EmployeeLeaveBalance,
    AttendanceRecord, HolidayCalendar,
)
from app.schemas import (
    LeaveTypeOut, LeaveBalanceOut, LeaveRequestCreate, LeaveRequestOut, LeaveDecision,
)
from app.utils import count_business_days
from app.email_service import (
    notify_leave_applied, notify_leave_decision,
)
from app.notification_service import notify

router = APIRouter(prefix="/leave", tags=["leave"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize_request(db: Session, lr: LeaveRequest) -> LeaveRequestOut:
    emp = db.query(Employee).filter(Employee.employee_id == lr.employee_id).first()
    lt  = db.query(LeaveType).filter(LeaveType.leave_type_id == lr.leave_type_id).first()
    out = LeaveRequestOut.model_validate(lr)
    out.employee_name   = emp.full_name if emp else None
    out.leave_type_name = lt.leave_type_name if lt else None
    return out


def _sync_attendance(db: Session, lr: LeaveRequest, leave_type: LeaveType, action: str):
    """
    Sync attendance records for the leave date range.
    action='pending'  → write record immediately when applied
    action='approve'  → keep/update record
    action='reject'   → delete records written by this leave
    Allowed source values (DB CHECK constraint): system, biometric, manual, regularised
    """
    is_wfh     = leave_type.leave_code == "WFH"
    att_status = "wfh" if is_wfh else "on_leave"
    remark_tag = f"leave_req_{lr.leave_request_id}"

    emp    = db.query(Employee).filter(Employee.employee_id == lr.employee_id).first()
    org_id = emp.org_id if emp else None

    day = lr.start_date
    while day <= lr.end_date:
        if day.weekday() >= 5:          # skip weekends
            day += timedelta(days=1)
            continue

        is_holiday = False
        if org_id:
            is_holiday = db.query(HolidayCalendar).filter(
                HolidayCalendar.org_id == org_id,
                HolidayCalendar.holiday_date == day,
            ).first() is not None

        if not is_holiday:
            existing = db.query(AttendanceRecord).filter(
                AttendanceRecord.employee_id     == lr.employee_id,
                AttendanceRecord.attendance_date == day,
            ).first()

            if action in ("pending", "approve"):
                if existing:
                    existing.status  = att_status
                    existing.source  = "manual"
                    existing.remarks = remark_tag
                else:
                    db.add(AttendanceRecord(
                        employee_id     = lr.employee_id,
                        attendance_date = day,
                        status          = att_status,
                        source          = "manual",
                        remarks         = remark_tag,
                    ))
            elif action == "reject":
                if existing and existing.remarks == remark_tag:
                    db.delete(existing)

        day += timedelta(days=1)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/types", response_model=list[LeaveTypeOut])
def list_leave_types(
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    return (
        db.query(LeaveType)
        .filter(LeaveType.org_id == current.org_id, LeaveType.is_active.is_(True))
        .order_by(LeaveType.leave_type_name)
        .all()
    )


@router.get("/balances", response_model=list[LeaveBalanceOut])
def my_balances(
    year: int = date.today().year,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    rows = (
        db.query(EmployeeLeaveBalance, LeaveType)
        .join(LeaveType, LeaveType.leave_type_id == EmployeeLeaveBalance.leave_type_id)
        .filter(
            EmployeeLeaveBalance.employee_id == current.employee_id,
            EmployeeLeaveBalance.year        == year,
        )
        .all()
    )
    out = []
    for balance, leave_type in rows:
        item = LeaveBalanceOut.model_validate(balance)
        item.leave_type_name = leave_type.leave_type_name
        item.leave_code      = leave_type.leave_code
        out.append(item)
    return out


@router.get("/requests", response_model=list[LeaveRequestOut])
def my_requests(
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    rows = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.employee_id == current.employee_id)
        .order_by(LeaveRequest.applied_at.desc())
        .all()
    )
    return [_serialize_request(db, r) for r in rows]


@router.get("/requests/team", response_model=list[LeaveRequestOut])
def team_requests(
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("manager", "hr_admin")),
):
    query = db.query(LeaveRequest).filter(LeaveRequest.status == "pending")
    if current.role == "manager":
        report_ids = [
            e.employee_id for e in
            db.query(Employee.employee_id)
            .filter(Employee.manager_id == current.employee_id).all()
        ]
        query = query.filter(LeaveRequest.employee_id.in_(report_ids or [-1]))
    return [
        _serialize_request(db, r)
        for r in query.order_by(LeaveRequest.applied_at.asc()).all()
    ]


@router.post("/requests", response_model=LeaveRequestOut, status_code=status.HTTP_201_CREATED)
def apply_leave(
    body: LeaveRequestCreate,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    if body.end_date < body.start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")

    leave_type = db.query(LeaveType).filter(LeaveType.leave_type_id == body.leave_type_id).first()
    if leave_type is None:
        raise HTTPException(status_code=404, detail="Leave type not found")

    if body.is_half_day:
        if body.start_date != body.end_date:
            raise HTTPException(status_code=400, detail="Half-day: start and end must be same date")
        if not leave_type.half_day_allowed:
            raise HTTPException(status_code=400, detail=f"{leave_type.leave_type_name} does not allow half-day")
        number_of_days = 0.5
    else:
        number_of_days = count_business_days(db, current.org_id, body.start_date, body.end_date)
        if number_of_days <= 0:
            raise HTTPException(status_code=400, detail="No working days in selected range (weekends/holidays excluded)")

    balance = (
        db.query(EmployeeLeaveBalance)
        .filter(
            EmployeeLeaveBalance.employee_id   == current.employee_id,
            EmployeeLeaveBalance.leave_type_id == body.leave_type_id,
            EmployeeLeaveBalance.year          == body.start_date.year,
        )
        .first()
    )
    if balance is None:
        raise HTTPException(status_code=400, detail="No leave balance allocated for this leave type this year")
    if float(balance.available_days or 0) < number_of_days:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance: {balance.available_days} available, {number_of_days} requested",
        )

    lr = LeaveRequest(
        employee_id    = current.employee_id,
        leave_type_id  = body.leave_type_id,
        start_date     = body.start_date,
        end_date       = body.end_date,
        number_of_days = number_of_days,
        is_half_day    = body.is_half_day,
        half_day_slot  = body.half_day_slot,
        reason         = body.reason,
        status         = "pending",
        applied_at     = datetime.utcnow(),
        updated_at     = datetime.utcnow(),
    )
    db.add(lr)
    balance.pending_days = float(balance.pending_days or 0) + number_of_days
    db.flush()

    # Write to attendance immediately — visible in calendar before approval
    try:
        _sync_attendance(db, lr, leave_type, "pending")
    except Exception as e:
        print(f"[attendance-sync] apply: {e}")

    db.commit()
    db.refresh(lr)

    # Email manager
    try:
        manager = db.query(Employee).filter(Employee.employee_id == current.manager_id).first()
        if manager and (manager.work_email or manager.email):
            notify_leave_applied(
                manager_email=manager.work_email or manager.email,
                manager_name=manager.full_name,
                emp_name=current.full_name,
                leave_type=leave_type.leave_type_name,
                start=str(body.start_date),
                end=str(body.end_date),
                days=number_of_days,
            )
        if manager:
            notify(db, manager.employee_id, "leave_applied",
                   f"Leave Request — {current.full_name}",
                   f"{current.full_name} applied for {leave_type.leave_type_name} "
                   f"({body.start_date} to {body.end_date}). Needs your approval.",
                   deep_link=f"/leave/requests/{lr.leave_request_id}")
            db.commit()
    except Exception as e:
        print(f"[email] apply notify failed: {e}")

    return _serialize_request(db, lr)


@router.post("/requests/{leave_request_id}/decision", response_model=LeaveRequestOut)
def decide_leave(
    leave_request_id: int,
    body: LeaveDecision,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("manager", "hr_admin")),
):
    lr = db.query(LeaveRequest).filter(LeaveRequest.leave_request_id == leave_request_id).first()
    if lr is None:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if lr.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {lr.status}")

    if current.role == "manager":
        applicant = db.query(Employee).filter(Employee.employee_id == lr.employee_id).first()
        if applicant is None or applicant.manager_id != current.employee_id:
            raise HTTPException(status_code=403, detail="You can only act on your direct reports' requests")

    leave_type = db.query(LeaveType).filter(LeaveType.leave_type_id == lr.leave_type_id).first()
    applicant  = db.query(Employee).filter(Employee.employee_id == lr.employee_id).first()

    # Update balance
    balance = (
        db.query(EmployeeLeaveBalance)
        .filter(
            EmployeeLeaveBalance.employee_id   == lr.employee_id,
            EmployeeLeaveBalance.leave_type_id == lr.leave_type_id,
            EmployeeLeaveBalance.year          == lr.start_date.year,
        )
        .first()
    )
    if balance:
        balance.pending_days = max(0.0, float(balance.pending_days or 0) - float(lr.number_of_days))
        if body.decision == "approved":
            balance.used_days = float(balance.used_days or 0) + float(lr.number_of_days)

    # Sync attendance
    if leave_type:
        try:
            action = "approve" if body.decision == "approved" else "reject"
            _sync_attendance(db, lr, leave_type, action)
        except Exception as e:
            print(f"[attendance-sync] decide: {e}")

    lr.status     = body.decision
    lr.updated_at = datetime.utcnow()
    db.add(LeaveApproval(
        leave_request_id = lr.leave_request_id,
        approver_id      = current.employee_id,
        approval_level   = 1 if current.role == "manager" else 2,
        action           = body.decision,
        comments         = body.comments,
        actioned_at      = datetime.utcnow(),
    ))
    db.commit()
    db.refresh(lr)

    # Email employee
    try:
        if applicant and (applicant.work_email or applicant.email) and leave_type:
            notify_leave_decision(
                emp_email  = applicant.work_email or applicant.email,
                emp_name   = applicant.full_name,
                decision   = body.decision,
                leave_type = leave_type.leave_type_name,
                start      = str(lr.start_date),
                end        = str(lr.end_date),
                comments   = body.comments or "",
            )
        if applicant:
            notify(db, applicant.employee_id, "leave_decision",
                   f"Leave {body.decision.title()}",
                   f"Your {leave_type.leave_type_name if leave_type else 'leave'} request "
                   f"({lr.start_date} to {lr.end_date}) was {body.decision}.",
                   deep_link=f"/leave/requests/{lr.leave_request_id}")
            db.commit()
    except Exception as e:
        print(f"[email] decide notify failed: {e}")

    return _serialize_request(db, lr)


@router.delete("/requests/{leave_request_id}", response_model=LeaveRequestOut)
def withdraw_leave(
    leave_request_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    lr = db.query(LeaveRequest).filter(LeaveRequest.leave_request_id == leave_request_id).first()
    if lr is None:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if lr.employee_id != current.employee_id:
        raise HTTPException(status_code=403, detail="You can only withdraw your own requests")
    if lr.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot withdraw — already {lr.status}")

    leave_type = db.query(LeaveType).filter(LeaveType.leave_type_id == lr.leave_type_id).first()
    balance = (
        db.query(EmployeeLeaveBalance)
        .filter(
            EmployeeLeaveBalance.employee_id   == lr.employee_id,
            EmployeeLeaveBalance.leave_type_id == lr.leave_type_id,
            EmployeeLeaveBalance.year          == lr.start_date.year,
        )
        .first()
    )
    if balance:
        balance.pending_days = max(0.0, float(balance.pending_days or 0) - float(lr.number_of_days))

    if leave_type:
        try:
            _sync_attendance(db, lr, leave_type, "reject")
        except Exception as e:
            print(f"[attendance-sync] withdraw: {e}")

    lr.status     = "withdrawn"
    lr.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(lr)
    return _serialize_request(db, lr)


# ── Year-end carryover (HR Admin triggered) ───────────────────────────────────

@router.post("/admin/year-end-carryover")
def year_end_carryover(
    year: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    """
    Runs the year-end carryover for all employees in the org.
    - Privilege Leave (PL): carries over up to max_carryover_days into next year
    - Casual/Sick: lapse at year-end (no carryover)
    Run this on Dec 31 or Jan 1 for the closing year.
    """
    leave_types = (
        db.query(LeaveType)
        .filter(LeaveType.org_id == current.org_id, LeaveType.is_active.is_(True))
        .all()
    )
    next_year   = year + 1
    processed   = 0
    carried_total = 0

    for lt in leave_types:
        balances = (
            db.query(EmployeeLeaveBalance)
            .filter(
                EmployeeLeaveBalance.leave_type_id == lt.leave_type_id,
                EmployeeLeaveBalance.year          == year,
            )
            .all()
        )
        for bal in balances:
            available    = float(bal.available_days or 0)
            carry_amount = 0.0

            if lt.carryover_allowed and available > 0:
                max_carry    = float(lt.max_carryover_days or 0)
                carry_amount = min(available, max_carry)

            # Check if next-year balance already exists
            existing_next = (
                db.query(EmployeeLeaveBalance)
                .filter(
                    EmployeeLeaveBalance.employee_id   == bal.employee_id,
                    EmployeeLeaveBalance.leave_type_id == lt.leave_type_id,
                    EmployeeLeaveBalance.year          == next_year,
                )
                .first()
            )
            if existing_next:
                existing_next.carried_over = carry_amount
            else:
                db.add(EmployeeLeaveBalance(
                    employee_id    = bal.employee_id,
                    leave_type_id  = lt.leave_type_id,
                    year           = next_year,
                    total_allotted = lt.annual_quota,
                    carried_over   = carry_amount,
                    used_days      = 0,
                    pending_days   = 0,
                    lapsed_days    = max(0, available - carry_amount),
                    last_updated   = datetime.utcnow(),
                ))

            # Mark current year lapsed
            bal.lapsed_days = max(0, available - carry_amount)
            carried_total  += carry_amount
            processed      += 1

    db.commit()
    return {
        "message":        f"Year-end carryover complete for {year} → {next_year}",
        "employees_processed": processed,
        "total_days_carried":  carried_total,
    }
