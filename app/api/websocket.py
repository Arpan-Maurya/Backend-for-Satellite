"""
Optional WebSocket endpoint for live risk updates.

Sends HIGH/CRITICAL risk alerts in real-time.
The REST APIs work completely without this WebSocket.
"""

import asyncio
import json
import logging
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])

# Connected WebSocket clients
_active_connections: Set[WebSocket] = set()


@router.websocket("/ws/live-risks")
async def live_risks(websocket: WebSocket):
    """
    WebSocket endpoint for real-time HIGH/CRITICAL risk updates.

    Clients connect and receive JSON messages when new high-risk
    conjunctions are detected. No authentication required for MVP.
    """
    await websocket.accept()
    _active_connections.add(websocket)
    logger.info("WebSocket client connected (%d total)", len(_active_connections))

    try:
        while True:
            # Keep connection alive; wait for client messages (ping/pong)
            data = await websocket.receive_text()
            # Echo acknowledgement
            await websocket.send_json({"type": "ack", "message": "received"})
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.warning("WebSocket error: %s", e)
    finally:
        _active_connections.discard(websocket)


async def broadcast_risk_alert(alert_data: dict) -> int:
    """
    Broadcast a risk alert to all connected WebSocket clients.

    Args:
        alert_data: Dict to send as JSON.

    Returns:
        Number of clients successfully notified.
    """
    if not _active_connections:
        return 0

    payload = json.dumps({"type": "risk_alert", "data": alert_data})
    sent = 0
    disconnected = set()

    for ws in _active_connections:
        try:
            await ws.send_text(payload)
            sent += 1
        except Exception:
            disconnected.add(ws)

    # Clean up disconnected clients
    _active_connections.difference_update(disconnected)

    logger.info("Broadcast risk alert to %d/%d clients", sent, sent + len(disconnected))
    return sent
