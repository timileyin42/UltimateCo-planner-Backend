"""
Redis pub/sub listener for broadcasting real-time updates to WebSocket clients.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional
import redis.asyncio as redis
from app.core.config import settings
from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)


class RedisSubscriber:
    """Redis pub/sub subscriber for relaying messages to WebSocket clients."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.is_running = False
        
    async def connect(self):
        """Connect to Redis."""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                encoding="utf-8"
            )
            self.pubsub = self.redis_client.pubsub()
            logger.info("Connected to Redis for pub/sub")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise
    
    async def disconnect(self):
        """Disconnect from Redis."""
        self.is_running = False
        if self.pubsub:
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Disconnected from Redis pub/sub")
    
    async def subscribe_to_user_payments(self, user_id: int):
        """Subscribe to payment updates for a specific user."""
        if not self.pubsub:
            logger.error("PubSub not initialized")
            return
        
        channel = f"user:{user_id}:payments"
        await self.pubsub.subscribe(channel)
        logger.info(f"Subscribed to channel: {channel}")
    
    async def subscribe_pattern(self, pattern: str):
        """Subscribe to a pattern of channels."""
        if not self.pubsub:
            logger.error("PubSub not initialized")
            return
        
        await self.pubsub.psubscribe(pattern)
        logger.info(f"Subscribed to pattern: {pattern}")
    
    async def listen_and_relay(self):
        """
        Listen to Redis pub/sub messages and relay to WebSocket clients.
        
        This should be run as a background task in the FastAPI application.
        """
        if not self.pubsub:
            logger.error("PubSub not initialized. Call connect() first.")
            return
        
        self.is_running = True
        logger.info("Started Redis pub/sub listener")
        
        try:
            # Subscribe to all user payment channels using pattern
            await self.subscribe_pattern("user:*:payments")
            
            async for message in self.pubsub.listen():
                if not self.is_running:
                    break
                
                if message["type"] == "pmessage":
                    # Pattern message
                    channel = message["channel"]
                    data = message["data"]
                    await self._handle_message(channel, data)
                elif message["type"] == "message":
                    # Direct channel message
                    channel = message["channel"]
                    data = message["data"]
                    await self._handle_message(channel, data)
                    
        except asyncio.CancelledError:
            logger.info("Redis listener task cancelled")
        except Exception as e:
            logger.error(f"Error in Redis listener: {str(e)}")
        finally:
            self.is_running = False
    
    async def _handle_message(self, channel: str, data: str):
        """Handle a message from Redis and relay to WebSocket clients."""
        try:
            # Parse channel to get user_id
            # Channel format: user:{user_id}:payments
            parts = channel.split(":")
            if len(parts) >= 2 and parts[0] == "user":
                user_id = int(parts[1])
                
                # Parse message data
                try:
                    message_data = json.loads(data) if isinstance(data, str) else data
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in Redis message: {data}")
                    return
                
                # Add notification type and formatting
                notification = {
                    "type": "payment_update",
                    "data": message_data,
                    "channel": channel
                }
                
                # Send to all WebSocket connections for this user
                sent = await websocket_manager.send_user_notification(user_id, notification)
                
                if sent:
                    logger.info(f"Relayed message from {channel} to user {user_id}")
                else:
                    logger.debug(f"No WebSocket connections for user {user_id}")
                    
        except ValueError as e:
            logger.error(f"Invalid user_id in channel {channel}: {str(e)}")
        except Exception as e:
            logger.error(f"Error handling Redis message from {channel}: {str(e)}")


# Global Redis subscriber instance
redis_subscriber = RedisSubscriber()


async def start_redis_listener():
    """
    Start the Redis pub/sub listener as a background task.
    
    This should be called when the FastAPI application starts.
    """
    try:
        await redis_subscriber.connect()
        await redis_subscriber.listen_and_relay()
    except Exception as e:
        logger.error(f"Redis listener failed: {str(e)}")
        raise


async def stop_redis_listener():
    """
    Stop the Redis pub/sub listener.
    
    This should be called when the FastAPI application shuts down.
    """
    await redis_subscriber.disconnect()
