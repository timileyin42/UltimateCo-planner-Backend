"""
WebSocket Connection Manager for Real-time Notifications
"""
import json
import logging
from typing import Dict, List, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time notifications."""
    
    def __init__(self):
        # Store active connections by user_id
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # Store connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: int, device_info: Optional[Dict[str, Any]] = None):
        """Accept a WebSocket connection and register it for a user."""
        await websocket.accept()
        
        # Initialize user connections if not exists
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        # Add connection to user's set
        self.active_connections[user_id].add(websocket)
        
        # Store connection metadata
        self.connection_metadata[websocket] = {
            'user_id': user_id,
            'connected_at': datetime.utcnow(),
            'device_info': device_info or {},
            'last_ping': datetime.utcnow()
        }
        
        logger.info(f"WebSocket connected for user {user_id}. Total connections: {len(self.active_connections[user_id])}")
        
        # Send connection confirmation
        await self.send_personal_message({
            'type': 'connection_established',
            'message': 'Connected to real-time notifications',
            'timestamp': datetime.utcnow().isoformat()
        }, websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.connection_metadata:
            user_id = self.connection_metadata[websocket]['user_id']
            
            # Remove from user's connections
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                
                # Clean up empty user entries
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            
            # Remove metadata
            del self.connection_metadata[websocket]
            
            logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send a message to a specific WebSocket connection."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message to WebSocket: {str(e)}")
            # Connection might be closed, remove it
            self.disconnect(websocket)
    
    async def send_user_notification(self, user_id: int, notification: Dict[str, Any]) -> bool:
        """Send a notification to all active connections for a user."""
        if user_id not in self.active_connections:
            logger.info(f"No active WebSocket connections for user {user_id}")
            return False
        
        connections = self.active_connections[user_id].copy()  # Copy to avoid modification during iteration
        sent_count = 0
        failed_connections = []
        
        for websocket in connections:
            try:
                await websocket.send_text(json.dumps(notification))
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send notification via WebSocket: {str(e)}")
                failed_connections.append(websocket)
        
        # Clean up failed connections
        for websocket in failed_connections:
            self.disconnect(websocket)
        
        logger.info(f"Sent notification to {sent_count} WebSocket connections for user {user_id}")
        return sent_count > 0
    
    async def broadcast_to_users(self, user_ids: List[int], notification: Dict[str, Any]) -> Dict[int, bool]:
        """Send a notification to multiple users."""
        results = {}
        
        for user_id in user_ids:
            results[user_id] = await self.send_user_notification(user_id, notification)
        
        return results
    
    async def send_event_notification(self, event_id: int, participant_ids: List[int], notification: Dict[str, Any]) -> Dict[int, bool]:
        """Send event-related notification to all participants."""
        # Add event context to notification
        notification['event_id'] = event_id
        notification['type'] = 'event_notification'
        
        return await self.broadcast_to_users(participant_ids, notification)
    
    def get_user_connection_count(self, user_id: int) -> int:
        """Get the number of active connections for a user."""
        return len(self.active_connections.get(user_id, set()))
    
    def get_total_connections(self) -> int:
        """Get total number of active connections."""
        return sum(len(connections) for connections in self.active_connections.values())
    
    def get_connected_users(self) -> List[int]:
        """Get list of user IDs with active connections."""
        return list(self.active_connections.keys())
    
    def is_user_online(self, user_id: int) -> bool:
        """Check if a user has any active WebSocket connections."""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0

    def is_user_connected(self, user_id: int) -> bool:
        """Backward-compatible alias used by API routes."""
        return self.is_user_online(user_id)
    
    async def ping_connections(self):
        """Send ping to all connections to keep them alive."""
        ping_message = {
            'type': 'ping',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        all_connections = []
        for connections in self.active_connections.values():
            all_connections.extend(connections)
        
        failed_connections = []
        
        for websocket in all_connections:
            try:
                await websocket.send_text(json.dumps(ping_message))
                # Update last ping time
                if websocket in self.connection_metadata:
                    self.connection_metadata[websocket]['last_ping'] = datetime.utcnow()
            except Exception as e:
                logger.error(f"Failed to ping WebSocket connection: {str(e)}")
                failed_connections.append(websocket)
        
        # Clean up failed connections
        for websocket in failed_connections:
            self.disconnect(websocket)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get statistics about WebSocket connections."""
        return {
            'total_connections': self.get_total_connections(),
            'connected_users': len(self.get_connected_users()),
            'users_with_connections': {
                user_id: len(connections) 
                for user_id, connections in self.active_connections.items()
            }
        }


# Global connection manager instance
websocket_manager = ConnectionManager()


async def start_ping_task():
    """Background task to ping connections periodically."""
    while True:
        try:
            await websocket_manager.ping_connections()
            await asyncio.sleep(30)  # Ping every 30 seconds
        except Exception as e:
            logger.error(f"Error in ping task: {str(e)}")
            await asyncio.sleep(30)