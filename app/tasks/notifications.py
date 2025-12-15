"""
Celery task for processing due notifications from the queue.
Runs periodically via Celery Beat to deliver reminders on time.
"""
import asyncio
from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.notification_service import NotificationService


@celery_app.task(name="app.tasks.notifications.process_due_notifications")
def process_due_notifications(limit: int = 100):
    """Process queued notifications that are due to be sent."""
    db = SessionLocal()
    try:
        service = NotificationService(db)
        # process_pending_notifications is async; run it in this sync task
        processed = asyncio.run(service.process_pending_notifications(limit=limit))
        return {"processed": processed}
    finally:
        db.close()
