"""
Email notification service.

Configure SMTP in backend/.env:
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=your-gmail@gmail.com
    SMTP_PASSWORD=your-app-password   # Gmail → Security → App passwords

If SMTP_HOST is blank the functions print a log line and return silently —
so the app works fully without email configured (local dev).

Gmail app password setup:
  1. Enable 2-factor auth on your Google account
  2. Go to myaccount.google.com → Security → App passwords
  3. Generate a password for "Mail" → copy the 16-char code
  4. Use that as SMTP_PASSWORD (not your real Gmail password)
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import settings


def _send(to_email: str, subject: str, html_body: str):
    """Internal sender — silent on failure."""
    if not getattr(settings, "SMTP_HOST", "") or not getattr(settings, "SMTP_USER", ""):
        print(f"[email-stub] Would send '{subject}' to {to_email}")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["From"]    = settings.SMTP_USER
        msg["To"]      = to_email
        msg["Subject"] = f"[HRFlow] {subject}"
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(settings.SMTP_HOST, int(getattr(settings, "SMTP_PORT", 587))) as s:
            s.ehlo(); s.starttls(); s.ehlo()
            s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)
        print(f"[email] Sent '{subject}' → {to_email}")
    except Exception as e:
        print(f"[email] FAILED '{subject}' → {to_email}: {e}")


def _base(content: str) -> str:
    return f"""
    <div style="font-family:Inter,sans-serif;max-width:560px;margin:auto;padding:24px">
      <div style="background:#1F5C5C;padding:16px 24px;border-radius:12px 12px 0 0">
        <h2 style="color:#fff;margin:0">HRFlow</h2>
        <p style="color:#9ED3D3;margin:4px 0 0;font-size:13px">Employee Self-Service Portal</p>
      </div>
      <div style="background:#f9fafb;border:1px solid #e5e7eb;border-top:none;
                  padding:24px;border-radius:0 0 12px 12px">
        {content}
        <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">
        <p style="color:#9ca3af;font-size:12px;margin:0">
          This is an automated notification from HRFlow. Please do not reply to this email.
        </p>
      </div>
    </div>"""


# ── Leave notifications ───────────────────────────────────────────────────────

def notify_leave_applied(manager_email: str, manager_name: str,
                          emp_name: str, leave_type: str,
                          start: str, end: str, days: float):
    _send(manager_email, f"Leave Request — {emp_name}", _base(f"""
        <p style="color:#374151">Hi <strong>{manager_name}</strong>,</p>
        <p style="color:#374151">
          <strong>{emp_name}</strong> has applied for leave and needs your approval.
        </p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
          <tr style="background:#f3f4f6"><td style="padding:8px 12px;color:#6b7280;font-size:13px">Leave Type</td>
              <td style="padding:8px 12px;font-weight:600">{leave_type}</td></tr>
          <tr><td style="padding:8px 12px;color:#6b7280;font-size:13px">Dates</td>
              <td style="padding:8px 12px">{start} to {end}</td></tr>
          <tr style="background:#f3f4f6"><td style="padding:8px 12px;color:#6b7280;font-size:13px">Days</td>
              <td style="padding:8px 12px">{days}</td></tr>
        </table>
        <p style="color:#374151">Please log in to HRFlow to approve or reject this request.</p>
    """))


def notify_leave_decision(emp_email: str, emp_name: str,
                           decision: str, leave_type: str,
                           start: str, end: str, comments: str = ""):
    color   = "#16a34a" if decision == "approved" else "#dc2626"
    label   = "Approved ✓" if decision == "approved" else "Rejected ✗"
    _send(emp_email, f"Leave {label} — {leave_type}", _base(f"""
        <p style="color:#374151">Hi <strong>{emp_name}</strong>,</p>
        <p style="color:#374151">Your leave request has been
          <strong style="color:{color}">{label}</strong>.
        </p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
          <tr style="background:#f3f4f6"><td style="padding:8px 12px;color:#6b7280;font-size:13px">Leave Type</td>
              <td style="padding:8px 12px;font-weight:600">{leave_type}</td></tr>
          <tr><td style="padding:8px 12px;color:#6b7280;font-size:13px">Dates</td>
              <td style="padding:8px 12px">{start} to {end}</td></tr>
          {'<tr style="background:#f3f4f6"><td style="padding:8px 12px;color:#6b7280;font-size:13px">Manager comment</td><td style="padding:8px 12px">' + comments + '</td></tr>' if comments else ''}
        </table>
        <p style="color:#374151">Log in to HRFlow to view your updated leave balance.</p>
    """))


# ── HR Request notifications ───────────────────────────────────────────────────

def notify_hr_request_raised(hr_email: str, emp_name: str, subject: str, category: str):
    _send(hr_email, f"New HR Request — {subject}", _base(f"""
        <p style="color:#374151">A new HR request has been raised and needs your attention.</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
          <tr style="background:#f3f4f6"><td style="padding:8px 12px;color:#6b7280;font-size:13px">Raised by</td>
              <td style="padding:8px 12px;font-weight:600">{emp_name}</td></tr>
          <tr><td style="padding:8px 12px;color:#6b7280;font-size:13px">Category</td>
              <td style="padding:8px 12px">{category}</td></tr>
          <tr style="background:#f3f4f6"><td style="padding:8px 12px;color:#6b7280;font-size:13px">Subject</td>
              <td style="padding:8px 12px">{subject}</td></tr>
        </table>
        <p style="color:#374151">Log in to HRFlow to action this request.</p>
    """))


def notify_hr_request_resolved(emp_email: str, emp_name: str,
                                subject: str, status: str, notes: str = ""):
    color = "#16a34a" if status in ("resolved", "closed") else "#6b7280"
    _send(emp_email, f"HR Request Update — {subject}", _base(f"""
        <p style="color:#374151">Hi <strong>{emp_name}</strong>,</p>
        <p style="color:#374151">Your HR request has been updated.</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
          <tr style="background:#f3f4f6"><td style="padding:8px 12px;color:#6b7280;font-size:13px">Subject</td>
              <td style="padding:8px 12px;font-weight:600">{subject}</td></tr>
          <tr><td style="padding:8px 12px;color:#6b7280;font-size:13px">Status</td>
              <td style="padding:8px 12px;font-weight:600;color:{color}">{status.replace("_"," ").title()}</td></tr>
          {'<tr style="background:#f3f4f6"><td style="padding:8px 12px;color:#6b7280;font-size:13px">Resolution note</td><td style="padding:8px 12px">' + notes + '</td></tr>' if notes else ''}
        </table>
        <p style="color:#374151">Log in to HRFlow for more details.</p>
    """))


# ── IT Request notifications ───────────────────────────────────────────────────

def notify_it_status_change(emp_email: str, emp_name: str,
                              subject: str, old_status: str, new_status: str, notes: str = ""):
    colors = {"resolved": "#16a34a", "closed": "#16a34a",
               "in_progress": "#d97706", "on_hold": "#9ca3af"}
    color = colors.get(new_status, "#374151")
    _send(emp_email, f"IT Request Update — {subject}", _base(f"""
        <p style="color:#374151">Hi <strong>{emp_name}</strong>,</p>
        <p style="color:#374151">Your IT request status has been updated.</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
          <tr style="background:#f3f4f6"><td style="padding:8px 12px;color:#6b7280;font-size:13px">Request</td>
              <td style="padding:8px 12px;font-weight:600">{subject}</td></tr>
          <tr><td style="padding:8px 12px;color:#6b7280;font-size:13px">Previous status</td>
              <td style="padding:8px 12px">{old_status.replace("_"," ").title()}</td></tr>
          <tr style="background:#f3f4f6"><td style="padding:8px 12px;color:#6b7280;font-size:13px">New status</td>
              <td style="padding:8px 12px;font-weight:600;color:{color}">{new_status.replace("_"," ").title()}</td></tr>
          {'<tr><td style="padding:8px 12px;color:#6b7280;font-size:13px">Notes</td><td style="padding:8px 12px">' + notes + '</td></tr>' if notes else ''}
        </table>
        <p style="color:#374151">Log in to HRFlow for full details.</p>
    """))


# ── Profile change request notifications ──────────────────────────────────────

def notify_change_request_raised(hr_email: str, emp_name: str, field_name: str):
    _send(hr_email, f"Profile Change Request — {emp_name}", _base(f"""
        <p style="color:#374151">An employee has submitted a profile change request that requires your approval.</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
          <tr style="background:#f3f4f6"><td style="padding:8px 12px;color:#6b7280;font-size:13px">Employee</td>
              <td style="padding:8px 12px;font-weight:600">{emp_name}</td></tr>
          <tr><td style="padding:8px 12px;color:#6b7280;font-size:13px">Field</td>
              <td style="padding:8px 12px">{field_name.replace("_"," ").title()}</td></tr>
        </table>
        <p style="color:#374151">Log in to HRFlow → Profile → Pending Approvals to review.</p>
    """))


def notify_change_request_decision(emp_email: str, emp_name: str,
                                    field_name: str, decision: str, notes: str = ""):
    color = "#16a34a" if decision == "approved" else "#dc2626"
    label = "Approved ✓" if decision == "approved" else "Rejected ✗"
    _send(emp_email, f"Profile Change Request {label}", _base(f"""
        <p style="color:#374151">Hi <strong>{emp_name}</strong>,</p>
        <p style="color:#374151">Your profile change request has been
          <strong style="color:{color}">{label}</strong> by HR.
        </p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
          <tr style="background:#f3f4f6"><td style="padding:8px 12px;color:#6b7280;font-size:13px">Field</td>
              <td style="padding:8px 12px;font-weight:600">{field_name.replace("_"," ").title()}</td></tr>
          {'<tr><td style="padding:8px 12px;color:#6b7280;font-size:13px">HR Note</td><td style="padding:8px 12px">' + notes + '</td></tr>' if notes else ''}
        </table>
        <p style="color:#374151">Log in to HRFlow → My Profile to see the current values.</p>
    """))
