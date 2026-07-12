from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_employee, require_personal_employee, require_role
from app.models import (
    Employee, EmployeeAddress, EmergencyContact, EmployeeIdentityInfo,
    ProfileChangeRequest, Department, Designation, Team,
)
from app.schemas import (
    ProfileOut, EmployeeOut, AddressOut, AddressUpdate, EmergencyContactOut,
    EmergencyContactCreate, ContactUpdate, ChangeRequestCreate, ChangeRequestOut,
    ChangeRequestDecision, HREmployeeEdit,
)
from app.email_service import notify_change_request_raised, notify_change_request_decision
from app.notification_service import notify

router = APIRouter(prefix="/profile", tags=["profile"])

HR_APPROVAL_FIELDS = {
    "bank_account_number": (EmployeeIdentityInfo, "bank_account_number", str),
    "bank_name":           (EmployeeIdentityInfo, "bank_name",           str),
    "bank_ifsc":           (EmployeeIdentityInfo, "bank_ifsc",           str),
    "bank_branch":         (EmployeeIdentityInfo, "bank_branch",         str),
    "pan_number":          (EmployeeIdentityInfo, "pan_number",          str),
    "aadhaar_number":      (EmployeeIdentityInfo, "aadhaar_number",      str),
    "designation_id":      (Employee,             "designation_id",      int),
    "department_id":       (Employee,             "department_id",       int),
}


def _mask(value: str | None, keep: int = 4) -> str | None:
    if not value:
        return value
    return "*" * max(0, len(value) - keep) + value[-keep:] if len(value) > keep else "*" * len(value)


def _enrich_employee_out(db: Session, employee: Employee) -> EmployeeOut:
    """Resolves manager/department/designation IDs into display names —
    used by both the self-service profile view and HR Admin's employee view."""
    out = EmployeeOut.model_validate(employee)
    if employee.manager_id:
        manager = db.query(Employee).filter(Employee.employee_id == employee.manager_id).first()
        out.manager_name = manager.full_name if manager else None
    if employee.department_id:
        dept = db.query(Department).filter(Department.department_id == employee.department_id).first()
        out.department_name = dept.department_name if dept else None
    if employee.team_id:
        team = db.query(Team).filter(Team.team_id == employee.team_id).first()
        out.team_name = team.team_name if team else None
    if employee.designation_id:
        desig = db.query(Designation).filter(Designation.designation_id == employee.designation_id).first()
        out.designation_title = desig.title if desig else None
    return out


@router.get("/me", response_model=ProfileOut)
def get_my_profile(
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    addresses = db.query(EmployeeAddress).filter(EmployeeAddress.employee_id == current.employee_id).all()
    contacts  = db.query(EmergencyContact).filter(EmergencyContact.employee_id == current.employee_id).all()
    identity  = db.query(EmployeeIdentityInfo).filter(EmployeeIdentityInfo.employee_id == current.employee_id).first()
    masked = {
        "pan_number":          _mask(identity.pan_number)          if identity else None,
        "aadhaar_number":      _mask(identity.aadhaar_number)      if identity else None,
        "bank_account_number": _mask(identity.bank_account_number) if identity else None,
        "bank_name":           identity.bank_name                  if identity else None,
        "bank_ifsc":           identity.bank_ifsc                  if identity else None,
    }
    employee_out = _enrich_employee_out(db, current)
    return ProfileOut(
        employee           = employee_out,
        addresses          = [AddressOut.model_validate(a) for a in addresses],
        emergency_contacts = [EmergencyContactOut.model_validate(c) for c in contacts],
        identity_masked    = masked,
    )


@router.put("/me/contact", response_model=EmployeeOut)
def update_contact(
    body: ContactUpdate,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    if body.phone is not None:
        current.phone = body.phone
    if body.profile_photo_url is not None:
        current.profile_photo_url = body.profile_photo_url
    current.updated_at = datetime.utcnow()
    db.commit(); db.refresh(current)
    return current


@router.put("/me/address", response_model=AddressOut)
def upsert_address(
    body: AddressUpdate,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    addr = (
        db.query(EmployeeAddress)
        .filter(EmployeeAddress.employee_id == current.employee_id,
                EmployeeAddress.address_type == body.address_type)
        .first()
    )
    if addr is None:
        addr = EmployeeAddress(employee_id=current.employee_id, address_type=body.address_type)
        db.add(addr)
    addr.address_line1 = body.address_line1
    addr.address_line2 = body.address_line2
    addr.city          = body.city
    addr.state         = body.state
    addr.country       = body.country
    addr.pincode       = body.pincode
    addr.updated_at    = datetime.utcnow()
    db.commit(); db.refresh(addr)
    return addr


@router.post("/me/emergency-contacts", response_model=EmergencyContactOut, status_code=201)
def add_emergency_contact(
    body: EmergencyContactCreate,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    contact = EmergencyContact(
        employee_id    = current.employee_id,
        contact_name   = body.contact_name,
        relationship_  = body.relationship,
        phone          = body.phone,
        alternate_phone= body.alternate_phone,
        is_primary     = body.is_primary,
        updated_at     = datetime.utcnow(),
    )
    db.add(contact); db.commit(); db.refresh(contact)
    return contact


@router.put("/me/emergency-contacts/{contact_id}", response_model=EmergencyContactOut)
def update_emergency_contact(
    contact_id: int,
    body: EmergencyContactCreate,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    contact = db.query(EmergencyContact).filter(
        EmergencyContact.contact_id == contact_id,
        EmergencyContact.employee_id == current.employee_id,
    ).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Emergency contact not found")
    contact.contact_name    = body.contact_name
    contact.relationship_   = body.relationship
    contact.phone           = body.phone
    contact.alternate_phone = body.alternate_phone
    contact.is_primary      = body.is_primary
    contact.updated_at      = datetime.utcnow()
    db.commit(); db.refresh(contact)
    return contact


@router.delete("/me/emergency-contacts/{contact_id}")
def delete_emergency_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    contact = db.query(EmergencyContact).filter(
        EmergencyContact.contact_id == contact_id,
        EmergencyContact.employee_id == current.employee_id,
    ).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Emergency contact not found")
    db.delete(contact); db.commit()
    return {"message": "Emergency contact removed"}


# ── HR-approval change requests ───────────────────────────────────────────────

def _serialize_cr(db: Session, cr: ProfileChangeRequest) -> ChangeRequestOut:
    emp = db.query(Employee).filter(Employee.employee_id == cr.employee_id).first()
    out = ChangeRequestOut.model_validate(cr)
    out.employee_name = emp.full_name if emp else None
    return out


@router.post("/change-requests", response_model=ChangeRequestOut, status_code=201)
def submit_change_request(
    body: ChangeRequestCreate,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    if body.field_name not in HR_APPROVAL_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"'{body.field_name}' is not a recognised HR-approval field. "
                   f"Valid fields: {', '.join(HR_APPROVAL_FIELDS)}",
        )

    target_model, column, _caster = HR_APPROVAL_FIELDS[body.field_name]
    old_value = None
    if target_model is Employee:
        old_value = str(getattr(current, column, ""))
    else:
        identity = (
            db.query(EmployeeIdentityInfo)
            .filter(EmployeeIdentityInfo.employee_id == current.employee_id)
            .first()
        )
        old_value = str(getattr(identity, column, "")) if identity else None

    cr = ProfileChangeRequest(
        employee_id  = current.employee_id,
        field_group  = body.field_group,
        field_name   = body.field_name,
        old_value    = old_value,
        new_value    = body.new_value,
        reason       = body.reason,
        status       = "pending",
        requested_at = datetime.utcnow(),
    )
    db.add(cr); db.commit(); db.refresh(cr)

    # Notify all HR Admins
    try:
        hr_admins = db.query(Employee).filter(
            Employee.org_id    == current.org_id,
            Employee.role      == "hr_admin",
            Employee.is_active.is_(True),
        ).all()
        for hr in hr_admins:
            email = hr.work_email or hr.email
            if email:
                notify_change_request_raised(email, current.full_name, body.field_name)
            notify(db, hr.employee_id, "profile_change_requested",
                   f"Profile Change Request — {current.full_name}",
                   f"{current.full_name} requested a change to {body.field_name.replace('_', ' ')}.",
                   deep_link=f"/profile/change-requests/{cr.change_request_id}")
        db.commit()
    except Exception as e:
        print(f"[email] change request notify failed: {e}")

    return _serialize_cr(db, cr)


@router.get("/change-requests", response_model=list[ChangeRequestOut])
def my_change_requests(
    db: Session = Depends(get_db),
    current: Employee = Depends(require_personal_employee),
):
    rows = (
        db.query(ProfileChangeRequest)
        .filter(ProfileChangeRequest.employee_id == current.employee_id)
        .order_by(ProfileChangeRequest.requested_at.desc())
        .all()
    )
    return [_serialize_cr(db, r) for r in rows]


@router.get("/change-requests/pending", response_model=list[ChangeRequestOut])
def pending_change_requests(
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    rows = (
        db.query(ProfileChangeRequest)
        .filter(ProfileChangeRequest.status == "pending")
        .order_by(ProfileChangeRequest.requested_at.asc())
        .all()
    )
    return [_serialize_cr(db, r) for r in rows]


@router.post("/change-requests/{change_request_id}/decision", response_model=ChangeRequestOut)
def decide_change_request(
    change_request_id: int,
    body: ChangeRequestDecision,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    cr = db.query(ProfileChangeRequest).filter(
        ProfileChangeRequest.change_request_id == change_request_id
    ).first()
    if cr is None:
        raise HTTPException(status_code=404, detail="Change request not found")
    if cr.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {cr.status}")

    if body.decision == "approved":
        target_model, column, caster = HR_APPROVAL_FIELDS[cr.field_name]
        try:
            new_value = caster(cr.new_value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Invalid value type for {cr.field_name}")

        if target_model is Employee:
            target = db.query(Employee).filter(Employee.employee_id == cr.employee_id).first()
        else:
            target = (
                db.query(EmployeeIdentityInfo)
                .filter(EmployeeIdentityInfo.employee_id == cr.employee_id)
                .first()
            )
            if target is None:
                target = EmployeeIdentityInfo(employee_id=cr.employee_id)
                db.add(target)
        setattr(target, column, new_value)
        if hasattr(target, "updated_at"):
            target.updated_at = datetime.utcnow()

    cr.status        = body.decision
    cr.reviewed_by   = current.employee_id
    cr.reviewed_at   = datetime.utcnow()
    cr.reviewer_notes= body.reviewer_notes
    db.commit(); db.refresh(cr)

    # Email employee
    try:
        emp   = db.query(Employee).filter(Employee.employee_id == cr.employee_id).first()
        email = emp.work_email or emp.email if emp else None
        if email:
            notify_change_request_decision(
                emp_email  = email,
                emp_name   = emp.full_name,
                field_name = cr.field_name,
                decision   = body.decision,
                notes      = body.reviewer_notes or "",
            )
        if emp:
            notify(db, emp.employee_id, "profile_change_decision",
                   f"Profile Change Request {body.decision.title()}",
                   f"Your request to change {cr.field_name.replace('_', ' ')} was {body.decision}.",
                   deep_link="/profile")
            db.commit()
    except Exception as e:
        print(f"[email] change request decision notify failed: {e}")

    return _serialize_cr(db, cr)


# ── HR Admin: direct view/edit of ANY employee's profile ────────────────────────
# Distinct from the self-service change-request flow below — HR Admin has
# direct authority to correct records rather than approving its own requests.
# "There will be multiple projects/employees, so HR allocates managers" and
# "HR Admin should be able to edit any employee's profile" — both handled here.

@router.get("/{employee_id}", response_model=ProfileOut)
def get_employee_profile(
    employee_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    target = db.query(Employee).filter(Employee.employee_id == employee_id,
                                        Employee.org_id == current.org_id).first()
    if target is None or target.is_shared_admin:
        raise HTTPException(status_code=404, detail="Employee not found")
    addresses = db.query(EmployeeAddress).filter(EmployeeAddress.employee_id == employee_id).all()
    contacts  = db.query(EmergencyContact).filter(EmergencyContact.employee_id == employee_id).all()
    identity  = db.query(EmployeeIdentityInfo).filter(EmployeeIdentityInfo.employee_id == employee_id).first()
    # HR Admin sees identity/bank fields unmasked — they're the ones with
    # authority to edit them (contrast with the employee's own masked view).
    unmasked = {
        "pan_number":          identity.pan_number          if identity else None,
        "aadhaar_number":      identity.aadhaar_number      if identity else None,
        "bank_account_number": identity.bank_account_number if identity else None,
        "bank_name":           identity.bank_name           if identity else None,
        "bank_ifsc":           identity.bank_ifsc           if identity else None,
    }
    employee_out = _enrich_employee_out(db, target)
    return ProfileOut(
        employee=employee_out,
        addresses=[AddressOut.model_validate(a) for a in addresses],
        emergency_contacts=[EmergencyContactOut.model_validate(c) for c in contacts],
        identity_masked=unmasked,
    )


@router.put("/{employee_id}/hr-edit", response_model=EmployeeOut)
def hr_edit_employee_profile(
    employee_id: int,
    body: HREmployeeEdit,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    target = db.query(Employee).filter(Employee.employee_id == employee_id,
                                        Employee.org_id == current.org_id).first()
    if target is None or target.is_shared_admin:
        raise HTTPException(status_code=404, detail="Employee not found")

    now = datetime.utcnow()

    def _audit(field_group: str, field_name: str, old_value, new_value):
        """Every HR-direct edit still gets an audit row — auto-approved (HR
        edited it directly) but fully attributed, timestamped, and traceable."""
        if str(old_value) == str(new_value):
            return
        db.add(ProfileChangeRequest(
            employee_id=employee_id, field_group=field_group, field_name=field_name,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else "",
            reason="Direct HR Admin edit", status="approved",
            requested_at=now, reviewed_by=current.employee_id, reviewed_at=now,
            reviewer_notes="Edited directly by HR Admin",
        ))

    if body.phone is not None:
        _audit("other", "phone", target.phone, body.phone)
        target.phone = body.phone

    if body.designation_id is not None:
        _audit("designation", "designation_id", target.designation_id, body.designation_id)
        target.designation_id = body.designation_id
    if body.department_id is not None:
        _audit("department", "department_id", target.department_id, body.department_id)
        target.department_id = body.department_id
    if body.team_id is not None:
        _audit("department", "team_id", target.team_id, body.team_id)
        target.team_id = body.team_id
    if body.manager_id is not None:
        _audit("other", "manager_id", target.manager_id, body.manager_id)
        target.manager_id = body.manager_id
    target.updated_at = now

    if any(v is not None for v in (body.address_line1, body.city, body.state, body.country, body.pincode)):
        addr = (
            db.query(EmployeeAddress)
            .filter(EmployeeAddress.employee_id == employee_id, EmployeeAddress.address_type == "current")
            .first()
        )
        if addr is None:
            if not body.address_line1 or not body.city or not body.state:
                raise HTTPException(
                    status_code=400,
                    detail="address_line1, city, and state are all required to create this employee's first address record.",
                )
            addr = EmployeeAddress(employee_id=employee_id, address_type="current",
                                    address_line1=body.address_line1, city=body.city, state=body.state,
                                    updated_at=now)
            db.add(addr); db.flush()
        _audit("other", "address", addr.address_line1, body.address_line1)
        addr.address_line1 = body.address_line1 or addr.address_line1
        addr.address_line2 = body.address_line2
        addr.city = body.city or addr.city
        addr.state = body.state or addr.state
        addr.country = body.country or addr.country
        addr.pincode = body.pincode or addr.pincode
        addr.updated_at = now

    bank_fields = {
        "bank_account_number": body.bank_account_number, "bank_name": body.bank_name,
        "bank_ifsc": body.bank_ifsc, "pan_number": body.pan_number, "aadhaar_number": body.aadhaar_number,
    }
    if any(v is not None for v in bank_fields.values()):
        identity = db.query(EmployeeIdentityInfo).filter(EmployeeIdentityInfo.employee_id == employee_id).first()
        if identity is None:
            identity = EmployeeIdentityInfo(employee_id=employee_id)
            db.add(identity); db.flush()
        for field, value in bank_fields.items():
            if value is not None:
                group = "identity" if field in ("pan_number", "aadhaar_number") else "bank"
                _audit(group, field, getattr(identity, field), value)
                setattr(identity, field, value)
        identity.updated_at = now
        identity.updated_by = current.employee_id

    db.commit(); db.refresh(target)
    return target
