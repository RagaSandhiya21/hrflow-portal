from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_employee, require_role
from app.models import Employee, HRRequestCategory, HRRequest, HRRequestComment
from app.schemas import (
    HRCategoryOut, HRRequestCreate, HRRequestOut, HRRequestStatusUpdate,
    HRCommentCreate, HRCommentOut,
)
from app.email_service import notify_hr_request_raised, notify_hr_request_resolved
from app.notification_service import notify

router = APIRouter(prefix="/hr-requests", tags=["hr-requests"])


def _serialize(db: Session, r: HRRequest) -> HRRequestOut:
    emp = db.query(Employee).filter(Employee.employee_id == r.employee_id).first()
    cat = db.query(HRRequestCategory).filter(HRRequestCategory.category_id == r.category_id).first()
    out = HRRequestOut.model_validate(r)
    out.employee_name  = emp.full_name if emp else None
    out.category_name  = cat.category_name if cat else None
    return out


@router.get("/categories", response_model=list[HRCategoryOut])
def list_categories(
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    return db.query(HRRequestCategory).filter(HRRequestCategory.is_active.is_(True)).all()


@router.get("", response_model=list[HRRequestOut])
def my_requests(
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    rows = (
        db.query(HRRequest)
        .filter(HRRequest.employee_id == current.employee_id)
        .order_by(HRRequest.raised_at.desc())
        .all()
    )
    return [_serialize(db, r) for r in rows]


@router.get("/queue", response_model=list[HRRequestOut])
def hr_queue(
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    rows = (
        db.query(HRRequest)
        .filter(HRRequest.status.notin_(["resolved", "closed", "cancelled"]))
        .order_by(HRRequest.raised_at.asc())
        .all()
    )
    return [_serialize(db, r) for r in rows]


@router.post("", response_model=HRRequestOut, status_code=201)
def raise_request(
    body: HRRequestCreate,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    category = db.query(HRRequestCategory).filter(
        HRRequestCategory.category_id == body.category_id
    ).first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    now = datetime.utcnow()
    r = HRRequest(
        employee_id = current.employee_id,
        category_id = body.category_id,
        subject     = body.subject,
        description = body.description,
        priority    = body.priority,
        status      = "open",
        raised_at   = now,
        updated_at  = now,
    )
    db.add(r); db.commit(); db.refresh(r)

    # Notify all HR Admins in the org
    try:
        hr_admins = db.query(Employee).filter(
            Employee.org_id == current.org_id,
            Employee.role   == "hr_admin",
            Employee.is_active.is_(True),
        ).all()
        for hr in hr_admins:
            email = hr.work_email or hr.email
            if email:
                notify_hr_request_raised(email, current.full_name, body.subject, category.category_name)
            notify(db, hr.employee_id, "hr_request_raised",
                   f"New HR Request — {body.subject}",
                   f"{current.full_name} raised a {category.category_name} request.",
                   deep_link=f"/hr-requests/{r.hr_request_id}")
        db.commit()
    except Exception as e:
        print(f"[email] hr_request notify failed: {e}")

    return _serialize(db, r)


@router.patch("/{hr_request_id}/status", response_model=HRRequestOut)
def update_status(
    hr_request_id: int,
    body: HRRequestStatusUpdate,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    r = db.query(HRRequest).filter(HRRequest.hr_request_id == hr_request_id).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Request not found")
    r.status     = body.status
    r.updated_at = datetime.utcnow()
    if body.status in ("resolved", "closed"):
        r.resolved_at      = datetime.utcnow()
        r.resolution_notes = body.resolution_notes
    if r.assigned_to is None:
        r.assigned_to = current.employee_id
    db.commit(); db.refresh(r)

    # Notify employee
    try:
        emp   = db.query(Employee).filter(Employee.employee_id == r.employee_id).first()
        email = emp.work_email or emp.email if emp else None
        if email and body.status in ("resolved", "closed", "in_progress", "pending_info"):
            notify_hr_request_resolved(
                emp_email = email,
                emp_name  = emp.full_name,
                subject   = r.subject,
                status    = body.status,
                notes     = body.resolution_notes or "",
            )
        if emp:
            notify(db, emp.employee_id, "hr_request_status",
                   f"HR Request Update — {r.subject}",
                   f"Your request status is now {body.status.replace('_', ' ').title()}.",
                   deep_link=f"/hr-requests/{r.hr_request_id}")
            db.commit()
    except Exception as e:
        print(f"[email] hr status notify failed: {e}")

    return _serialize(db, r)


@router.get("/{hr_request_id}/comments", response_model=list[HRCommentOut])
def list_comments(
    hr_request_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    r = db.query(HRRequest).filter(HRRequest.hr_request_id == hr_request_id).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if r.employee_id != current.employee_id and current.role not in ("hr_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Not your request")

    query = db.query(HRRequestComment).filter(HRRequestComment.hr_request_id == hr_request_id)
    if current.role not in ("hr_admin", "super_admin"):
        query = query.filter(HRRequestComment.is_internal.is_(False))
    rows  = query.order_by(HRRequestComment.created_at.asc()).all()

    out = []
    for c in rows:
        commenter = db.query(Employee).filter(Employee.employee_id == c.commenter_id).first()
        item = HRCommentOut.model_validate(c)
        item.commenter_name = commenter.full_name if commenter else None
        out.append(item)
    return out


@router.post("/{hr_request_id}/comments", response_model=HRCommentOut, status_code=201)
def add_comment(
    hr_request_id: int,
    body: HRCommentCreate,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    r = db.query(HRRequest).filter(HRRequest.hr_request_id == hr_request_id).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if r.employee_id != current.employee_id and current.role not in ("hr_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Not your request")

    is_internal = body.is_internal and current.role in ("hr_admin", "super_admin")
    c = HRRequestComment(
        hr_request_id = hr_request_id,
        commenter_id  = current.employee_id,
        comment_text  = body.comment_text,
        is_internal   = is_internal,
        created_at    = datetime.utcnow(),
    )
    db.add(c)
    r.updated_at = datetime.utcnow()
    db.commit(); db.refresh(c)

    item = HRCommentOut.model_validate(c)
    item.commenter_name = current.full_name
    return item
