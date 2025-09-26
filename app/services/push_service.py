"""
Firebase Cloud Messaging (FCM) Push Notification Service
"""
import json
import logging
from typing import List, Dict, Any, Optional
from firebase_admin import messaging, credentials, initialize_app
from firebase_admin.exceptions import FirebaseError
from app.core.config import settings
from app.core.circuit_breaker import firebase_circuit_breaker, firebase_fallback
from app.models.notification_models import DevicePlatform, NotificationType

logger = logging.getLogger(__name__)

class PushNotificationService:
    """Service for sending push notifications via Firebase Cloud Messaging."""
    
    def __init__(self):
        self._app = None
        self._initialize_firebase()
    
    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK."""
        try:
            # Prioritize JSON credentials (best for production with Doppler)
            if settings.FIREBASE_CREDENTIALS_JSON:
                # Initialize with JSON credentials from environment variable
                cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
                cred = credentials.Certificate(cred_dict)
                self._app = initialize_app(cred)
                logger.info("Firebase initialized with JSON credentials from environment")
            elif settings.FIREBASE_CREDENTIALS_PATH:
                # Fallback to file path (mainly for local development)
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                self._app = initialize_app(cred)
                logger.info("Firebase initialized with credentials file")
            else:
                logger.warning("Firebase credentials not configured. Push notifications will be disabled.")
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid Firebase credentials JSON format: {str(e)}")
            self._app = None
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            self._app = None
    
    def is_available(self) -> bool:
        """Check if push notification service is available."""
        return self._app is not None
    
    @firebase_circuit_breaker(fallback=firebase_fallback)
    async def send_notification(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        notification_type: Optional[NotificationType] = None,
        platform: Optional[DevicePlatform] = None
    ) -> bool:
        """
        Send a push notification to a single device.
        
        Args:
            device_token: FCM device token
            title: Notification title
            body: Notification body
            data: Additional data payload
            notification_type: Type of notification
            platform: Target platform (iOS, Android, Web)
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.is_available():
            logger.warning("Push notification service not available")
            return False
        
        try:
            # Prepare notification payload
            notification = messaging.Notification(
                title=title,
                body=body
            )
            
            # Prepare data payload
            data_payload = data or {}
            if notification_type:
                data_payload['notification_type'] = notification_type.value
            
            # Platform-specific configuration
            android_config = None
            apns_config = None
            webpush_config = None
            
            if platform == DevicePlatform.ANDROID:
                android_config = messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        title=title,
                        body=body,
                        icon='ic_notification',
                        color='#FF6B35',
                        sound='default'
                    )
                )
            elif platform == DevicePlatform.IOS:
                apns_config = messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            alert=messaging.ApsAlert(
                                title=title,
                                body=body
                            ),
                            badge=1,
                            sound='default'
                        )
                    )
                )
            elif platform == DevicePlatform.WEB:
                webpush_config = messaging.WebpushConfig(
                    notification=messaging.WebpushNotification(
                        title=title,
                        body=body,
                        icon='/icon-192x192.png'
                    )
                )
            
            # Create message
            message = messaging.Message(
                notification=notification,
                data={k: str(v) for k, v in data_payload.items()},  # FCM requires string values
                token=device_token,
                android=android_config,
                apns=apns_config,
                webpush=webpush_config
            )
            
            # Send message
            response = messaging.send(message)
            logger.info(f"Successfully sent push notification: {response}")
            return True
            
        except FirebaseError as e:
            logger.error(f"Firebase error sending push notification: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending push notification: {str(e)}")
            return False
    
    @firebase_circuit_breaker(fallback=firebase_fallback)
    async def send_multicast_notification(
        self,
        device_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        notification_type: Optional[NotificationType] = None
    ) -> Dict[str, Any]:
        """
        Send a push notification to multiple devices.
        
        Args:
            device_tokens: List of FCM device tokens
            title: Notification title
            body: Notification body
            data: Additional data payload
            notification_type: Type of notification
            
        Returns:
            Dict with success_count, failure_count, and failed_tokens
        """
        if not self.is_available():
            logger.warning("Push notification service not available")
            return {
                'success_count': 0,
                'failure_count': len(device_tokens),
                'failed_tokens': device_tokens
            }
        
        if not device_tokens:
            return {
                'success_count': 0,
                'failure_count': 0,
                'failed_tokens': []
            }
        
        try:
            # Prepare notification payload
            notification = messaging.Notification(
                title=title,
                body=body
            )
            
            # Prepare data payload
            data_payload = data or {}
            if notification_type:
                data_payload['notification_type'] = notification_type.value
            
            # Create multicast message
            message = messaging.MulticastMessage(
                notification=notification,
                data={k: str(v) for k, v in data_payload.items()},
                tokens=device_tokens
            )
            
            # Send multicast message
            response = messaging.send_multicast(message)
            
            # Process results
            failed_tokens = []
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    failed_tokens.append(device_tokens[idx])
                    logger.warning(f"Failed to send to token {device_tokens[idx]}: {resp.exception}")
            
            logger.info(f"Multicast notification sent. Success: {response.success_count}, Failed: {response.failure_count}")
            
            return {
                'success_count': response.success_count,
                'failure_count': response.failure_count,
                'failed_tokens': failed_tokens
            }
            
        except FirebaseError as e:
            logger.error(f"Firebase error sending multicast notification: {str(e)}")
            return {
                'success_count': 0,
                'failure_count': len(device_tokens),
                'failed_tokens': device_tokens
            }
        except Exception as e:
            logger.error(f"Unexpected error sending multicast notification: {str(e)}")
            return {
                'success_count': 0,
                'failure_count': len(device_tokens),
                'failed_tokens': device_tokens
            }
    
    @firebase_circuit_breaker(fallback=firebase_fallback)
    async def send_topic_notification(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        notification_type: Optional[NotificationType] = None
    ) -> bool:
        """
        Send a push notification to a topic.
        
        Args:
            topic: FCM topic name
            title: Notification title
            body: Notification body
            data: Additional data payload
            notification_type: Type of notification
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.is_available():
            logger.warning("Push notification service not available")
            return False
        
        try:
            # Prepare notification payload
            notification = messaging.Notification(
                title=title,
                body=body
            )
            
            # Prepare data payload
            data_payload = data or {}
            if notification_type:
                data_payload['notification_type'] = notification_type.value
            
            # Create topic message
            message = messaging.Message(
                notification=notification,
                data={k: str(v) for k, v in data_payload.items()},
                topic=topic
            )
            
            # Send message
            response = messaging.send(message)
            logger.info(f"Successfully sent topic notification to {topic}: {response}")
            return True
            
        except FirebaseError as e:
            logger.error(f"Firebase error sending topic notification: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending topic notification: {str(e)}")
            return False
    
    async def subscribe_to_topic(self, device_tokens: List[str], topic: str) -> Dict[str, Any]:
        """
        Subscribe device tokens to a topic.
        
        Args:
            device_tokens: List of FCM device tokens
            topic: Topic name to subscribe to
            
        Returns:
            Dict with success_count and failure_count
        """
        if not self.is_available():
            logger.warning("Push notification service not available")
            return {'success_count': 0, 'failure_count': len(device_tokens)}
        
        try:
            response = messaging.subscribe_to_topic(device_tokens, topic)
            logger.info(f"Topic subscription result for {topic}: Success: {response.success_count}, Failed: {response.failure_count}")
            return {
                'success_count': response.success_count,
                'failure_count': response.failure_count
            }
        except FirebaseError as e:
            logger.error(f"Firebase error subscribing to topic {topic}: {str(e)}")
            return {'success_count': 0, 'failure_count': len(device_tokens)}
        except Exception as e:
            logger.error(f"Unexpected error subscribing to topic {topic}: {str(e)}")
            return {'success_count': 0, 'failure_count': len(device_tokens)}
    
    async def unsubscribe_from_topic(self, device_tokens: List[str], topic: str) -> Dict[str, Any]:
        """
        Unsubscribe device tokens from a topic.
        
        Args:
            device_tokens: List of FCM device tokens
            topic: Topic name to unsubscribe from
            
        Returns:
            Dict with success_count and failure_count
        """
        if not self.is_available():
            logger.warning("Push notification service not available")
            return {'success_count': 0, 'failure_count': len(device_tokens)}
        
        try:
            response = messaging.unsubscribe_from_topic(device_tokens, topic)
            logger.info(f"Topic unsubscription result for {topic}: Success: {response.success_count}, Failed: {response.failure_count}")
            return {
                'success_count': response.success_count,
                'failure_count': response.failure_count
            }
        except FirebaseError as e:
            logger.error(f"Firebase error unsubscribing from topic {topic}: {str(e)}")
            return {'success_count': 0, 'failure_count': len(device_tokens)}
        except Exception as e:
            logger.error(f"Unexpected error unsubscribing from topic {topic}: {str(e)}")
            return {'success_count': 0, 'failure_count': len(device_tokens)}

# Global instance
push_service = PushNotificationService()