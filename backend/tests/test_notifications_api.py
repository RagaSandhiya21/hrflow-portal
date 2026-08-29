"""
Integration tests for app/routers/notifications.py — previously had zero
dedicated test coverage. Covers the REST endpoints (GET / POST .../read);
the WebSocket push path (app/ws_manager.py) is exercised indirectly by the
E2E flows in test_e2e_flows.py that trigger notify() calls.
"""
from datetime import datetime


def _make_notification(db_session, recipient_id, title="Test notification", is_read=False):
    from app.models import Notification
    n = Notification(
        recipient_id=recipient_id, notification_type="test_event",
        title=title, message="Something happened.", is_read=is_read,
        created_at=datetime.utcnow(),
    )
    db_session.add(n); db_session.commit(); db_session.refresh(n)
    return n


def test_employee_sees_only_their_own_notifications(client, seeded, db_session):
    mine = _make_notification(db_session, seeded.employee.employee_id, "Mine")
    _make_notification(db_session, seeded.manager.employee_id, "Not mine")

    token = seeded.token_for(seeded.employee)
    res = client.get("/notifications", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    titles = [n["title"] for n in res.json()]
    assert "Mine" in titles
    assert "Not mine" not in titles
    assert any(n["notification_id"] == mine.notification_id for n in res.json())


def test_unread_only_filter(client, seeded, db_session):
    _make_notification(db_session, seeded.employee.employee_id, "Read one", is_read=True)
    unread = _make_notification(db_session, seeded.employee.employee_id, "Unread one", is_read=False)

    token = seeded.token_for(seeded.employee)
    res = client.get("/notifications", params={"unread_only": True},
                      headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    ids = [n["notification_id"] for n in res.json()]
    assert unread.notification_id in ids
    assert len(res.json()) == 1


def test_mark_notification_read(client, seeded, db_session):
    n = _make_notification(db_session, seeded.employee.employee_id)
    token = seeded.token_for(seeded.employee)

    res = client.post(f"/notifications/{n.notification_id}/read",
                       headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    assert res.json()["is_read"] is True

    db_session.refresh(n)
    assert n.is_read is True
    assert n.read_at is not None


def test_cannot_mark_another_employees_notification_read(client, seeded, db_session):
    n = _make_notification(db_session, seeded.manager.employee_id)
    token = seeded.token_for(seeded.employee)

    res = client.post(f"/notifications/{n.notification_id}/read",
                       headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404


def test_marking_nonexistent_notification_returns_404(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.post("/notifications/999999/read", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404


def test_notification_service_helper_persists_and_is_listable(client, seeded, db_session):
    """app/notification_service.notify() is the function every other router
    calls to push a notification — exercise it directly rather than only
    through another module's side effect."""
    from app.notification_service import notify
    notify(db_session, seeded.employee.employee_id, "test_event",
           "Direct notify() call", "Body text here.", deep_link="/somewhere")
    db_session.commit()

    token = seeded.token_for(seeded.employee)
    res = client.get("/notifications", headers={"Authorization": f"Bearer {token}"})
    assert any(n["title"] == "Direct notify() call" and n["deep_link"] == "/somewhere" for n in res.json())
