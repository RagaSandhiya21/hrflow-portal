from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Employee
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_employee(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Employee:
    """
    Resolves the bearer token to an Employee row (which may be a real
    individual, or a shared HR Admin / IT Admin functional account -
    see employees.is_shared_admin). 401 if the token is missing/invalid or
    the account is inactive.
    """
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(creds.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    employee = db.query(Employee).filter(Employee.employee_id == int(payload["sub"])).first()
    if employee is None or not employee.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # Stash who is *actually* signed in, off the JWT, for endpoints/audit
    # logs that need to attribute an action to a real person even when
    # `employee` is a shared admin account (see admin_account_access_log).
    employee._acting_display_name = payload.get("acting_display_name")
    employee._acting_email = payload.get("email")

    return employee


def require_role(*allowed_roles: str):
    """
    Usage: Depends(require_role("hr_admin", "super_admin"))
    super_admin is implicitly allowed everywhere a role check is used,
    matching the schema's role hierarchy (employees.role CHECK constraint).
    """
    def checker(employee: Employee = Depends(get_current_employee)) -> Employee:
        if employee.role == "super_admin" or employee.role in allowed_roles:
            return employee
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{employee.role}' is not permitted to access this endpoint",
        )
    return checker


def require_personal_employee(employee: Employee = Depends(get_current_employee)) -> Employee:
    """
    Guard for endpoints that deal with an individual's OWN HR data - leave
    balances/applications, payslips, personal attendance, profile
    self-service. Shared HR Admin / IT Admin accounts (is_shared_admin=True)
    have no personal employment record and must be blocked here rather than
    being allowed to "apply for leave" or "view a payslip" as if they were a
    person on payroll.
    """
    if employee.is_shared_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This is a shared admin account (HR Admin / IT Admin), not an individual "
                "employee - it has no personal HR records such as leave, payslips, or "
                "attendance. Sign in with your own individual account for personal "
                "self-service, and use this shared account only for its admin queues."
            ),
        )
    return employee
