"""
WebSocket Router for Real-time Notifications
"""
import json
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user_websocket
from app.services.websocket_manager import websocket_manager
from app.models.user_models import User

logger = logging.getLogger(__name__)
security = HTTPBearer()

router = APIRouter()


@router.websocket("/notifications/{user_id}")
async def websocket_notifications(
    websocket: WebSocket,
    user_id: int,
    token: Optional[str] = Query(None),
    device_type: Optional[str] = Query(None),
    device_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time notifications.
    
    Query Parameters:
    - token: JWT authentication token
    - device_type: Type of device (mobile, web, desktop)
    - device_id: Unique device identifier
    """
    try:
        # Authenticate user via token
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication token required")
            return
        
        # Verify user authentication
        try:
            current_user = await get_current_user_websocket(token, db)
            if not current_user or current_user.id != user_id:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication")
                return
        except Exception as e:
            logger.error(f"WebSocket authentication failed: {str(e)}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed")
            return
        
        # Prepare device info
        device_info = {
            'device_type': device_type,
            'device_id': device_id,
            'user_agent': websocket.headers.get('user-agent', ''),
            'ip_address': websocket.client.host if websocket.client else None
        }
        
        # Connect to WebSocket manager
        await websocket_manager.connect(websocket, user_id, device_info)
        
        try:
            while True:
                # Listen for messages from client
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                    await handle_client_message(websocket, user_id, message, db)
                except json.JSONDecodeError:
                    await websocket_manager.send_personal_message({
                        'type': 'error',
                        'message': 'Invalid JSON format'
                    }, websocket)
                except Exception as e:
                    logger.error(f"Error handling client message: {str(e)}")
                    await websocket_manager.send_personal_message({
                        'type': 'error',
                        'message': 'Error processing message'
                    }, websocket)
                    
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for user {user_id}")
        except Exception as e:
            logger.error(f"WebSocket error for user {user_id}: {str(e)}")
        finally:
            websocket_manager.disconnect(websocket)
            
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")
        except:
            pass


async def handle_client_message(websocket: WebSocket, user_id: int, message: Dict[str, Any], db: Session):
    """Handle messages received from WebSocket clients."""
    message_type = message.get('type')
    
    if message_type == 'pong':
        # Handle pong response to ping
        await websocket_manager.send_personal_message({
            'type': 'pong_received',
            'timestamp': message.get('timestamp')
        }, websocket)
        
    elif message_type == 'mark_notification_read':
        # Handle marking notification as read
        notification_id = message.get('notification_id')
        if notification_id:
            # TODO: Implement marking notification as read in database
            await websocket_manager.send_personal_message({
                'type': 'notification_marked_read',
                'notification_id': notification_id
            }, websocket)
    
    elif message_type == 'get_connection_info':
        # Send connection information
        stats = websocket_manager.get_connection_stats()
        user_connections = websocket_manager.get_user_connection_count(user_id)
        
        await websocket_manager.send_personal_message({
            'type': 'connection_info',
            'user_connections': user_connections,
            'total_connections': stats['total_connections'],
            'connected_users': stats['connected_users']
        }, websocket)
    
    elif message_type == 'heartbeat':
        # Respond to heartbeat
        await websocket_manager.send_personal_message({
            'type': 'heartbeat_response',
            'timestamp': message.get('timestamp'),
            'server_time': json.dumps({"timestamp": "now"})  # You might want to use actual timestamp
        }, websocket)
    
    else:
        # Unknown message type
        await websocket_manager.send_personal_message({
            'type': 'error',
            'message': f'Unknown message type: {message_type}'
        }, websocket)


@router.get("/websocket/stats")
async def get_websocket_stats(current_user: User = Depends(get_current_user)):
    """Get WebSocket connection statistics (admin only)."""
    # You might want to add admin check here
    return websocket_manager.get_connection_stats()


@router.post("/websocket/broadcast")
async def broadcast_notification(
    user_ids: list[int],
    notification: dict,
    current_user: User = Depends(get_current_user)
):
    """Broadcast notification to multiple users via WebSocket (admin only)."""
    # You might want to add admin check here
    results = await websocket_manager.broadcast_to_users(user_ids, notification)
    return {
        'message': 'Broadcast sent',
        'results': results,
        'total_users': len(user_ids),
        'successful_sends': sum(1 for success in results.values() if success)
    }