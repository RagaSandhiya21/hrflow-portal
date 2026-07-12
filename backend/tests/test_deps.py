"""
Unit tests for app/deps.py role guards — no DB needed, just plain objects
with the attributes `require_role`/`require_personal_employee` read.
"""
import os
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from fastapi import HTTPException

from app.deps import require_role, require_personal_employee


class FakeEmployee:
    def __init__(self, role, is_shared_admin=False):
        self.role = role
        self.is_shared_admin = is_shared_admin


def test_require_role_allows_matching_role():
    checker = require_role("hr_admin")
    emp = FakeEmployee(role="hr_admin")
    assert checker(emp) is emp


def test_require_role_rejects_other_role():
    checker = require_role("hr_admin")
    emp = FakeEmployee(role="employee")
    with pytest.raises(HTTPException) as exc:
        checker(emp)
    assert exc.value.status_code == 403


def test_require_role_super_admin_always_allowed():
    checker = require_role("hr_admin")
    emp = FakeEmployee(role="super_admin")
    assert checker(emp) is emp


def test_require_personal_employee_allows_real_employee():
    emp = FakeEmployee(role="employee", is_shared_admin=False)
    assert require_personal_employee(emp) is emp


def test_require_personal_employee_blocks_shared_admin_account():
    """The core of the admin-account fix: a shared HR/IT Admin account must
    never be treated as if it were a person with personal HR records."""
    emp = FakeEmployee(role="hr_admin", is_shared_admin=True)
    with pytest.raises(HTTPException) as exc:
        require_personal_employee(emp)
    assert exc.value.status_code == 403
    assert "shared admin account" in exc.value.detail.lower()
