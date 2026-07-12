import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_employee, require_role
from app.models import Employee, Payslip, MonthlyPayroll, Department, Designation
from app.schemas import PayslipOut, PayslipDetail

router = APIRouter(prefix="/payslips", tags=["payslips"])


def _safe(v, default=0.0):
    """Safely convert potentially-None DB value to float."""
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _get_payslip_detail(db, payslip_id, current):
    payslip = db.query(Payslip).filter(Payslip.payslip_id == payslip_id).first()
    if payslip is None:
        raise HTTPException(status_code=404, detail="Payslip not found")
    if payslip.employee_id != current.employee_id and current.role not in ("hr_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="You can only view your own payslips")
    if not payslip.is_published and current.role not in ("hr_admin", "super_admin"):
        raise HTTPException(status_code=404, detail="Payslip not yet published")
    payroll  = db.query(MonthlyPayroll).filter(MonthlyPayroll.payroll_id == payslip.payroll_id).first()
    employee = db.query(Employee).filter(Employee.employee_id == payslip.employee_id).first()
    return payslip, payroll, employee


def _build_detail(payslip, payroll, employee, db) -> PayslipDetail:
    designation = db.query(Designation).filter(Designation.designation_id == employee.designation_id).first()
    department  = db.query(Department).filter(Department.department_id   == employee.department_id).first()

    basic      = _safe(payroll.basic_salary)
    hra        = _safe(payroll.hra)
    transport  = _safe(payroll.transport_allowance)
    medical    = _safe(payroll.medical_allowance)
    special    = _safe(payroll.special_allowance)
    bonus      = _safe(payroll.performance_bonus)
    other_earn = _safe(payroll.other_earnings)
    gross      = _safe(payroll.gross_earnings) or (basic + hra + transport + medical + special + bonus + other_earn)

    pf         = _safe(payroll.pf_employee)
    esi        = _safe(payroll.esi_employee)
    prof_tax   = _safe(payroll.professional_tax)
    tds        = _safe(payroll.tds)
    loan       = _safe(payroll.loan_deduction)
    lop        = _safe(payroll.loss_of_pay)
    other_ded  = _safe(payroll.other_deductions)
    total_ded  = _safe(payroll.total_deductions) or (pf + esi + prof_tax + tds + loan + lop + other_ded)
    net        = _safe(payroll.net_salary)       or (gross - total_ded)

    return PayslipDetail(
        payslip_id          = payslip.payslip_id,
        payslip_month       = payslip.payslip_month,
        employee_name       = employee.full_name,
        employee_code       = employee.employee_code,
        designation         = designation.title            if designation else None,
        department          = department.department_name   if department  else None,
        basic_salary        = basic,
        hra                 = hra,
        transport_allowance = transport,
        medical_allowance   = medical,
        special_allowance   = special,
        performance_bonus   = bonus,
        other_earnings      = other_earn,
        gross_earnings      = gross,
        pf_employee         = pf,
        esi_employee        = esi,
        professional_tax    = prof_tax,
        tds                 = tds,
        loan_deduction      = loan,
        loss_of_pay         = lop,
        other_deductions    = other_ded,
        total_deductions    = total_ded,
        net_salary          = net,
        days_worked         = payroll.days_worked,
        payroll_status      = payroll.payroll_status,
    )


@router.get("", response_model=list[PayslipOut])
def list_payslips(
    employee_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    target_id = current.employee_id
    if employee_id is not None and employee_id != current.employee_id:
        if current.role not in ("hr_admin", "super_admin"):
            raise HTTPException(status_code=403, detail="Only HR Admin can view another employee's payslips")
        target_id = employee_id
    elif current.is_shared_admin:
        raise HTTPException(
            status_code=403,
            detail="The shared HR Admin account has no personal payslips — pass ?employee_id= to look up an employee's.",
        )

    query = db.query(Payslip).filter(Payslip.employee_id == target_id)
    if current.role not in ("hr_admin", "super_admin"):
        query = query.filter(Payslip.is_published.is_(True))
    return query.order_by(Payslip.payslip_month.desc()).all()


@router.get("/{payslip_id}", response_model=PayslipDetail)
def payslip_detail(
    payslip_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    payslip, payroll, employee = _get_payslip_detail(db, payslip_id, current)
    return _build_detail(payslip, payroll, employee, db)


@router.get("/{payslip_id}/pdf")
def payslip_pdf(
    payslip_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    """
    Generate payslip PDF on-demand using PyMuPDF, from a fixed-coordinate
    template (see app/payslip_pdf.py) — matching Module 3 of the proposal.
    Returns a downloadable PDF file with earnings, deductions, and net salary.
    """
    from app.payslip_pdf import build_payslip_pdf

    payslip, payroll, employee = _get_payslip_detail(db, payslip_id, current)
    d = _build_detail(payslip, payroll, employee, db)

    pdf_bytes = build_payslip_pdf(d)
    buf = io.BytesIO(pdf_bytes)

    # Update download stats
    payslip.last_downloaded_at = datetime.utcnow()
    payslip.download_count = (payslip.download_count or 0) + 1
    db.commit()

    month_tag = d.payslip_month.strftime("%Y_%m") if d.payslip_month else "unknown"
    filename  = f"payslip_{employee.employee_code}_{month_tag}.pdf"

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{payslip_id}/publish", response_model=PayslipOut)
def publish_payslip(
    payslip_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    payslip = db.query(Payslip).filter(Payslip.payslip_id == payslip_id).first()
    if payslip is None:
        raise HTTPException(status_code=404, detail="Payslip not found")
    payslip.is_published = True
    payslip.published_at = datetime.utcnow()
    db.commit(); db.refresh(payslip)
    return payslip
