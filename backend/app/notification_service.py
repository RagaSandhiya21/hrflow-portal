"""
In-portal notifications: writes a Notification row (so GET /notifications
still works for anyone not currently connected) AND pushes it live over
WebSocket to the recipient if they have the portal open (see ws_manager.py).

This is the "in-portal" half of the proposal's "Dual notifications (email +
in-portal)" requirement — call it next to the matching email_service.notify_*
call at every event: leave decisions, HR request updates, IT status
changes, profile change-request decisions, chatbot escalations, etc.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Notification
from app.ws_manager import manager


def notify(db: Session, recipient_id: int, notification_type: str,
           title: str, message: str, deep_link: str | None = None) -> Notification:
    n = Notification(
        recipient_id=recipient_id,
        notification_type=notification_type,
        title=title,
        message=message,
        deep_link=deep_link,
        is_read=False,
        created_at=datetime.utcnow(),
    )
    db.add(n)
    db.flush()  # get notification_id without committing the caller's transaction early

    manager.push_sync(recipient_id, {
        "notification_id": n.notification_id,
        "notification_type": notification_type,
        "title": title,
        "message": message,
        "deep_link": deep_link,
        "created_at": n.created_at.isoformat(),
    })
    return n
