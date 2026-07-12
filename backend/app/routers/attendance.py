from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel as PydanticBase
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_employee, require_role, require_personal_employee
from app.models import (
    Employee, AttendanceRecord, AttendanceMonthlySummary,
    AttendanceRegularisation, HolidayCalendar,
)
from app.schemas import (
    AttendanceDayOut, AttendanceSummaryOut, RegularisationCreate,
    RegularisationOut, RegularisationDecision,
)

router = APIRouter(prefix="/attendance", tags=["attendance"])


# ── My attendance ──────────────────────────────────────────────────────────────

@router.get("/me", response_model=list[AttendanceDayOut])
def my_attendance(
    year:  int = date.today().year,
    month: int = date.today().month,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    next_y = year + 1 if month == 12 else year
    next_m = 1        if month == 12 else month + 1
    return (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.employee_id    == current.employee_id,
            AttendanceRecord.attendance_date >= date(year, month, 1),
            AttendanceRecord.attendance_date <  date(next_y, next_m, 1),
        )
        .order_by(AttendanceRecord.attendance_date.asc())
        .all()
    )


@router.get("/summary", response_model=AttendanceSummaryOut)
def my_summary(
    year:  int = date.today().year,
    month: int = date.today().month,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    s = (
        db.query(AttendanceMonthlySummary)
        .filter(
            AttendanceMonthlySummary.employee_id == current.employee_id,
            AttendanceMonthlySummary.year  == year,
            AttendanceMonthlySummary.month == month,
        )
        .first()
    )
    if s is None:
        return AttendanceSummaryOut(
            year=year, month=month, total_working_days=0, days_present=0,
            days_absent=0, days_wfh=0, days_on_leave=0, late_arrivals=0,
            total_hours_worked=0,
        )
    return AttendanceSummaryOut(
        year=s.year, month=s.month,
        total_working_days=s.total_working_days, days_present=s.days_present,
        days_absent=s.days_absent, days_wfh=s.days_wfh, days_on_leave=s.days_on_leave,
        late_arrivals=s.late_arrivals, total_hours_worked=float(s.total_hours_worked or 0),
    )


# ── HR Admin: view any employee's attendance ───────────────────────────────────

@router.get("/admin/{employee_id}", response_model=list[AttendanceDayOut])
def admin_view_attendance(
    employee_id: int,
    year:  int = date.today().year,
    month: int = date.today().month,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    next_y = year + 1 if month == 12 else year
    next_m = 1        if month == 12 else month + 1
    return (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.employee_id    == employee_id,
            AttendanceRecord.attendance_date >= date(year, month, 1),
            AttendanceRecord.attendance_date <  date(next_y, next_m, 1),
        )
        .order_by(AttendanceRecord.attendance_date.asc())
        .all()
    )


# ── HR Admin: direct attendance edit with audit log ───────────────────────────

class AttendanceEditRequest(PydanticBase):
    employee_id:     int
    attendance_date: date
    new_status:      str
    check_in_time:   Optional[datetime] = None
    check_out_time:  Optional[datetime] = None
    reason:          str


class AttendanceEditOut(PydanticBase):
    attendance_id:   int
    employee_id:     int
    attendance_date: date
    status:          str
    source:          str
    remarks:         Optional[str] = None

    class Config:
        from_attributes = True


@router.post("/admin/edit", response_model=AttendanceEditOut)
def admin_edit_attendance(
    body: AttendanceEditRequest,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    """
    HR Admin can directly correct any employee's attendance for any date.
    The edit is logged in attendance_edit_log with old/new values and the HR editor's ID.
    """
    allowed_statuses = {"present", "absent", "wfh", "on_leave", "half_day", "holiday"}
    if body.new_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Allowed: {', '.join(allowed_statuses)}",
        )

    # Check employee exists in org
    emp = db.query(Employee).filter(Employee.employee_id == body.employee_id).first()
    if emp is None or emp.org_id != current.org_id:
        raise HTTPException(status_code=404, detail="Employee not found in your organisation")

    existing = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.employee_id     == body.employee_id,
            AttendanceRecord.attendance_date == body.attendance_date,
        )
        .first()
    )

    old_status = existing.status if existing else None

    if existing:
        # Log the edit
        try:
            from app.models import AttendanceEditLog
            db.add(AttendanceEditLog(
                attendance_id  = existing.attendance_id,
                edited_by      = current.employee_id,
                old_status     = old_status,
                new_status     = body.new_status,
                old_check_in   = existing.check_in_time,
                new_check_in   = body.check_in_time,
                old_check_out  = existing.check_out_time,
                new_check_out  = body.check_out_time,
                reason         = body.reason,
                edited_at      = datetime.utcnow(),
            ))
        except Exception as e:
            print(f"[audit] attendance edit log failed: {e}")

        existing.status         = body.new_status
        existing.source         = "manual"
        existing.remarks        = f"HR edit by {current.full_name}: {body.reason}"
        existing.is_regularised = True
        if body.check_in_time:
            existing.check_in_time = body.check_in_time
        if body.check_out_time:
            existing.check_out_time = body.check_out_time
        db.commit(); db.refresh(existing)
        return existing
    else:
        record = AttendanceRecord(
            employee_id     = body.employee_id,
            attendance_date = body.attendance_date,
            status          = body.new_status,
            check_in_time   = body.check_in_time,
            check_out_time  = body.check_out_time,
            source          = "manual",
            remarks         = f"HR edit by {current.full_name}: {body.reason}",
            is_regularised  = True,
        )
        db.add(record); db.commit(); db.refresh(record)
        return record


# ── Regularisation ─────────────────────────────────────────────────────────────

def _serialize_reg(db: Session, r: AttendanceRegularisation) -> RegularisationOut:
    emp = db.query(Employee).filter(Employee.employee_id == r.employee_id).first()
    out = RegularisationOut.model_validate(r)
    out.employee_name = emp.full_name if emp else None
    return out


@router.post("/regularisation", response_model=RegularisationOut, status_code=201)
def request_regularisation(
    body: RegularisationCreate,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    r = AttendanceRegularisation(
        employee_id         = current.employee_id,
        attendance_date     = body.attendance_date,
        requested_check_in  = body.requested_check_in,
        requested_check_out = body.requested_check_out,
        requested_status    = body.requested_status,
        reason              = body.reason,
        status              = "pending",
        requested_at        = datetime.utcnow(),
    )
    db.add(r); db.commit(); db.refresh(r)
    return _serialize_reg(db, r)


@router.get("/regularisation", response_model=list[RegularisationOut])
def my_regularisations(
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    rows = (
        db.query(AttendanceRegularisation)
        .filter(AttendanceRegularisation.employee_id == current.employee_id)
        .order_by(AttendanceRegularisation.requested_at.desc())
        .all()
    )
    return [_serialize_reg(db, r) for r in rows]


@router.get("/regularisation/queue", response_model=list[RegularisationOut])
def regularisation_queue(
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin", "manager")),
):
    query = db.query(AttendanceRegularisation).filter(AttendanceRegularisation.status == "pending")
    if current.role == "manager":
        report_ids = [
            e.employee_id for e in
            db.query(Employee.employee_id)
            .filter(Employee.manager_id == current.employee_id).all()
        ]
        query = query.filter(AttendanceRegularisation.employee_id.in_(report_ids or [-1]))
    return [
        _serialize_reg(db, r)
        for r in query.order_by(AttendanceRegularisation.requested_at.asc()).all()
    ]


@router.post("/regularisation/{regularisation_id}/decision", response_model=RegularisationOut)
def decide_regularisation(
    regularisation_id: int,
    body: RegularisationDecision,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin", "manager")),
):
    r = db.query(AttendanceRegularisation).filter(
        AttendanceRegularisation.regularisation_id == regularisation_id
    ).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Regularisation request not found")
    if r.status != "pending":
        raise HTTPException(status_code=400, detail=f"Already {r.status}")

    r.status            = body.decision
    r.reviewed_by       = current.employee_id
    r.reviewed_at       = datetime.utcnow()
    r.reviewer_comments = body.reviewer_comments

    if body.decision == "approved":
        record = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.employee_id     == r.employee_id,
                AttendanceRecord.attendance_date == r.attendance_date,
            )
            .first()
        )
        if record is None:
            record = AttendanceRecord(
                employee_id     = r.employee_id,
                attendance_date = r.attendance_date,
                status          = r.requested_status or "present",
                source          = "regularised",
            )
            db.add(record)
        if r.requested_check_in:   record.check_in_time  = r.requested_check_in
        if r.requested_check_out:  record.check_out_time = r.requested_check_out
        if r.requested_status:     record.status         = r.requested_status
        record.is_regularised = True
        record.source         = "regularised"

    db.commit(); db.refresh(r)
    return _serialize_reg(db, r)


# ── Holiday management (HR Admin) ─────────────────────────────────────────────

class HolidayCreate(PydanticBase):
    holiday_date: date
    holiday_name: str
    holiday_type: str = "public"


class HolidayOut(PydanticBase):
    holiday_id:   int
    holiday_date: date
    holiday_name: str
    holiday_type: str
    class Config:
        from_attributes = True


@router.get("/holidays", response_model=list[HolidayOut])
def list_holidays(
    year: int = date.today().year,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    return (
        db.query(HolidayCalendar)
        .filter(
            HolidayCalendar.org_id       == current.org_id,
            HolidayCalendar.holiday_date >= date(year, 1, 1),
            HolidayCalendar.holiday_date <= date(year, 12, 31),
        )
        .order_by(HolidayCalendar.holiday_date.asc())
        .all()
    )


@router.post("/holidays", response_model=HolidayOut, status_code=201)
def add_holiday(
    body: HolidayCreate,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    existing = db.query(HolidayCalendar).filter(
        HolidayCalendar.org_id       == current.org_id,
        HolidayCalendar.holiday_date == body.holiday_date,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="A holiday already exists for this date")
    h = HolidayCalendar(
        org_id       = current.org_id,
        holiday_date = body.holiday_date,
        holiday_name = body.holiday_name,
        holiday_type = body.holiday_type,
    )
    db.add(h); db.commit(); db.refresh(h)
    return h


@router.delete("/holidays/{holiday_id}")
def delete_holiday(
    holiday_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    h = db.query(HolidayCalendar).filter(
        HolidayCalendar.holiday_id == holiday_id,
        HolidayCalendar.org_id     == current.org_id,
    ).first()
    if h is None:
        raise HTTPException(status_code=404, detail="Holiday not found")
    db.delete(h); db.commit()
    return {"message": "Holiday deleted"}
