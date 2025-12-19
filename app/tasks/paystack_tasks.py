"""
Celery tasks for processing Paystack webhook events.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from celery import Task

from app.tasks.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.paystack_service import paystack_service
from app.models.subscription_models import PaystackEventLog

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task that provides database session management."""
    _db = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def process_paystack_event_task(
    self, 
    event_id: str, 
    event_type: str, 
    event_data: Dict[str, Any]
):
    """
    Process Paystack webhook event in background.
    
    Args:
        event_id: Unique Paystack event ID
        event_type: Type of Paystack event (e.g., 'charge.success', 'subscription.create')
        event_data: The complete event data object from Paystack
    
    Returns:
        Dict with processing status
    """
    db = self.db
    
    try:
        # Check idempotency - skip if already processed
        existing_log = db.query(PaystackEventLog).filter_by(event_id=event_id).first()
        
        if existing_log:
            if existing_log.processing_status == "completed":
                logger.info(f"Paystack event {event_id} already processed successfully")
                return {"status": "skipped", "reason": "already_processed"}
            elif existing_log.processing_status == "processing":
                logger.warning(f"Paystack event {event_id} is currently being processed")
                return {"status": "skipped", "reason": "already_processing"}
            else:
                # Update retry count for failed events
                existing_log.retry_count += 1
                existing_log.processing_status = "processing"
                db.commit()
                event_log = existing_log
        else:
            # Create new event log
            event_log = PaystackEventLog(
                event_id=event_id,
                event_type=event_type,
                processing_status="processing",
                event_metadata=json.dumps(event_data)
            )
            db.add(event_log)
            db.commit()
            db.refresh(event_log)
        
        logger.info(f"Processing Paystack event {event_id} of type {event_type}")
        
        # Process the event using PaystackService
        paystack_service.process_webhook_event(db, event_data)
        
        # Mark as completed
        event_log.processing_status = "completed"
        event_log.processed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Successfully processed Paystack event {event_id}")
        
        return {
            "status": "success",
            "event_id": event_id,
            "event_type": event_type,
            "processed_at": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error processing Paystack event {event_id}: {str(e)}", exc_info=True)
        
        # Update event log with error
        if 'event_log' in locals():
            event_log.processing_status = "failed"
            event_log.error_message = str(e)
            db.commit()
        
        # Re-raise for Celery retry mechanism
        raise


@celery_app.task(bind=True, base=DatabaseTask)
def sync_paystack_subscription_status(self, subscription_code: str):
    """
    Sync subscription status from Paystack.
    
    Args:
        subscription_code: Paystack subscription code
    """
    db = self.db
    
    try:
        from app.models.subscription_models import UserSubscription, SubscriptionStatus
        
        # Fetch subscription details from Paystack
        paystack_subscription = paystack_service.fetch_subscription(subscription_code)
        
        # Find local subscription
        subscription = db.query(UserSubscription).filter(
            UserSubscription.paystack_subscription_code == subscription_code
        ).first()
        
        if not subscription:
            logger.warning(f"Local subscription not found for Paystack code {subscription_code}")
            return {"status": "not_found"}
        
        # Update status based on Paystack status
        paystack_status = paystack_subscription.get("status")
        if paystack_status == "active":
            subscription.status = SubscriptionStatus.ACTIVE
        elif paystack_status == "non-renewing":
            subscription.status = SubscriptionStatus.CANCELED
        elif paystack_status == "cancelled":
            subscription.status = SubscriptionStatus.CANCELED
            subscription.canceled_at = datetime.utcnow()
        elif paystack_status == "attention":
            subscription.status = SubscriptionStatus.PAST_DUE
        
        db.commit()
        
        logger.info(f"Synced subscription {subscription_code} status to {subscription.status}")
        
        return {
            "status": "success",
            "subscription_code": subscription_code,
            "local_status": subscription.status.value
        }
    
    except Exception as e:
        logger.error(f"Error syncing subscription {subscription_code}: {str(e)}", exc_info=True)
        raise


@celery_app.task(bind=True, base=DatabaseTask)
def verify_pending_payments(self):
    """
    Verify pending payments with Paystack.
    This task runs periodically to check status of pending payments.
    """
    db = self.db
    
    try:
        from app.models.subscription_models import SubscriptionPayment, PaymentStatus
        
        # Get all pending payments from last 24 hours
        pending_payments = db.query(SubscriptionPayment).filter(
            SubscriptionPayment.status == PaymentStatus.PENDING,
            SubscriptionPayment.paystack_reference.isnot(None),
            SubscriptionPayment.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).all()
        
        verified_count = 0
        
        for payment in pending_payments:
            try:
                # Verify with Paystack
                transaction = paystack_service.verify_transaction(payment.paystack_reference)
                
                if transaction.get("status") == "success":
                    payment.status = PaymentStatus.SUCCEEDED
                    payment.paid_at = datetime.utcnow()
                    verified_count += 1
                elif transaction.get("status") == "failed":
                    payment.status = PaymentStatus.FAILED
                    payment.failed_at = datetime.utcnow()
                    payment.failure_message = transaction.get("gateway_response")
                
                db.commit()
                
            except Exception as e:
                logger.error(f"Error verifying payment {payment.id}: {str(e)}")
                continue
        
        logger.info(f"Verified {verified_count} pending payments")
        
        return {
            "status": "success",
            "verified_count": verified_count,
            "total_pending": len(pending_payments)
        }
    
    except Exception as e:
        logger.error(f"Error in verify_pending_payments task: {str(e)}", exc_info=True)
        raise
