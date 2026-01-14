"""
Celery tasks for processing payment webhook events.
DEPRECATED: Stripe tasks kept for backward compatibility.
Use paystack_tasks.py for new Paystack payment processing.
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime
from celery import Task
import redis
import stripe

from app.tasks.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.subscription_models import (
    StripeEventLog, UserSubscription, SubscriptionPayment,
    SubscriptionStatus, PaymentStatus
)
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Initialize Redis client for pub/sub
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


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
def process_stripe_event_task(self, stripe_event_id: str, event_type: str, event_data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None):
    """
    Process Stripe webhook event in background.
    
    Args:
        stripe_event_id: Unique Stripe event ID
        event_type: Type of Stripe event (e.g., 'invoice.payment_succeeded')
        event_data: The event data object from Stripe
        metadata: Additional metadata from the event
    
    Returns:
        Dict with processing status
    """
    db = self.db
    
    try:
        # Check idempotency - skip if already processed
        existing_log = db.query(StripeEventLog).filter_by(event_id=stripe_event_id).first()
        
        if existing_log:
            if existing_log.processing_status == "completed":
                logger.info(f"Stripe event {stripe_event_id} already processed successfully")
                return {"status": "skipped", "reason": "already_processed"}
            elif existing_log.processing_status == "processing":
                logger.warning(f"Stripe event {stripe_event_id} is currently being processed")
                return {"status": "skipped", "reason": "already_processing"}
            else:
                # Update retry count for failed events
                existing_log.retry_count += 1
                existing_log.processing_status = "processing"
                db.commit()
                event_log = existing_log
        else:
            # Create new event log
            event_log = StripeEventLog(
                event_id=stripe_event_id,
                event_type=event_type,
                processing_status="processing",
                metadata=json.dumps(metadata) if metadata else None
            )
            db.add(event_log)
            db.commit()
            db.refresh(event_log)
        
        logger.info(f"Processing Stripe event {stripe_event_id} of type {event_type}")
        
        # Route to appropriate handler based on event type
        result = None
        user_id = None
        
        if event_type == "invoice.payment_succeeded":
            result, user_id = handle_payment_succeeded(db, event_data)
        elif event_type == "invoice.payment_failed":
            result, user_id = handle_payment_failed(db, event_data)
        elif event_type == "customer.subscription.updated":
            result, user_id = handle_subscription_updated(db, event_data)
        elif event_type == "customer.subscription.deleted":
            result, user_id = handle_subscription_deleted(db, event_data)
        elif event_type == "customer.subscription.created":
            result, user_id = handle_subscription_created(db, event_data)
        else:
            logger.info(f"Unhandled event type: {event_type}")
            result = {"status": "ignored", "reason": "unhandled_event_type"}
        
        # Mark event as completed
        event_log.processing_status = "completed"
        event_log.processed_at = datetime.utcnow()
        event_log.error_message = None
        db.commit()
        
        logger.info(f"Successfully processed Stripe event {stripe_event_id}")
        
        # Broadcast completion to WebSocket clients via Redis pub/sub
        if user_id and result:
            broadcast_payment_update(user_id, {
                "event": "payment_processed",
                "event_type": event_type,
                "stripe_event_id": stripe_event_id,
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        return {"status": "completed", "result": result}
        
    except Exception as exc:
        db.rollback()
        logger.exception(f"Error processing Stripe event {stripe_event_id}: {str(exc)}")
        
        # Update event log with error
        try:
            event_log = db.query(StripeEventLog).filter_by(event_id=stripe_event_id).first()
            if event_log:
                event_log.processing_status = "failed"
                event_log.error_message = str(exc)
                event_log.retry_count += 1
                db.commit()
        except Exception as log_error:
            logger.error(f"Failed to update event log: {str(log_error)}")
        
        # Retry the task
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for Stripe event {stripe_event_id}")
            return {"status": "failed", "error": str(exc), "max_retries_exceeded": True}


def handle_payment_succeeded(db, invoice_data: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[int]]:
    """Handle successful payment webhook."""
    subscription_id = invoice_data.get("subscription")
    if not subscription_id:
        logger.warning("No subscription ID in payment succeeded event")
        return {"status": "ignored", "reason": "no_subscription_id"}, None
    
    # Find local subscription
    subscription = db.query(UserSubscription).filter(
        UserSubscription.stripe_subscription_id == subscription_id
    ).first()
    
    if not subscription:
        logger.warning(f"Subscription not found for Stripe ID: {subscription_id}")
        return {"status": "error", "reason": "subscription_not_found"}, None
    
    # Create payment record
    payment = SubscriptionPayment(
        subscription_id=subscription.id,
        amount=invoice_data["amount_paid"] / 100,  # Convert from cents
        currency=invoice_data["currency"].upper(),
        status=PaymentStatus.SUCCEEDED,
        stripe_payment_intent_id=invoice_data.get("payment_intent"),
        stripe_invoice_id=invoice_data["id"],
        billing_reason=invoice_data.get("billing_reason"),
        paid_at=datetime.fromtimestamp(invoice_data["status_transitions"]["paid_at"]) if invoice_data.get("status_transitions", {}).get("paid_at") else datetime.utcnow()
    )
    
    db.add(payment)
    
    # Update subscription status
    old_status = subscription.status
    if subscription.status != SubscriptionStatus.ACTIVE:
        subscription.status = SubscriptionStatus.ACTIVE
    
    db.commit()
    
    logger.info(f"Payment succeeded for subscription {subscription.id}, user {subscription.user_id}")
    
    return {
        "status": "success",
        "payment_id": payment.id,
        "amount": payment.amount,
        "subscription_id": subscription.id,
        "subscription_status": subscription.status.value,
        "status_changed": old_status != subscription.status
    }, subscription.user_id


def handle_payment_failed(db, invoice_data: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[int]]:
    """Handle failed payment webhook."""
    subscription_id = invoice_data.get("subscription")
    if not subscription_id:
        return {"status": "ignored", "reason": "no_subscription_id"}, None
    
    subscription = db.query(UserSubscription).filter(
        UserSubscription.stripe_subscription_id == subscription_id
    ).first()
    
    if not subscription:
        return {"status": "error", "reason": "subscription_not_found"}, None
    
    # Create failed payment record
    payment = SubscriptionPayment(
        subscription_id=subscription.id,
        amount=invoice_data["amount_due"] / 100,
        currency=invoice_data["currency"].upper(),
        status=PaymentStatus.FAILED,
        stripe_invoice_id=invoice_data["id"],
        billing_reason=invoice_data.get("billing_reason"),
        failed_at=datetime.utcnow(),
        failure_code=invoice_data.get("last_finalization_error", {}).get("code"),
        failure_message=invoice_data.get("last_finalization_error", {}).get("message")
    )
    
    db.add(payment)
    
    # Update subscription status
    old_status = subscription.status
    subscription.status = SubscriptionStatus.PAST_DUE
    
    db.commit()
    
    logger.warning(f"Payment failed for subscription {subscription.id}, user {subscription.user_id}")
    
    return {
        "status": "payment_failed",
        "payment_id": payment.id,
        "subscription_id": subscription.id,
        "subscription_status": subscription.status.value,
        "failure_reason": payment.failure_message
    }, subscription.user_id


def handle_subscription_updated(db, subscription_data: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[int]]:
    """Handle subscription update webhook."""
    subscription = db.query(UserSubscription).filter(
        UserSubscription.stripe_subscription_id == subscription_data["id"]
    ).first()
    
    if not subscription:
        return {"status": "error", "reason": "subscription_not_found"}, None
    
    # Update subscription details
    old_status = subscription.status
    subscription.current_period_start = datetime.fromtimestamp(subscription_data["current_period_start"])
    subscription.current_period_end = datetime.fromtimestamp(subscription_data["current_period_end"])
    
    # Map Stripe status to our status
    stripe_status = subscription_data["status"]
    status_mapping = {
        "active": SubscriptionStatus.ACTIVE,
        "past_due": SubscriptionStatus.PAST_DUE,
        "canceled": SubscriptionStatus.CANCELED,
        "incomplete": SubscriptionStatus.INCOMPLETE,
        "incomplete_expired": SubscriptionStatus.INCOMPLETE_EXPIRED,
        "trialing": SubscriptionStatus.TRIALING,
        "unpaid": SubscriptionStatus.UNPAID
    }
    
    subscription.status = status_mapping.get(stripe_status, SubscriptionStatus.INACTIVE)
    
    db.commit()
    
    logger.info(f"Subscription {subscription.id} updated for user {subscription.user_id}")
    
    return {
        "status": "updated",
        "subscription_id": subscription.id,
        "new_status": subscription.status.value,
        "status_changed": old_status != subscription.status,
        "current_period_end": subscription.current_period_end.isoformat()
    }, subscription.user_id


def handle_subscription_deleted(db, subscription_data: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[int]]:
    """Handle subscription deletion webhook."""
    subscription = db.query(UserSubscription).filter(
        UserSubscription.stripe_subscription_id == subscription_data["id"]
    ).first()
    
    if not subscription:
        return {"status": "error", "reason": "subscription_not_found"}, None
    
    subscription.status = SubscriptionStatus.CANCELED
    subscription.canceled_at = datetime.utcnow()
    subscription.end_date = datetime.utcnow()
    
    db.commit()
    
    logger.info(f"Subscription {subscription.id} canceled for user {subscription.user_id}")
    
    return {
        "status": "canceled",
        "subscription_id": subscription.id,
        "canceled_at": subscription.canceled_at.isoformat()
    }, subscription.user_id


def handle_subscription_created(db, subscription_data: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[int]]:
    """Handle subscription creation webhook (for subscriptions created outside our system)."""
    # Check if subscription already exists
    subscription = db.query(UserSubscription).filter(
        UserSubscription.stripe_subscription_id == subscription_data["id"]
    ).first()
    
    if subscription:
        logger.info(f"Subscription {subscription_data['id']} already exists in system")
        return {"status": "already_exists", "subscription_id": subscription.id}, subscription.user_id
    
    logger.info(f"Subscription {subscription_data['id']} created externally, not in our system yet")
    return {"status": "external_creation", "stripe_subscription_id": subscription_data["id"]}, None


def broadcast_payment_update(user_id: int, update_data: Dict[str, Any]):
    """
    Broadcast payment update to user's WebSocket connections via Redis pub/sub.
    
    Args:
        user_id: User ID to send update to
        update_data: Update data to broadcast
    """
    try:
        channel = f"user:{user_id}:payments"
        message = json.dumps(update_data)
        redis_client.publish(channel, message)
        logger.info(f"Broadcasted payment update to channel {channel}")
    except Exception as e:
        logger.error(f"Failed to broadcast payment update to Redis: {str(e)}")
