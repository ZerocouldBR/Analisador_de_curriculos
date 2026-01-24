"""
WebSocket endpoints for real-time updates
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Optional
import json

from app.core.websocket_manager import websocket_manager
from app.core.dependencies import get_current_user_ws
from app.db.models import User

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    WebSocket endpoint for real-time updates

    Clients should connect with JWT token as query parameter:
    ws://localhost:8000/api/v1/ws?token=<jwt_token>

    Messages format:
    - Subscribe to document: {"action": "subscribe_document", "document_id": 123}
    - Unsubscribe: {"action": "unsubscribe_document", "document_id": 123}

    Server sends:
    - Document progress: {"type": "document_progress", "document_id": 123, "status": "processing", "progress": 50, "message": "..."}
    """
    # Validate token and get user
    try:
        from app.core.security import decode_access_token
        from app.db.database import SessionLocal

        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))

        db = SessionLocal()
        user = db.query(User).filter(User.id == user_id).first()
        db.close()

        if not user:
            await websocket.close(code=1008, reason="Invalid token")
            return

    except Exception as e:
        await websocket.close(code=1008, reason=f"Authentication failed: {str(e)}")
        return

    # Connect WebSocket
    await websocket_manager.connect(websocket, user_id)

    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "message": f"Connected as {user.email}",
            "user_id": user_id
        })

        # Listen for messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            action = message.get("action")

            if action == "subscribe_document":
                document_id = message.get("document_id")
                if document_id:
                    await websocket_manager.subscribe_document(document_id, user_id)
                    await websocket.send_json({
                        "type": "subscribed",
                        "document_id": document_id,
                        "message": f"Subscribed to document {document_id}"
                    })

            elif action == "unsubscribe_document":
                document_id = message.get("document_id")
                if document_id:
                    await websocket_manager.unsubscribe_document(document_id, user_id)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "document_id": document_id,
                        "message": f"Unsubscribed from document {document_id}"
                    })

            elif action == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, user_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        websocket_manager.disconnect(websocket, user_id)


@router.get("/ws/status")
async def websocket_status():
    """Get WebSocket server status"""
    return {
        "active_connections": len(websocket_manager.active_connections),
        "document_subscriptions": len(websocket_manager.document_subscriptions),
        "status": "running"
    }
