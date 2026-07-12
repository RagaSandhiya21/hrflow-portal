"""
Org hierarchy management: Department -> Team -> Designation, and (read-only
here) Employee assignment into that hierarchy.

Per the proposal's Module 1: "Org hierarchy (department -> team -> employee)
managed exclusively by HR Admin" - every write endpoint below requires the
hr_admin role. This was previously missing entirely (departments/teams were
only ever read, never managed via the API).
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_employee, require_role
from app.models import Department, Designation, Employee, Location, Team
from app.schemas import (
    DepartmentIn, DepartmentOut, DesignationIn, DesignationOut,
    LocationOut, TeamIn, TeamOut,
)

router = APIRouter(prefix="/org", tags=["org-hierarchy"])


# ── Departments ───────────────────────────────────────────────────────────────

@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db), current: Employee = Depends(get_current_employee)):
    return (
        db.query(Department)
        .filter(Department.org_id == current.org_id, Department.is_active.is_(True))
        .order_by(Department.department_name)
        .all()
    )


@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(
    body: DepartmentIn,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    if db.query(Department).filter(Department.department_code == body.department_code).first():
        raise HTTPException(status_code=409, detail="A department with this code already exists")
    dept = Department(org_id=current.org_id, **body.model_dump())
    db.add(dept); db.commit(); db.refresh(dept)
    return dept


@router.put("/departments/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: int,
    body: DepartmentIn,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    dept = db.query(Department).filter(Department.department_id == department_id,
                                        Department.org_id == current.org_id).first()
    if dept is None:
        raise HTTPException(status_code=404, detail="Department not found")
    for k, v in body.model_dump().items():
        setattr(dept, k, v)
    db.commit(); db.refresh(dept)
    return dept


@router.delete("/departments/{department_id}")
def deactivate_department(
    department_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    dept = db.query(Department).filter(Department.department_id == department_id,
                                        Department.org_id == current.org_id).first()
    if dept is None:
        raise HTTPException(status_code=404, detail="Department not found")
    dept.is_active = False
    db.commit()
    return {"message": f"'{dept.department_name}' deactivated"}


# ── Teams ─────────────────────────────────────────────────────────────────────

@router.get("/teams", response_model=list[TeamOut])
def list_teams(
    department_id: int | None = None,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    q = db.query(Team).filter(Team.org_id == current.org_id, Team.is_active.is_(True))
    if department_id is not None:
        q = q.filter(Team.department_id == department_id)
    return q.order_by(Team.team_name).all()


@router.post("/teams", response_model=TeamOut, status_code=201)
def create_team(
    body: TeamIn,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    if not db.query(Department).filter(Department.department_id == body.department_id).first():
        raise HTTPException(status_code=400, detail="department_id does not exist")
    if db.query(Team).filter(Team.team_code == body.team_code).first():
        raise HTTPException(status_code=409, detail="A team with this code already exists")
    team = Team(org_id=current.org_id, **body.model_dump())
    db.add(team); db.commit(); db.refresh(team)
    return team


@router.put("/teams/{team_id}", response_model=TeamOut)
def update_team(
    team_id: int,
    body: TeamIn,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    team = db.query(Team).filter(Team.team_id == team_id, Team.org_id == current.org_id).first()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    for k, v in body.model_dump().items():
        setattr(team, k, v)
    db.commit(); db.refresh(team)
    return team


@router.delete("/teams/{team_id}")
def deactivate_team(
    team_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    team = db.query(Team).filter(Team.team_id == team_id, Team.org_id == current.org_id).first()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    team.is_active = False
    db.commit()
    return {"message": f"'{team.team_name}' deactivated"}


# ── Designations ───────────────────────────────────────────────────────────────

@router.get("/designations", response_model=list[DesignationOut])
def list_designations(db: Session = Depends(get_db), current: Employee = Depends(get_current_employee)):
    return (
        db.query(Designation)
        .filter(Designation.org_id == current.org_id, Designation.is_active.is_(True))
        .order_by(Designation.title)
        .all()
    )


@router.post("/designations", response_model=DesignationOut, status_code=201)
def create_designation(
    body: DesignationIn,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    designation = Designation(org_id=current.org_id, **body.model_dump())
    db.add(designation); db.commit(); db.refresh(designation)
    return designation


@router.put("/designations/{designation_id}", response_model=DesignationOut)
def update_designation(
    designation_id: int,
    body: DesignationIn,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    d = db.query(Designation).filter(Designation.designation_id == designation_id,
                                      Designation.org_id == current.org_id).first()
    if d is None:
        raise HTTPException(status_code=404, detail="Designation not found")
    for k, v in body.model_dump().items():
        setattr(d, k, v)
    db.commit(); db.refresh(d)
    return d


@router.delete("/designations/{designation_id}")
def deactivate_designation(
    designation_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    d = db.query(Designation).filter(Designation.designation_id == designation_id,
                                      Designation.org_id == current.org_id).first()
    if d is None:
        raise HTTPException(status_code=404, detail="Designation not found")
    d.is_active = False
    db.commit()
    return {"message": f"'{d.title}' deactivated"}


# ── Locations (read-only here; seeded at org setup time) ────────────────────────

@router.get("/locations", response_model=list[LocationOut])
def list_locations(db: Session = Depends(get_db), current: Employee = Depends(get_current_employee)):
    return (
        db.query(Location)
        .filter(Location.org_id == current.org_id, Location.is_active.is_(True))
        .order_by(Location.location_name)
        .all()
    )


# ── Employee directory search (for HR Admin tools like Attendance Admin) ───────

@router.get("/employees")
def search_employees(
    q: str = "",
    limit: int = 20,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    """
    Employee-directory search with the detail needed for HR Admin's
    Employee Management screen: current department/team/designation/manager,
    so HR can review and reassign them (multiple projects/teams, HR
    allocates the manager — see PUT /org/employees/{id}/assignment below).
    Excludes shared admin accounts — those aren't individuals to manage here.
    """
    query = (
        db.query(Employee)
        .filter(Employee.org_id == current.org_id, Employee.is_active.is_(True),
                Employee.is_shared_admin.is_(False))
    )
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            (Employee.full_name.ilike(like)) |
            (Employee.employee_code.ilike(like)) |
            (Employee.email.ilike(like))
        )
    results = query.order_by(Employee.full_name).limit(limit).all()

    dept_map = {d.department_id: d.department_name for d in db.query(Department).filter(Department.org_id == current.org_id)}
    team_map = {t.team_id: t.team_name for t in db.query(Team).filter(Team.org_id == current.org_id)}
    desig_map = {d.designation_id: d.title for d in db.query(Designation).filter(Designation.org_id == current.org_id)}
    manager_ids = {e.manager_id for e in results if e.manager_id}
    manager_map = {
        m.employee_id: m.full_name
        for m in db.query(Employee).filter(Employee.employee_id.in_(manager_ids or [-1]))
    }

    return [
        {
            "employee_id": e.employee_id,
            "full_name": e.full_name,
            "employee_code": e.employee_code,
            "email": e.email,
            "role": e.role,
            "department_id": e.department_id,
            "department_name": dept_map.get(e.department_id),
            "team_id": e.team_id,
            "team_name": team_map.get(e.team_id),
            "designation_id": e.designation_id,
            "designation_title": desig_map.get(e.designation_id),
            "manager_id": e.manager_id,
            "manager_name": manager_map.get(e.manager_id),
        }
        for e in results
    ]


@router.get("/managers")
def list_possible_managers(
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    """
    Any active employee is eligible to be designated as someone's manager —
    with multiple projects/teams, the person leading one may not have
    "manager" as their system role yet (see assign_employee below, which
    auto-elevates them to it the moment HR assigns them a direct report).
    Shared admin accounts (HR Admin / IT Admin) are excluded: they represent
    a role, not a person, and were never meant to appear as "the manager"
    of an individual employee.
    """
    candidates = (
        db.query(Employee)
        .filter(Employee.org_id == current.org_id, Employee.is_active.is_(True),
                Employee.is_shared_admin.is_(False))
        .order_by(Employee.full_name)
        .all()
    )
    return [{"employee_id": m.employee_id, "full_name": m.full_name, "role": m.role} for m in candidates]


# ── Assigning an employee into the hierarchy ────────────────────────────────────

@router.put("/employees/{employee_id}/assignment")
def assign_employee(
    employee_id: int,
    department_id: int | None = None,
    team_id: int | None = None,
    designation_id: int | None = None,
    manager_id: int | None = None,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    """
    HR Admin moves an employee to a different department/team/designation/
    manager. Multiple projects/teams means the person HR designates as a
    manager may still just be a plain "employee" in the system — assigning
    them a direct report here automatically elevates their role to
    'manager' (if it isn't already 'manager'/'hr_admin'/'it_admin'), since
    they now need approval permissions (leave decisions, etc.) to do the job.
    """
    emp = db.query(Employee).filter(Employee.employee_id == employee_id, Employee.org_id == current.org_id).first()
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if emp.is_shared_admin:
        raise HTTPException(status_code=400, detail="Shared admin accounts are not part of the personal org hierarchy")
    if employee_id == manager_id:
        raise HTTPException(status_code=400, detail="An employee cannot be their own manager")
    if department_id is not None:
        emp.department_id = department_id
    if team_id is not None:
        emp.team_id = team_id
    if designation_id is not None:
        emp.designation_id = designation_id
    if manager_id is not None:
        emp.manager_id = manager_id
        manager = db.query(Employee).filter(Employee.employee_id == manager_id).first()
        if manager is None:
            raise HTTPException(status_code=400, detail="manager_id does not exist")
        if manager.is_shared_admin:
            raise HTTPException(status_code=400, detail="A shared admin account cannot be assigned as a manager")
        if manager.role == "employee":
            manager.role = "manager"
    db.commit()
    return {"message": f"{emp.full_name}'s org assignment updated"}


@router.delete("/employees/{employee_id}")
def deactivate_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    """
    HR Admin offboards an employee (soft delete — sets is_active = False,
    preserving all their historical records for audit/payroll purposes
    rather than actually deleting rows). Deactivated employees can no
    longer sign in (see get_current_employee's is_active check) and drop
    out of the employee directory and manager picker.

    Direct reports who had this person as their manager keep that
    manager_id as a historical record — HR should reassign them to a new
    manager separately (via PUT .../assignment) as part of offboarding.
    """
    emp = db.query(Employee).filter(Employee.employee_id == employee_id, Employee.org_id == current.org_id).first()
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if emp.is_shared_admin:
        raise HTTPException(status_code=400, detail="Shared admin accounts cannot be deactivated here")
    if emp.employee_id == current.employee_id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    emp.is_active = False
    emp.employment_status = "terminated"
    emp.last_working_day = emp.last_working_day or datetime.utcnow().date()
    db.commit()
    return {"message": f"{emp.full_name} has been deactivated"}
