from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.deps import get_current_employee
from app.models import Employee, Notification
from app.schemas import NotificationOut
from app.security import decode_access_token
from app.ws_manager import manager

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def my_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    query = db.query(Notification).filter(Notification.recipient_id == current.employee_id)
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    return query.order_by(Notification.created_at.desc()).limit(50).all()


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    n = (
        db.query(Notification)
        .filter(Notification.notification_id == notification_id, Notification.recipient_id == current.employee_id)
        .first()
    )
    if n is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = True
    n.read_at = datetime.utcnow()
    db.commit()
    db.refresh(n)
    return n


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket, token: str = Query(...)):
    """
    Real-time in-portal notification stream (Module 7 / tech-stack
    requirement: "in-portal notification system (FastAPI WebSocket)").

    Browsers can't set an Authorization header on a WebSocket handshake, so
    the frontend passes the same bearer JWT as a query string instead:
        new WebSocket(`${WS_BASE}/notifications/ws?token=${accessToken}`)

    Once connected, any call to notification_service.notify(db, employee_id, ...)
    anywhere in the app pushes JSON straight to this socket.
    """
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=4401)
        return

    db = SessionLocal()
    try:
        employee = db.query(Employee).filter(Employee.employee_id == int(payload["sub"])).first()
        if employee is None or not employee.is_active:
            await websocket.close(code=4401)
            return
        employee_id = employee.employee_id
    finally:
        db.close()

    await manager.connect(employee_id, websocket)
    try:
        while True:
            # We don't expect the client to send anything meaningful, but we
            # must keep awaiting receive() to detect disconnects promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(employee_id, websocket)
