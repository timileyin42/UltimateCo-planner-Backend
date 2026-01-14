"""
Paystack Payment API Endpoints
Handles payment initialization, verification, and webhook events from Paystack.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Header, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import json

from app.core.deps import get_db, get_current_user
from app.models.user_models import User
from app.services.paystack_service import paystack_service
from app.services.subscription_service import SubscriptionService
from app.tasks.paystack_tasks import process_paystack_event_task
from app.models.subscription_models import BillingInterval
from pydantic import BaseModel, EmailStr
from app.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/paystack", tags=["paystack", "payments"])


class InitializePaymentRequest(BaseModel):
    """Request model for initializing payment."""
    email: EmailStr
    amount: float
    currency: Optional[str] = "USD"  # USD or GBP
    plan_id: Optional[int] = None
    billing_interval: Optional[BillingInterval] = None
    metadata: Optional[Dict[str, Any]] = None


class InitializePaymentResponse(BaseModel):
    """Response model for payment initialization."""
    authorization_url: str
    access_code: str
    reference: str


class VerifyPaymentResponse(BaseModel):
    """Response model for payment verification."""
    status: str
    reference: str
    amount: float
    currency: str
    paid_at: Optional[str] = None
    customer_email: str


class CreateSubscriptionRequest(BaseModel):
    """Request model for creating subscription."""
    plan_id: int
    billing_interval: BillingInterval
    authorization_code: str
    customer_code: Optional[str] = None


@router.post("/initialize", response_model=InitializePaymentResponse)
async def initialize_payment(
    request: InitializePaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initialize a Paystack payment transaction.
    
    This endpoint creates a payment transaction on Paystack and returns
    an authorization URL where the user will complete the payment.
    """
    try:
        # Add user_id to metadata
        metadata = request.metadata or {}
        metadata["user_id"] = current_user.id
        metadata["email"] = current_user.email
        
        # If plan_id provided, add to metadata
        if request.plan_id:
            metadata["plan_id"] = request.plan_id
            metadata["billing_interval"] = request.billing_interval.value if request.billing_interval else None
        
        # Validate currency
        currency = (request.currency or "USD").upper()
        if currency not in ["USD", "GBP"]:
            raise HTTPException(status_code=400, detail="Currency must be USD or GBP")
        
        # Initialize transaction with Paystack
        result = await paystack_service.initialize_transaction(
            email=request.email or current_user.email,
            amount=request.amount,
            currency=currency,
            metadata=metadata
        )
        
        return InitializePaymentResponse(
            authorization_url=result["authorization_url"],
            access_code=result["access_code"],
            reference=result["reference"]
        )
    
    except Exception as e:
        logger.error(f"Failed to initialize payment: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Payment initialization failed: {str(e)}")


@router.get("/verify/{reference}", response_model=VerifyPaymentResponse)
async def verify_payment(
    reference: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify a Paystack payment transaction.
    
    After user completes payment, call this endpoint to verify the transaction
    and get payment details.
    """
    try:
        # Verify transaction with Paystack
        transaction = await paystack_service.verify_transaction(reference)
        
        return VerifyPaymentResponse(
            status=transaction["status"],
            reference=transaction["reference"],
            amount=transaction["amount"] / 100,  # Convert from kobo to naira
            currency=transaction["currency"],
            paid_at=transaction.get("paid_at"),
            customer_email=transaction["customer"]["email"]
        )
    
    except Exception as e:
        logger.error(f"Failed to verify payment: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Payment verification failed: {str(e)}")


@router.post("/subscribe")
async def create_subscription(
    request: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a subscription after successful payment.
    
    After user completes payment and you have the authorization_code,
    call this endpoint to create the subscription.
    """
    try:
        subscription_service = SubscriptionService()
        
        # Create subscription
        subscription = await subscription_service.create_subscription(
            db=db,
            user=current_user,
            plan_id=request.plan_id,
            billing_interval=request.billing_interval,
            authorization_code=request.authorization_code,
            customer_code=request.customer_code
        )
        
        return {
            "status": "success",
            "message": "Subscription created successfully",
            "subscription_id": subscription.id,
            "plan": subscription.plan.name,
            "billing_interval": subscription.billing_interval.value,
            "status": subscription.status.value,
            "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None
        }
    
    except Exception as e:
        logger.error(f"Failed to create subscription: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cancel-subscription")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel user's active subscription.
    """
    try:
        subscription_service = SubscriptionService()
        
        subscription = await subscription_service.cancel_subscription(
            db=db,
            user_id=current_user.id
        )
        
        return {
            "status": "success",
            "message": "Subscription canceled successfully",
            "subscription_id": subscription.id,
            "canceled_at": subscription.canceled_at.isoformat() if subscription.canceled_at else None
        }
    
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def paystack_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_paystack_signature: Optional[str] = Header(None)
):
    """
    Webhook endpoint for Paystack events.
    
    Paystack will send webhook events to this endpoint.
    Events are processed asynchronously using Celery.
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Verify webhook signature
        if x_paystack_signature:
            is_valid = paystack_service.verify_webhook_signature(
                payload=body,
                signature=x_paystack_signature
            )
            
            if not is_valid:
                logger.warning("Invalid Paystack webhook signature")
                raise HTTPException(status_code=401, detail="Invalid signature")
        else:
            logger.warning("No webhook signature provided")
        
        # Parse event data
        event_data = json.loads(body)
        event_type = event_data.get("event")
        event_id = event_data.get("id") or event_data.get("data", {}).get("reference")
        
        if not event_id:
            logger.warning("Webhook event has no ID")
            return {"status": "error", "message": "No event ID"}
        
        # Process event asynchronously
        background_tasks.add_task(
            process_paystack_event_task.delay,
            event_id=event_id,
            event_type=event_type,
            event_data=event_data
        )
        
        logger.info(f"Paystack webhook event {event_id} queued for processing")
        
        return {"status": "success", "message": "Event received"}
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook payload")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.get("/callback")
async def payment_callback(
    reference: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Payment callback endpoint.
    
    Users are redirected here after completing payment on Paystack.
    This endpoint verifies the payment and returns the result.
    """
    try:
        # Verify the payment
        transaction = await paystack_service.verify_transaction(reference)
        
        if transaction["status"] == "success":
            return {
                "status": "success",
                "message": "Payment successful",
                "reference": reference,
                "amount": transaction["amount"] / 100,
                "currency": transaction["currency"]
            }
        else:
            return {
                "status": "failed",
                "message": "Payment was not successful",
                "reference": reference
            }
    
    except Exception as e:
        logger.error(f"Payment callback error: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to process payment callback")
