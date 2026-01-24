"""
WebSocket connection manager for real-time updates
"""
from typing import Dict, List
from fastapi import WebSocket
import json
import asyncio


class WebSocketManager:
    """Manages WebSocket connections and broadcasts"""

    def __init__(self):
        # Active connections by user_id
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # Document subscriptions: document_id -> [user_ids]
        self.document_subscriptions: Dict[int, List[int]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        """Connect a new WebSocket client"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        """Disconnect a WebSocket client"""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def subscribe_document(self, document_id: int, user_id: int):
        """Subscribe a user to document updates"""
        if document_id not in self.document_subscriptions:
            self.document_subscriptions[document_id] = []
        if user_id not in self.document_subscriptions[document_id]:
            self.document_subscriptions[document_id].append(user_id)

    async def unsubscribe_document(self, document_id: int, user_id: int):
        """Unsubscribe a user from document updates"""
        if document_id in self.document_subscriptions:
            if user_id in self.document_subscriptions[document_id]:
                self.document_subscriptions[document_id].remove(user_id)
            if not self.document_subscriptions[document_id]:
                del self.document_subscriptions[document_id]

    async def send_personal_message(self, message: dict, user_id: int):
        """Send a message to a specific user"""
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"Error sending message to user {user_id}: {e}")
                    disconnected.append(connection)

            # Remove disconnected connections
            for conn in disconnected:
                self.disconnect(conn, user_id)

    async def send_document_progress(
        self,
        document_id: int,
        status: str,
        progress: int,
        message: str
    ):
        """
        Send document processing progress to subscribed users

        Args:
            document_id: ID of the document being processed
            status: Current status (started, processing, completed, error)
            progress: Progress percentage (0-100)
            message: Progress message
        """
        if document_id not in self.document_subscriptions:
            return

        update = {
            "type": "document_progress",
            "document_id": document_id,
            "status": status,
            "progress": progress,
            "message": message
        }

        # Send to all subscribed users
        for user_id in self.document_subscriptions[document_id]:
            await self.send_personal_message(update, user_id)

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients"""
        for user_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, user_id)

    async def broadcast_to_role(self, message: dict, role: str):
        """Broadcast to users with specific role (requires user role tracking)"""
        # This would require tracking user roles in active_connections
        # For now, just broadcast to all
        await self.broadcast(message)


# Global WebSocket manager instance
websocket_manager = WebSocketManager()
