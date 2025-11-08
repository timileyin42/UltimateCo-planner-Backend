from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy import true
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.deps import get_db, get_current_active_user
from app.core.errors import http_400_bad_request, http_404_not_found, http_403_forbidden
from app.services.notification_service import NotificationService
from app.services.email_service import email_service
from app.services.sms_service import sms_service
from app.services.push_service import push_service
from app.models.user_models import User
from app.models.notification_models import NotificationType, NotificationChannel, AutomationRule, NotificationLog, NotificationQueue
from app.services.websocket_manager import websocket_manager
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from app.schemas.notification import (
    # Smart Reminder schemas
    SmartReminderCreate, SmartReminderUpdate, SmartReminderResponse, ReminderListResponse,
    
    # Notification Preference schemas
    NotificationPreferenceCreate, NotificationPreferenceResponse, BulkPreferenceUpdate,
    
    # Template schemas
    ReminderTemplateCreate, ReminderTemplateUpdate, ReminderTemplateResponse, TemplateListResponse,
    
    # Analytics and logs
    NotificationAnalytics, NotificationLogResponse, NotificationLogListResponse,
    
    # Automation and testing
    AutomationRuleCreate, AutomationRuleUpdate, AutomationRuleResponse,
    TestNotificationRequest, NotificationQueueStatus,
    
    # Search and bulk operations
    ReminderSearchParams, BulkReminderCreate,
    
    # In-app notifications and device management
    InAppNotificationResponse, InAppNotificationListResponse, MarkNotificationReadRequest,
    DeviceRegistrationRequest, DeviceResponse, WebSocketStatsResponse
)

notifications_router = APIRouter()

# Smart Reminder endpoints
@notifications_router.post("/events/{event_id}/reminders", response_model=SmartReminderResponse)
async def create_reminder(
    event_id: int,
    reminder_data: SmartReminderCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new smart reminder for an event"""
    try:
        notification_service = NotificationService(db)
        reminder = notification_service.create_reminder(
            event_id, current_user.id, reminder_data.model_dump()
        )
        
        return SmartReminderResponse.model_validate(reminder)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower() or "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to create reminder")

@notifications_router.get("/events/{event_id}/reminders", response_model=List[SmartReminderResponse])
async def get_event_reminders(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all reminders for an event"""
    try:
        notification_service = NotificationService(db)
        reminders = notification_service.get_event_reminders(event_id, current_user.id)
        
        return [SmartReminderResponse.model_validate(reminder) for reminder in reminders]
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get reminders")

@notifications_router.put("/reminders/{reminder_id}", response_model=SmartReminderResponse)
async def update_reminder(
    reminder_id: int,
    update_data: SmartReminderUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a smart reminder"""
    try:
        notification_service = NotificationService(db)
        reminder = notification_service.update_reminder(
            reminder_id, current_user.id, update_data.model_dump(exclude_unset=True)
        )
        
        return SmartReminderResponse.model_validate(reminder)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to update reminder")

@notifications_router.delete("/reminders/{reminder_id}")
async def delete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a smart reminder"""
    try:
        notification_service = NotificationService(db)
        success = notification_service.delete_reminder(reminder_id, current_user.id)
        
        return {"message": "Reminder deleted successfully", "success": success}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to delete reminder")

# Automatic reminder creation
@notifications_router.post("/events/{event_id}/auto-reminders", response_model=List[SmartReminderResponse])
async def create_automatic_reminders(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create automatic reminders for an event"""
    try:
        notification_service = NotificationService(db)
        reminders = notification_service.create_automatic_reminders(event_id)
        
        return [SmartReminderResponse.model_validate(reminder) for reminder in reminders]
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request("Failed to create automatic reminders")

# Notification preferences
@notifications_router.get("/preferences", response_model=List[NotificationPreferenceResponse])
async def get_notification_preferences(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's notification preferences"""
    try:
        notification_service = NotificationService(db)
        preferences = notification_service.get_user_preferences(current_user.id)
        
        return [NotificationPreferenceResponse.model_validate(pref) for pref in preferences]
        
    except Exception as e:
        raise http_400_bad_request("Failed to get notification preferences")

@notifications_router.put("/preferences", response_model=List[NotificationPreferenceResponse])
async def update_notification_preferences(
    preferences_data: BulkPreferenceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update user's notification preferences"""
    try:
        notification_service = NotificationService(db)
        preferences = notification_service.update_user_preferences(
            current_user.id, [pref.model_dump() for pref in preferences_data.preferences]
        )
        
        return [NotificationPreferenceResponse.model_validate(pref) for pref in preferences]
        
    except Exception as e:
        raise http_400_bad_request("Failed to update notification preferences")

# Reminder templates
@notifications_router.post("/templates", response_model=ReminderTemplateResponse)
async def create_reminder_template(
    template_data: ReminderTemplateCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a reminder template"""
    try:
        notification_service = NotificationService(db)
        template = notification_service.create_reminder_template(
            current_user.id, template_data.model_dump()
        )
        
        return ReminderTemplateResponse.model_validate(template)
        
    except Exception as e:
        raise http_400_bad_request("Failed to create reminder template")

@notifications_router.get("/templates", response_model=List[ReminderTemplateResponse])
async def get_reminder_templates(
    notification_type: Optional[NotificationType] = Query(None, description="Filter by notification type"),
    include_system: bool = Query(True, description="Include system templates"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get reminder templates"""
    try:
        notification_service = NotificationService(db)
        user_id = current_user.id if not include_system else None
        templates = notification_service.get_reminder_templates(user_id, notification_type)
        
        return [ReminderTemplateResponse.model_validate(template) for template in templates]
        
    except Exception as e:
        raise http_400_bad_request("Failed to get reminder templates")

# Notification processing
@notifications_router.post("/process-queue")
async def process_notification_queue(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Process pending notifications (admin only)"""
    try:
        # Check if user is admin (you might want to add proper admin check)
        notification_service = NotificationService(db)
        
        # Add background task to process notifications
        background_tasks.add_task(notification_service.process_pending_notifications)
        
        return {"message": "Notification processing started", "status": "queued"}
        
    except Exception as e:
        raise http_400_bad_request("Failed to start notification processing")

@notifications_router.get("/queue-status", response_model=NotificationQueueStatus)
async def get_queue_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get notification queue status"""
    try:
        
        # Get queue statistics
        queued_count = db.query(NotificationQueue).filter(
            NotificationQueue.status == "queued"
        ).count()
        
        processing_count = db.query(NotificationQueue).filter(
            NotificationQueue.status == "processing"
        ).count()
        
        sent_count = db.query(NotificationQueue).filter(
            NotificationQueue.status == "sent"
        ).count()
        
        failed_count = db.query(NotificationQueue).filter(
            NotificationQueue.status == "failed"
        ).count()
        
        # Get next scheduled notification
        next_notification = db.query(NotificationQueue).filter(
            NotificationQueue.status == "queued"
        ).order_by(NotificationQueue.scheduled_for).first()
        
        # Get last processed notification
        last_processed = db.query(NotificationQueue).filter(
            NotificationQueue.status.in_(["sent", "failed"])
        ).order_by(NotificationQueue.last_attempt_at.desc()).first()
        
        return NotificationQueueStatus(
            queued_count=queued_count,
            processing_count=processing_count,
            sent_count=sent_count,
            failed_count=failed_count,
            next_scheduled=next_notification.scheduled_for if next_notification else None,
            last_processed=last_processed.last_attempt_at if last_processed else None
        )
        
    except Exception as e:
        raise http_400_bad_request("Failed to get queue status")

# Analytics
@notifications_router.get("/analytics", response_model=NotificationAnalytics)
async def get_notification_analytics(
    event_id: Optional[int] = Query(None, description="Filter by event ID"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get notification analytics"""
    try:
        notification_service = NotificationService(db)
        analytics = notification_service.get_notification_analytics(
            event_id=event_id,
            user_id=current_user.id,
            days=days
        )
        
        return NotificationAnalytics(**analytics)
        
    except Exception as e:
        raise http_400_bad_request("Failed to get notification analytics")

@notifications_router.get("/logs", response_model=NotificationLogListResponse)
async def get_notification_logs(
    event_id: Optional[int] = Query(None, description="Filter by event ID"),
    notification_type: Optional[NotificationType] = Query(None, description="Filter by type"),
    channel: Optional[NotificationChannel] = Query(None, description="Filter by channel"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get notification logs"""
    try:
        
        # Build query
        query = db.query(NotificationLog).options(
            joinedload(NotificationLog.recipient)
        ).filter(
            NotificationLog.recipient_id == current_user.id
        )
        
        if event_id:
            query = query.filter(NotificationLog.event_id == event_id)
        
        if notification_type:
            query = query.filter(NotificationLog.notification_type == notification_type)
        
        if channel:
            query = query.filter(NotificationLog.channel == channel)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        logs = query.order_by(NotificationLog.sent_at.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        
        log_responses = [NotificationLogResponse.model_validate(log) for log in logs]
        
        return NotificationLogListResponse(
            logs=log_responses,
            total=total,
            page=page,
            per_page=per_page,
            has_next=(page * per_page) < total,
            has_prev=page > 1
        )
        
    except Exception as e:
        raise http_400_bad_request("Failed to get notification logs")

# Test notifications
@notifications_router.post("/test")
async def send_test_notification(
    test_request: TestNotificationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Send a test notification"""
    try:
        notification_service = NotificationService(db)
        
        # Create a test notification queue item
        
        test_notification = NotificationQueue(
            notification_type=test_request.notification_type,
            channel=test_request.channel,
            subject=test_request.subject,
            message=test_request.message,
            scheduled_for=datetime.utcnow(),
            event_id=1,  # Dummy event ID for test
            recipient_id=current_user.id,
            priority=1
        )
        
        # Send immediately
        success = await notification_service._send_notification(test_notification)
        
        return {
            "message": "Test notification sent" if success else "Test notification failed",
            "success": success,
            "channel": test_request.channel.value,
            "recipient": test_request.recipient_email
        }
        
    except Exception as e:
        raise http_400_bad_request(f"Failed to send test notification: {str(e)}")

# Bulk operations
@notifications_router.post("/events/{event_id}/bulk-reminders", response_model=List[SmartReminderResponse])
async def bulk_create_reminders(
    event_id: int,
    bulk_data: BulkReminderCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Bulk create reminders for an event"""
    try:
        notification_service = NotificationService(db)
        created_reminders = []
        
        for reminder_data in bulk_data.reminders:
            reminder = notification_service.create_reminder(
                event_id, current_user.id, reminder_data.model_dump()
            )
            created_reminders.append(SmartReminderResponse.model_validate(reminder))
        
        return created_reminders
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to bulk create reminders")

# Automation rules (advanced feature)
@notifications_router.post("/automation-rules", response_model=AutomationRuleResponse)
async def create_automation_rule(
    rule_data: AutomationRuleCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create an automation rule for automatic reminder creation"""
    try:
        
        rule = AutomationRule(
            name=rule_data.name,
            description=rule_data.description,
            trigger_event=rule_data.trigger_event,
            trigger_conditions=rule_data.trigger_conditions,
            notification_type=rule_data.notification_type,
            template_id=rule_data.template_id,
            delay_hours=rule_data.delay_hours,
            advance_hours=rule_data.advance_hours,
            is_active=rule_data.is_active,
            apply_to_all_events=rule_data.apply_to_all_events,
            creator_id=current_user.id
        )
        
        db.add(rule)
        db.commit()
        db.refresh(rule)
        
        return AutomationRuleResponse.model_validate(rule)
        
    except Exception as e:
        raise http_400_bad_request("Failed to create automation rule")

@notifications_router.get("/automation-rules", response_model=List[AutomationRuleResponse])
async def get_automation_rules(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get automation rules for the current user"""
    try:
        
        rules = db.query(AutomationRule).options(
            joinedload(AutomationRule.creator),
            joinedload(AutomationRule.template)
        ).filter(
            AutomationRule.creator_id == current_user.id,
            AutomationRule.is_active == True
        ).all()
        
        return [AutomationRuleResponse.model_validate(rule) for rule in rules]
        
    except Exception as e:
        raise http_400_bad_request("Failed to get automation rules")

# Notification channels management
@notifications_router.get("/channels")
async def get_notification_channels(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get available notification channels and their status"""
    try:
        # Check actual service availability
        
        # Check email service status
        email_available = email_service.is_configured()
        
        # Check SMS service status
        sms_available = sms_service.is_configured()
        
        # Check push service status
        push_available = push_service.is_configured()
        
        # In-app notifications are always available via WebSocket
        in_app_available = True
        
        # Get user's device count for push notifications
        user_devices_count = 0
        if push_available:
            try:
                devices = push_service.get_user_devices(current_user.id)
                user_devices_count = len(devices)
            except:
                user_devices_count = 0
        
        # Get WebSocket connection status
        websocket_connected = websocket_manager.is_user_connected(current_user.id)
        
        return {
            "channels": [
                {
                    "id": "email",
                    "name": "Email",
                    "description": "Send notifications via email",
                    "available": email_available,
                    "configured": email_available,
                    "user_configured": bool(current_user.email),
                    "details": {
                        "user_email": current_user.email if current_user.email else None,
                        "service_status": "configured" if email_available else "not_configured"
                    }
                },
                {
                    "id": "sms",
                    "name": "SMS",
                    "description": "Send notifications via SMS",
                    "available": sms_available,
                    "configured": sms_available,
                    "user_configured": bool(getattr(current_user, 'phone_number', None)),
                    "details": {
                        "user_phone": getattr(current_user, 'phone_number', None),
                        "service_status": "configured" if sms_available else "not_configured"
                    }
                },
                {
                    "id": "push",
                    "name": "Push Notifications",
                    "description": "Send push notifications to mobile devices",
                    "available": push_available,
                    "configured": push_available,
                    "user_configured": user_devices_count > 0,
                    "details": {
                        "registered_devices": user_devices_count,
                        "service_status": "configured" if push_available else "not_configured"
                    }
                },
                {
                    "id": "in_app",
                    "name": "In-App Notifications",
                    "description": "Real-time notifications within the application",
                    "available": in_app_available,
                    "configured": in_app_available,
                    "user_configured": True,
                    "details": {
                        "websocket_connected": websocket_connected,
                        "service_status": "configured"
                    }
                }
            ],
            "summary": {
                "total_channels": 4,
                "available_channels": sum([email_available, sms_available, push_available, in_app_available]),
                "user_configured_channels": sum([
                    bool(current_user.email) and email_available,
                    bool(getattr(current_user, 'phone_number', None)) and sms_available,
                    user_devices_count > 0 and push_available,
                    in_app_available
                ])
            }
        }
        
    except Exception as e:
        raise http_400_bad_request(f"Failed to get notification channels: {str(e)}")

# In-App Notifications endpoints
@notifications_router.get("/in-app", response_model=InAppNotificationListResponse)
async def get_in_app_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    unread_only: bool = Query(False, description="Show only unread notifications"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get in-app notifications for the current user"""
    try:
        
        # Build query for user's notifications
        query = db.query(NotificationLog).filter(
            NotificationLog.recipient_id == current_user.id,
            NotificationLog.channel == NotificationChannel.IN_APP
        )
        
        if unread_only:
            query = query.filter(NotificationLog.read_at.is_(None))
        
        # Get total count
        total = query.count()
        
        # Get unread count
        unread_count = db.query(NotificationLog).filter(
            NotificationLog.recipient_id == current_user.id,
            NotificationLog.channel == NotificationChannel.IN_APP,
            NotificationLog.read_at.is_(None)
        ).count()
        
        # Apply pagination and ordering
        notifications = query.order_by(NotificationLog.sent_at.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        
        # Convert to response format
        notification_responses = []
        for notif in notifications:
            notification_responses.append(InAppNotificationResponse(
                id=notif.id,
                type="notification",
                title=notif.subject or "Notification",
                message=notif.message,
                notification_type=notif.notification_type.value,
                event_id=notif.event_id,
                timestamp=notif.sent_at,
                priority=getattr(notif, 'priority', 5),
                read=notif.read_at is not None
            ))
        
        return InAppNotificationListResponse(
            notifications=notification_responses,
            total=total,
            page=page,
            per_page=per_page,
            has_next=(page * per_page) < total,
            has_prev=page > 1,
            unread_count=unread_count
        )
        
    except Exception as e:
        raise http_400_bad_request(f"Failed to get in-app notifications: {str(e)}")

@notifications_router.post("/in-app/mark-read")
async def mark_notifications_read(
    request: MarkNotificationReadRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Mark in-app notifications as read"""
    try:
        
        # Update notifications to mark as read
        updated_count = db.query(NotificationLog).filter(
            NotificationLog.id.in_(request.notification_ids),
            NotificationLog.recipient_id == current_user.id,
            NotificationLog.channel == NotificationChannel.IN_APP,
            NotificationLog.read_at.is_(None)
        ).update({
            NotificationLog.read_at: datetime.utcnow()
        }, synchronize_session=False)
        
        db.commit()
        
        return {
            "message": f"Marked {updated_count} notifications as read",
            "updated_count": updated_count
        }
        
    except Exception as e:
        db.rollback()
        raise http_400_bad_request(f"Failed to mark notifications as read: {str(e)}")

# Device Management endpoints
@notifications_router.post("/devices/register", response_model=DeviceResponse)
async def register_device(
    device_data: DeviceRegistrationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Register a device for push notifications"""
    try:
        
        device = push_service.register_device(
            user_id=current_user.id,
            device_token=device_data.device_token,
            device_type=device_data.device_type,
            device_name=device_data.device_name,
            app_version=device_data.app_version
        )
        
        return DeviceResponse.model_validate(device)
        
    except Exception as e:
        raise http_400_bad_request(f"Failed to register device: {str(e)}")

@notifications_router.get("/devices", response_model=List[DeviceResponse])
async def get_user_devices(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all registered devices for the current user"""
    try:        
        devices = push_service.get_user_devices(current_user.id)
        
        return [DeviceResponse.model_validate(device) for device in devices]
        
    except Exception as e:
        raise http_400_bad_request(f"Failed to get user devices: {str(e)}")

@notifications_router.delete("/devices/{device_id}")
async def unregister_device(
    device_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Unregister a device"""
    try:        
        success = push_service.unregister_device(device_id, current_user.id)
        
        if not success:
            raise http_404_not_found("Device not found or not owned by user")
        
        return {"message": "Device unregistered successfully"}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request(f"Failed to unregister device: {str(e)}")

# WebSocket Statistics endpoint
@notifications_router.get("/websocket/stats", response_model=WebSocketStatsResponse)
async def get_websocket_stats(
    current_user: User = Depends(get_current_active_user)
):
    """Get WebSocket connection statistics"""
    try:
        stats = websocket_manager.get_connection_stats()
        
        return WebSocketStatsResponse(
            total_connections=stats.get("total_connections", 0),
            active_connections=stats.get("active_connections", 0),
            connections_by_user=stats.get("connections_by_user", {}),
            total_messages_sent=stats.get("total_messages_sent", 0),
            uptime_seconds=stats.get("uptime_seconds", 0)
        )
        
    except Exception as e:
        raise http_400_bad_request(f"Failed to get WebSocket stats: {str(e)}")

# Notification types information
@notifications_router.get("/types")
async def get_notification_types(
    current_user: User = Depends(get_current_active_user)
):
    """Get available notification types with descriptions"""
    return {
        "types": [
            {
                "name": "rsvp_reminder",
                "display_name": "RSVP Reminder",
                "description": "Remind guests to respond to event invitations",
                "icon": "✉️",
                "default_advance_hours": 168  # 7 days
            },
            {
                "name": "payment_reminder",
                "display_name": "Payment Reminder",
                "description": "Remind about outstanding payments or contributions",
                "icon": "💳",
                "default_advance_hours": 72  # 3 days
            },
            {
                "name": "dress_code_reminder",
                "display_name": "Dress Code Reminder",
                "description": "Remind guests about event dress code",
                "icon": "👔",
                "default_advance_hours": 72  # 3 days
            },
            {
                "name": "event_reminder",
                "display_name": "Event Reminder",
                "description": "Remind about upcoming events",
                "icon": "📅",
                "default_advance_hours": 24  # 1 day
            },
            {
                "name": "task_reminder",
                "display_name": "Task Reminder",
                "description": "Remind about assigned tasks and deadlines",
                "icon": "✅",
                "default_advance_hours": 48  # 2 days
            },
            {
                "name": "timeline_reminder",
                "display_name": "Timeline Reminder",
                "description": "Remind about timeline items and schedule",
                "icon": "⏰",
                "default_advance_hours": 2  # 2 hours
            },
            {
                "name": "weather_alert",
                "display_name": "Weather Alert",
                "description": "Alert about weather conditions affecting events",
                "icon": "🌤️",
                "default_advance_hours": 24  # 1 day
            },
            {
                "name": "budget_alert",
                "display_name": "Budget Alert",
                "description": "Alert about budget limits and overspending",
                "icon": "💰",
                "default_advance_hours": 0  # Immediate
            },
            {
                "name": "custom",
                "display_name": "Custom Notification",
                "description": "Custom notifications for specific needs",
                "icon": "📢",
                "default_advance_hours": 24  # 1 day
            }
        ]
    }