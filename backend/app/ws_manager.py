"""
In-portal real-time notifications over WebSocket (FastAPI's built-in
WebSocket support), per the proposal's tech stack: "in-portal notification
system (FastAPI WebSocket)". Previously notifications were poll-only
(GET /notifications); this adds an actual push channel alongside that.

Usage from any router that creates a Notification row:
    from app.ws_manager import manager
    await manager.push(employee_id, {"type": "leave_decision", "title": ..., ...})

Since most of the existing routers are synchronous `def` endpoints (not
`async def`), `push_sync` is provided as a fire-and-forget wrapper that
schedules the coroutine without requiring the calling endpoint to be async.
"""
import asyncio
import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # employee_id -> set of live WebSocket connections (an employee may
        # have the portal open in more than one tab/device).
        self._connections: dict[int, set[WebSocket]] = {}

    async def connect(self, employee_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(employee_id, set()).add(ws)

    def disconnect(self, employee_id: int, ws: WebSocket) -> None:
        conns = self._connections.get(employee_id)
        if conns and ws in conns:
            conns.discard(ws)
            if not conns:
                self._connections.pop(employee_id, None)

    async def push(self, employee_id: int, payload: dict) -> None:
        conns = list(self._connections.get(employee_id, ()))
        if not conns:
            return
        message = json.dumps(payload, default=str)
        stale = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.info("Dropping stale websocket for employee %s: %s", employee_id, e)
                stale.append(ws)
        for ws in stale:
            self.disconnect(employee_id, ws)

    def push_sync(self, employee_id: int, payload: dict) -> None:
        """Fire-and-forget push from a synchronous request handler."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.push(employee_id, payload))
            else:
                loop.run_until_complete(self.push(employee_id, payload))
        except RuntimeError:
            # No event loop in this thread (e.g. a background/test context) -
            # notification simply won't be pushed live; the polling
            # GET /notifications endpoint still has it.
            logger.info("No running event loop; skipping live push for employee %s", employee_id)


manager = ConnectionManager()
