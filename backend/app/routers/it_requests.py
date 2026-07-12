from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_employee, require_role
from app.models import Employee, ITRequest, ITRequestStatusHistory
from app.schemas import ITRequestCreate, ITRequestOut, ITRequestStatusUpdate
from app.email_service import notify_it_status_change
from app.notification_service import notify

router = APIRouter(prefix="/it-requests", tags=["it-requests"])


def _serialize(db: Session, r: ITRequest) -> ITRequestOut:
    emp = db.query(Employee).filter(Employee.employee_id == r.employee_id).first()
    out = ITRequestOut.model_validate(r)
    out.employee_name = emp.full_name if emp else None
    return out


@router.get("", response_model=list[ITRequestOut])
def my_requests(
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    rows = (
        db.query(ITRequest)
        .filter(ITRequest.employee_id == current.employee_id)
        .order_by(ITRequest.raised_at.desc())
        .all()
    )
    return [_serialize(db, r) for r in rows]


@router.get("/queue", response_model=list[ITRequestOut])
def it_queue(
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("it_admin", "hr_admin")),
):
    rows = (
        db.query(ITRequest)
        .filter(ITRequest.status.notin_(["resolved", "closed"]))
        .order_by(ITRequest.raised_at.asc())
        .all()
    )
    return [_serialize(db, r) for r in rows]


@router.post("", response_model=ITRequestOut, status_code=201)
def raise_request(
    body: ITRequestCreate,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    now = datetime.utcnow()
    r = ITRequest(
        employee_id  = current.employee_id,
        request_type = body.request_type,
        subject      = body.subject,
        description  = body.description,
        priority     = body.priority,
        status       = "open",
        raised_at    = now,
        updated_at   = now,
    )
    db.add(r); db.commit(); db.refresh(r)

    db.add(ITRequestStatusHistory(
        it_request_id = r.it_request_id,
        old_status    = None,
        new_status    = "open",
        changed_by    = current.employee_id,
        changed_at    = now,
    ))
    db.commit()
    return _serialize(db, r)


@router.patch("/{it_request_id}/status", response_model=ITRequestOut)
def update_status(
    it_request_id: int,
    body: ITRequestStatusUpdate,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("it_admin")),
):
    r = db.query(ITRequest).filter(ITRequest.it_request_id == it_request_id).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Request not found")

    old_status = r.status
    r.status   = body.status
    r.updated_at = datetime.utcnow()
    if body.status in ("resolved", "closed"):
        r.resolved_at      = datetime.utcnow()
        r.resolution_notes = body.notes
    if r.assigned_to is None:
        r.assigned_to = current.employee_id

    db.add(ITRequestStatusHistory(
        it_request_id = it_request_id,
        old_status    = old_status,
        new_status    = body.status,
        changed_by    = current.employee_id,
        notes         = body.notes,
        changed_at    = datetime.utcnow(),
    ))
    db.commit(); db.refresh(r)

    # Email employee on every status change
    try:
        emp   = db.query(Employee).filter(Employee.employee_id == r.employee_id).first()
        email = emp.work_email or emp.email if emp else None
        if email:
            notify_it_status_change(
                emp_email  = email,
                emp_name   = emp.full_name,
                subject    = r.subject,
                old_status = old_status,
                new_status = body.status,
                notes      = body.notes or "",
            )
        if emp:
            notify(db, emp.employee_id, "it_request_status",
                   f"IT Request Update — {r.subject}",
                   f"Status changed to {body.status.replace('_', ' ').title()}.",
                   deep_link=f"/it-requests/{r.it_request_id}")
            db.commit()
    except Exception as e:
        print(f"[email] it status notify failed: {e}")

    return _serialize(db, r)
