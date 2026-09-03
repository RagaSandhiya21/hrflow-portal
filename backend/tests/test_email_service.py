"""
Unit tests for app/email_service.py — previously had ZERO test coverage.

Important distinction this test file exists to prove: the send logic
itself (real smtplib, real STARTTLS+login, correctly assembled HTML per
notification type) was already fully implemented, and every router
(leave.py, hr_requests.py, it_requests.py, profile.py) already calls the
right notify_*() function at the right lifecycle point. The "SMTP is a
silent no-op" gap was a DEPLOYMENT/config gap — SMTP_HOST/SMTP_USER/
SMTP_PASSWORD were simply never set in the live Render environment — not a
code gap. These tests mock smtplib.SMTP so they never touch a real mail
server, and assert:
  1. With no SMTP config, _send() logs and returns without raising.
  2. With SMTP config present, _send() actually opens a connection, does
     STARTTLS + login, and sends a correctly-addressed/subject-lined message.
  3. A handful of the notify_*() wrapper functions produce mail with the
     right recipient, subject, and key details embedded in the body.
"""
from unittest.mock import MagicMock, patch

from app.config import settings
from app import email_service


def test_send_is_a_no_op_without_smtp_config(monkeypatch, capsys):
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")

    with patch("smtplib.SMTP") as mock_smtp:
        email_service._send("someone@test.com", "Test Subject", "<p>Body</p>")
        mock_smtp.assert_not_called()

    captured = capsys.readouterr()
    assert "[email-stub]" in captured.out
    assert "Test Subject" in captured.out


def test_send_connects_and_sends_when_smtp_configured(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USER", "hrflow@test.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "app-password-123")

    mock_server = MagicMock()
    mock_server.__enter__.return_value = mock_server

    with patch("smtplib.SMTP", return_value=mock_server) as mock_smtp:
        email_service._send("employee@test.com", "Leave Approved", "<p>Hi</p>")

    mock_smtp.assert_called_once_with("smtp.gmail.com", 587)
    mock_server.ehlo.assert_called()
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("hrflow@test.com", "app-password-123")
    mock_server.send_message.assert_called_once()

    sent_msg = mock_server.send_message.call_args[0][0]
    assert sent_msg["To"] == "employee@test.com"
    assert "Leave Approved" in sent_msg["Subject"]


def test_send_uses_implicit_ssl_on_port_465_not_starttls(monkeypatch):
    """Port 465 (implicit SSL) must use SMTP_SSL, not smtplib.SMTP+starttls()
    — the two are different protocols and mixing them fails outright. This
    path exists because some hosts (Render's free tier included) block
    outbound port 587 entirely, surfacing as a raw socket-level
    "[Errno 101] Network is unreachable" rather than an auth error — 465 is
    the documented fallback that gets through on those hosts."""
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 465)
    monkeypatch.setattr(settings, "SMTP_USER", "hrflow@test.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "app-password-123")

    mock_server = MagicMock()
    mock_server.__enter__.return_value = mock_server

    with patch("smtplib.SMTP_SSL", return_value=mock_server) as mock_smtp_ssl, \
         patch("smtplib.SMTP") as mock_smtp_plain:
        email_service._send("employee@test.com", "Leave Approved", "<p>Hi</p>")

    mock_smtp_ssl.assert_called_once_with("smtp.gmail.com", 465)
    mock_smtp_plain.assert_not_called()          # must not also try the STARTTLS path
    mock_server.starttls.assert_not_called()     # SMTP_SSL doesn't use STARTTLS at all
    mock_server.login.assert_called_once_with("hrflow@test.com", "app-password-123")
    mock_server.send_message.assert_called_once()
    sent_msg = mock_server.send_message.call_args[0][0]
    assert sent_msg["From"] == "hrflow@test.com"


def test_send_failure_is_caught_and_logged_not_raised(monkeypatch, capsys):
    """A bad password or unreachable SMTP host must never crash the request
    that triggered the notification (e.g. approving leave) — it should log
    and move on."""
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(settings, "SMTP_USER", "hrflow@test.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "wrong-password")

    with patch("smtplib.SMTP", side_effect=Exception("535 Authentication failed")):
        email_service._send("employee@test.com", "Subject", "<p>Body</p>")  # must not raise

    captured = capsys.readouterr()
    assert "[email] FAILED" in captured.out
    assert "535 Authentication failed" in captured.out


def _configure_smtp(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(settings, "SMTP_USER", "hrflow@test.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "app-password-123")


def _html_body(sent_msg) -> str:
    """MIMEText payloads get base64-encoded whenever the content has
    non-ASCII characters (e.g. the ✓/✗ glyphs used in decision emails), so
    always decode explicitly rather than assuming plain text."""
    part = sent_msg.get_payload()[0]
    return part.get_payload(decode=True).decode("utf-8")


def test_notify_leave_applied_content(monkeypatch):
    _configure_smtp(monkeypatch)
    mock_server = MagicMock()
    mock_server.__enter__.return_value = mock_server

    with patch("smtplib.SMTP", return_value=mock_server):
        email_service.notify_leave_applied(
            "manager@test.com", "Manager Name", "Employee Name",
            "Casual Leave", "2026-06-10", "2026-06-11", 2,
        )

    sent_msg = mock_server.send_message.call_args[0][0]
    assert sent_msg["To"] == "manager@test.com"
    body = _html_body(sent_msg)
    assert "Employee Name" in body
    assert "Casual Leave" in body


def test_notify_leave_decision_shows_rejected_in_red(monkeypatch):
    _configure_smtp(monkeypatch)
    mock_server = MagicMock()
    mock_server.__enter__.return_value = mock_server

    with patch("smtplib.SMTP", return_value=mock_server):
        email_service.notify_leave_decision(
            "employee@test.com", "Employee Name", "rejected",
            "Sick Leave", "2026-07-01", "2026-07-01", comments="Team is short-staffed that week.",
        )

    sent_msg = mock_server.send_message.call_args[0][0]
    body = _html_body(sent_msg)
    assert "Rejected" in body
    assert "#dc2626" in body  # red
    assert "Team is short-staffed" in body


def test_notify_it_status_change_content(monkeypatch):
    _configure_smtp(monkeypatch)
    mock_server = MagicMock()
    mock_server.__enter__.return_value = mock_server

    with patch("smtplib.SMTP", return_value=mock_server):
        email_service.notify_it_status_change(
            "employee@test.com", "Employee Name", "Laptop won't turn on",
            "open", "resolved", notes="Replaced the charger; confirmed working.",
        )

    sent_msg = mock_server.send_message.call_args[0][0]
    body = _html_body(sent_msg)
    assert "Laptop won't turn on" in body
    assert "Resolved" in body
    assert "Replaced the charger" in body
