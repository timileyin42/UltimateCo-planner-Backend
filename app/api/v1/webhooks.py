"""
Webhook endpoints for external service integrations.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Request, Header, HTTPException, Response
from starlette.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_500_INTERNAL_SERVER_ERROR

from app.services.stripe_service import StripeService
from app.tasks.payments import process_stripe_event_task

logger = logging.getLogger(__name__)

router = APIRouter()
stripe_service = StripeService()


@router.post(
    "/stripe",
    status_code=HTTP_200_OK,
    summary="Stripe Webhook Endpoint",
    description="Receives webhook events from Stripe and queues them for processing"
)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature")
):
    """
    Handle Stripe webhook events.
    
    This endpoint:
    1. Verifies the Stripe signature
    2. Validates the payload
    3. Enqueues the event to Celery for asynchronous processing
    4. Returns 200 immediately to acknowledge receipt
    
    The actual processing happens in the background via Celery workers.
    """
    if not stripe_signature:
        logger.error("Missing Stripe signature header")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Missing stripe-signature header"
        )
    
    # Get raw body
    try:
        payload = await request.body()
        payload_str = payload.decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to read request body: {str(e)}")
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Invalid request body"
        )
    
    # Verify signature and parse event
    is_valid, event, error_message = stripe_service.verify_webhook_signature(
        payload_str, 
        stripe_signature
    )
    
    if not is_valid:
        logger.error(f"Webhook signature verification failed: {error_message}")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail=error_message or "Invalid signature"
        )
    
    # Extract event details
    event_id = event.get("id")
    event_type = event.get("type")
    event_data = event.get("data", {}).get("object", {})
    metadata = event_data.get("metadata", {}) or {}
    
    logger.info(f"Received Stripe webhook event: {event_id} of type {event_type}")
    
    # Enqueue the event for background processing
    try:
        # Use delay() to enqueue asynchronously
        task = process_stripe_event_task.delay(
            stripe_event_id=event_id,
            event_type=event_type,
            event_data=event_data,
            metadata=metadata
        )
        
        logger.info(f"Enqueued Stripe event {event_id} for processing. Task ID: {task.id}")
        
    except Exception as e:
        logger.error(f"Failed to enqueue Stripe event {event_id}: {str(e)}")
        # Return 500 so Stripe will retry
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue event for processing"
        )
    
    # Acknowledge receipt immediately
    return Response(
        content='{"status": "received"}',
        status_code=HTTP_200_OK,
        media_type="application/json"
    )


@router.get(
    "/stripe",
    summary="Stripe Webhook Health Check",
    description="Health check endpoint for Stripe webhook"
)
async def stripe_webhook_health():
    """Health check endpoint for Stripe webhook."""
    return {
        "status": "healthy",
        "service": "stripe_webhook",
        "message": "Webhook endpoint is ready to receive events"
    }
