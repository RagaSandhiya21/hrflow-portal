# This script patches app/schemas.py to add attendance_summary and
# pending_change_requests to DashboardSummary
import re

path = 'app/schemas.py'
src = open(path).read()

old = '''class DashboardSummary(BaseModel):
    employee: EmployeeOut
    leave_balances: List[LeaveBalanceMini]
    pending_leave_requests: int
    latest_payslip_month: Optional[str] = None
    open_hr_requests: int
    open_it_requests: int
    pending_approvals: int = 0  # only non-zero for managers / hr_admin
    unread_notifications: int = 0'''

new = '''class DashboardSummary(BaseModel):
    employee: EmployeeOut
    leave_balances: List[LeaveBalanceMini]
    pending_leave_requests: int
    latest_payslip_month: Optional[str] = None
    open_hr_requests: int
    open_it_requests: int
    pending_approvals: int = 0
    unread_notifications: int = 0
    attendance_summary: dict = {}
    pending_change_requests: int = 0'''

if old in src:
    src = src.replace(old, new)
    open(path, 'w').write(src)
    print('DashboardSummary patched OK')
else:
    print('Pattern not found - check schemas.py manually')
    # Show current DashboardSummary
    idx = src.find('class DashboardSummary')
    print(src[idx:idx+500])
