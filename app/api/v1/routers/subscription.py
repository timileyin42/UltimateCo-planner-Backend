from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional
from app.core.deps import get_db, get_current_active_user
from app.core.errors import http_400_bad_request, http_404_not_found, http_403_forbidden
from app.core.rate_limiter import create_rate_limit_decorator, RateLimitConfig
from app.services.subscription_service import SubscriptionService, SubscriptionError
from app.services.stripe_service import StripeService
from app.schemas.subscription_schemas import (
    SubscriptionPlan, UserSubscription, SubscriptionPayment, UsageLimit,
    SubscriptionCreate, UpdatePaymentMethodRequest, CancelSubscriptionRequest,
    UpgradeSubscriptionRequest
)
from app.models.user_models import User
import stripe
import logging

logger = logging.getLogger(__name__)

subscription_router = APIRouter()

# Rate limiting decorators for subscription endpoints
rate_limit_subscription = create_rate_limit_decorator(RateLimitConfig.SUBSCRIPTION_MANAGE)
rate_limit_payment = create_rate_limit_decorator(RateLimitConfig.PAYMENT_CREATE)

@subscription_router.get("/plans", response_model=list[SubscriptionPlan])
async def get_subscription_plans(
    db: Session = Depends(get_db)
):
    """Get all available subscription plans"""
    try:
        subscription_service = SubscriptionService(db)
        plans = subscription_service.get_all_plans()
        return plans
    except Exception as e:
        logger.error(f"Error fetching subscription plans: {e}")
        raise http_400_bad_request("Failed to fetch subscription plans")

@subscription_router.get("/current", response_model=UserSubscription)
async def get_current_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's subscription details"""
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.get_user_subscription(current_user.id)
        return subscription
    except Exception as e:
        logger.error(f"Error fetching user subscription: {e}")
        raise http_400_bad_request("Failed to fetch subscription details")

@subscription_router.get("/usage", response_model=UsageLimit)
async def get_usage_limits(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's usage limits and remaining quota"""
    try:
        subscription_service = SubscriptionService(db)
        usage = subscription_service.get_usage_limits(current_user.id)
        return usage
    except Exception as e:
        logger.error(f"Error fetching usage limits: {e}")
        raise http_400_bad_request("Failed to fetch usage limits")

@subscription_router.post("/subscribe", response_model=UserSubscription)
@rate_limit_subscription
async def create_subscription(
    request: Request,
    subscription_data: SubscriptionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new subscription for the user"""
    try:
        subscription_service = SubscriptionService(db)
        stripe_service = StripeService()
        
        # Create Stripe customer if not exists
        if not current_user.stripe_customer_id:
            customer = stripe_service.create_customer(
                email=current_user.email,
                name=f"{current_user.first_name} {current_user.last_name}",
                user_id=current_user.id
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
        
        # Create subscription
        subscription = subscription_service.create_subscription(
            user_id=current_user.id,
            plan_id=subscription_data.plan_id,
            payment_method_id=subscription_data.payment_method_id
        )
        
        return subscription
    except SubscriptionError as e:
        raise http_400_bad_request(str(e))
    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        raise http_400_bad_request("Failed to create subscription")

@subscription_router.post("/cancel")
@rate_limit_subscription
async def cancel_subscription(
    request: Request,
    cancel_data: CancelSubscriptionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Cancel user's current subscription"""
    try:
        subscription_service = SubscriptionService(db)
        subscription_service.cancel_subscription(
            user_id=current_user.id,
            cancel_at_period_end=cancel_data.cancel_at_period_end
        )
        return {"message": "Subscription cancelled successfully"}
    except SubscriptionError as e:
        raise http_400_bad_request(str(e))
    except Exception as e:
        logger.error(f"Error cancelling subscription: {e}")
        raise http_400_bad_request("Failed to cancel subscription")

@subscription_router.post("/reactivate", response_model=UserSubscription)
@rate_limit_subscription
async def reactivate_subscription(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Reactivate a cancelled subscription"""
    try:
        subscription_service = SubscriptionService(db)
        subscription = subscription_service.reactivate_subscription(
            user_id=current_user.id
        )
        return subscription
    except SubscriptionError as e:
        raise http_400_bad_request(str(e))
    except Exception as e:
        logger.error(f"Error reactivating subscription: {e}")
        raise http_400_bad_request("Failed to reactivate subscription")

@subscription_router.put("/payment-method")
@rate_limit_payment
async def update_payment_method(
    request: Request,
    payment_data: UpdatePaymentMethodRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update user's payment method"""
    try:
        subscription_service = SubscriptionService(db)
        subscription_service.update_payment_method(
            user_id=current_user.id,
            payment_method_id=payment_data.payment_method_id
        )
        return {"message": "Payment method updated successfully"}
    except SubscriptionError as e:
        raise http_400_bad_request(str(e))
    except Exception as e:
        logger.error(f"Error updating payment method: {e}")
        raise http_400_bad_request("Failed to update payment method")

@subscription_router.post("/setup-intent")
@rate_limit_payment
async def create_setup_intent(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a setup intent for payment method collection"""
    try:
        stripe_service = StripeService()
        
        # Ensure user has Stripe customer ID
        if not current_user.stripe_customer_id:
            customer = stripe_service.create_customer(
                email=current_user.email,
                name=f"{current_user.first_name} {current_user.last_name}",
                user_id=current_user.id
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
        
        setup_intent = stripe_service.create_setup_intent(current_user.stripe_customer_id)
        return {"client_secret": setup_intent.client_secret}
    except Exception as e:
        logger.error(f"Error creating setup intent: {e}")
        raise http_400_bad_request("Failed to create setup intent")

@subscription_router.get("/payment-methods")
async def get_payment_methods(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's saved payment methods"""
    try:
        if not current_user.stripe_customer_id:
            return {"payment_methods": []}
        
        stripe_service = StripeService()
        payment_methods = stripe_service.get_payment_methods(current_user.stripe_customer_id)
        return {"payment_methods": payment_methods}
    except Exception as e:
        logger.error(f"Error fetching payment methods: {e}")
        raise http_400_bad_request("Failed to fetch payment methods")

@subscription_router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Stripe webhooks"""
    try:
        stripe_service = StripeService()
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')
        
        event = stripe_service.handle_webhook(payload, sig_header)
        
        subscription_service = SubscriptionService(db)
        
        if event['type'] == 'invoice.payment_succeeded':
            # Handle successful payment
            subscription_service.handle_payment_success(event['data']['object'])
        elif event['type'] == 'invoice.payment_failed':
            # Handle failed payment
            subscription_service.handle_payment_failure(event['data']['object'])
        elif event['type'] == 'customer.subscription.deleted':
            # Handle subscription cancellation
            subscription_service.handle_subscription_cancelled(event['data']['object'])
        elif event['type'] == 'customer.subscription.updated':
            # Handle subscription updates
            subscription_service.handle_subscription_updated(event['data']['object'])
        
        return {"status": "success"}
    except stripe.error.SignatureVerificationError:
        raise http_400_bad_request("Invalid signature")
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        raise http_400_bad_request("Webhook handling failed")