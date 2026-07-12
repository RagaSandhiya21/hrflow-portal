from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_employee
from datetime import datetime

from app.models import AdminAccountAccessLog, Employee
from app.schemas import EmployeeOut, LoginRequest, SSOLoginRequest, TokenResponse
from app.security import create_access_token, extract_identity, validate_entra_id_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _resolve_identity_to_employee(db: Session, identity: dict) -> tuple[Employee, str | None, str | None]:
    """
    Given a normalized identity (oid/email/display_name/groups off an Entra
    ID token - or an equivalent stand-in from the dev mock login), resolves
    which `employees` row should be signed into.

    Shared-account rule: if the identity is a member of the HR Admin or IT
    Admin Entra ID group, they are signed into that ORG'S shared functional
    account (is_shared_admin=True) - never into a personal record - and the
    real person's identity is written to admin_account_access_log for
    accountability. Otherwise we fall back to matching their own personal
    employees row by email/OID, exactly as the proposal's "if user exists in
    DB -> grant role-based access; else -> error" rule describes.

    Returns (employee_row, acting_display_name, acting_email). The acting_*
    values are only meaningful for shared accounts; for personal accounts
    they mirror the employee's own name/email.
    """
    groups = set(identity.get("groups") or [])

    shared_role = None
    if settings.ENTRA_HR_ADMIN_GROUP_ID and settings.ENTRA_HR_ADMIN_GROUP_ID in groups:
        shared_role = "hr_admin"
    elif settings.ENTRA_IT_ADMIN_GROUP_ID and settings.ENTRA_IT_ADMIN_GROUP_ID in groups:
        shared_role = "it_admin"

    if shared_role:
        account = (
            db.query(Employee)
            .filter(Employee.role == shared_role, Employee.is_shared_admin.is_(True), Employee.is_active.is_(True))
            .first()
        )
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"No shared '{shared_role}' account is provisioned for this organisation yet.",
            )
        db.add(AdminAccountAccessLog(
            admin_employee_id=account.employee_id,
            acting_entra_oid=identity["oid"] or "unknown",
            acting_email=identity["email"] or "unknown",
            acting_display_name=identity.get("display_name"),
            logged_in_at=datetime.utcnow(),
        ))
        db.commit()
        return account, identity.get("display_name"), identity.get("email")

    # Not a member of a shared-admin group -> resolve their own personal record.
    employee = (
        db.query(Employee)
        .filter(Employee.email == identity["email"], Employee.is_active.is_(True))
        .first()
    )
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active employee found for this account. Only users provisioned in the "
                   "employees table (or members of the HR/IT Admin Entra ID groups) are granted access.",
        )
    if employee.is_shared_admin:
        # Safety net: a shared account should only ever be reached via its group,
        # never by someone directly matching its (non-personal) email.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is a shared HR/IT Admin identity - sign in with your own "
                   "individual account, or via the HR/IT Admin Entra ID group, to use it.",
        )
    return employee, employee.full_name, employee.email


@router.post("/sso/entra", response_model=TokenResponse)
def sso_login(body: SSOLoginRequest, db: Session = Depends(get_db)):
    """
    Real Microsoft Entra ID SSO. The frontend (MSAL.js) redirects the user to
    Microsoft, gets back an id_token, and posts it here. We validate it
    against Microsoft's JWKS for our tenant (see security.py) and resolve it
    to either a personal employee record or a shared HR/IT Admin account.
    """
    try:
        claims = validate_entra_id_token(body.id_token)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    identity = extract_identity(claims)
    employee, acting_name, acting_email = _resolve_identity_to_employee(db, identity)

    token = create_access_token(
        employee.employee_id, employee.role, employee.email,
        acting_display_name=acting_name, is_shared_admin=employee.is_shared_admin,
    )
    return TokenResponse(
        access_token=token,
        employee=EmployeeOut.model_validate(employee),
        acting_display_name=acting_name,
        acting_email=acting_email,
    )


@router.post("/login", response_model=TokenResponse)
def dev_mock_login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Dev-only stand-in for the Entra ID SSO redirect, active only when
    USE_MOCK_SSO=true (the default, so this zip runs without an Azure
    tenant). It mirrors the same resolution rule as real SSO
    (_resolve_identity_to_employee) - including that logging in with the
    seeded HR Admin / IT Admin email is treated as "signing in as a member
    of that group" for local testing, and is logged to
    admin_account_access_log exactly like a real shared-account login would
    be. Disable by setting USE_MOCK_SSO=false once real Entra ID is wired up.
    """
    if not settings.USE_MOCK_SSO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mock SSO is disabled (USE_MOCK_SSO=false). Sign in via POST /auth/sso/entra.",
        )

    employee = db.query(Employee).filter(Employee.email == body.email).first()
    if employee is None or not employee.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active employee/admin account found for this email.",
        )

    acting_name = employee.full_name
    acting_email = employee.email
    if employee.is_shared_admin:
        # Local dev has no real Entra token to pull a distinct person's
        # identity off of, so we log the mock session as an anonymous
        # "dev tester" acting under the shared account, rather than
        # attributing it to a fabricated person.
        db.add(AdminAccountAccessLog(
            admin_employee_id=employee.employee_id,
            acting_entra_oid="mock-sso-dev",
            acting_email=body.email,
            acting_display_name="Dev/local tester (mock SSO)",
            ip_address=request.client.host if request.client else None,
            logged_in_at=datetime.utcnow(),
        ))
        db.commit()
        acting_name = "Dev/local tester (mock SSO)"

    token = create_access_token(
        employee.employee_id, employee.role, employee.email,
        acting_display_name=acting_name, is_shared_admin=employee.is_shared_admin,
    )
    return TokenResponse(
        access_token=token,
        employee=EmployeeOut.model_validate(employee),
        acting_display_name=acting_name,
        acting_email=acting_email,
    )


@router.get("/me", response_model=EmployeeOut)
def get_me(current: Employee = Depends(get_current_employee)):
    return EmployeeOut.model_validate(current)


@router.get("/admin-account-log/{employee_id}")
def admin_account_log(
    employee_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    """
    Accountability trail for a shared HR/IT Admin account: who (real person)
    has signed into it and when. Only HR Admin / IT Admin / super_admin may
    view this, and only for a shared account (not for a personal record).
    """
    if current.role not in ("hr_admin", "it_admin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")
    target = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if target is None or not target.is_shared_admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not a shared admin account")
    rows = (
        db.query(AdminAccountAccessLog)
        .filter(AdminAccountAccessLog.admin_employee_id == employee_id)
        .order_by(AdminAccountAccessLog.logged_in_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "acting_email": r.acting_email,
            "acting_display_name": r.acting_display_name,
            "logged_in_at": r.logged_in_at,
            "ip_address": r.ip_address,
        }
        for r in rows
    ]
