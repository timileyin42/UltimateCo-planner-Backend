import stripe
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.subscription_models import (
    UserSubscription, SubscriptionPlan, SubscriptionPayment, 
    SubscriptionStatus, PaymentStatus, BillingInterval, PlanType
)
from app.models.user_models import User
from app.core.errors import PlanEtalException
from app.core.circuit_breaker import stripe_circuit_breaker, stripe_fallback
from app.core.idempotency import IdempotencyManager, idempotent_operation
import logging

logger = logging.getLogger(__name__)

class StripeError(PlanEtalException):
    """Stripe-related errors."""
    pass

class StripeService:
    """Service for handling Stripe payments and subscriptions."""
    
    def __init__(self):
        """Initialize Stripe service with API key."""
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        
    @stripe_circuit_breaker(fallback=stripe_fallback)
    async def create_customer(self, user: User, idempotency_key: Optional[str] = None) -> str:
        """Create a Stripe customer for a user."""
        try:
            customer_params = {
                'email': user.email,
                'name': user.full_name,
                'metadata': {
                    'user_id': str(user.id),
                    'username': user.username or ''
                }
            }
            
            # Add idempotency key if provided
            if idempotency_key:
                customer_params['idempotency_key'] = idempotency_key
            
            customer = stripe.Customer.create(**customer_params)
            return customer.id
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer for user {user.id}: {e}")
            raise StripeError(f"Failed to create customer: {str(e)}")
    
    @stripe_circuit_breaker(fallback=stripe_fallback)
    @idempotent_operation(resource_type="subscription", expiry_hours=24)
    async def create_subscription(
        self, 
        db: Session,
        user: User, 
        plan: SubscriptionPlan,
        billing_interval: BillingInterval,
        payment_method_id: str,
        trial_days: Optional[int] = None,
        idempotency_key: Optional[str] = None
    ) -> UserSubscription:
        """Create a new subscription for a user."""
        try:
            # Get or create Stripe customer
            stripe_customer_id = await self._get_or_create_customer(user)
            
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=stripe_customer_id
            )
            
            # Set as default payment method
            stripe.Customer.modify(
                stripe_customer_id,
                invoice_settings={'default_payment_method': payment_method_id}
            )
            
            # Get the appropriate price ID
            price_id = (
                plan.stripe_price_id_yearly if billing_interval == BillingInterval.YEARLY 
                else plan.stripe_price_id_monthly
            )
            
            if not price_id:
                raise StripeError(f"No Stripe price ID configured for plan {plan.name}")
            
            # Create subscription
            subscription_params = {
                'customer': stripe_customer_id,
                'items': [{'price': price_id}],
                'payment_behavior': 'default_incomplete',
                'payment_settings': {'save_default_payment_method': 'on_subscription'},
                'expand': ['latest_invoice.payment_intent'],
                'metadata': {
                    'user_id': str(user.id),
                    'plan_id': str(plan.id)
                }
            }
            
            if trial_days:
                subscription_params['trial_period_days'] = trial_days
            
            # Add idempotency key if provided
            if idempotency_key:
                subscription_params['idempotency_key'] = idempotency_key
            
            stripe_subscription = stripe.Subscription.create(**subscription_params)
            
            # Create local subscription record
            user_subscription = UserSubscription(
                user_id=user.id,
                plan_id=plan.id,
                status=SubscriptionStatus.INCOMPLETE if not trial_days else SubscriptionStatus.TRIALING,
                billing_interval=billing_interval,
                stripe_subscription_id=stripe_subscription.id,
                stripe_customer_id=stripe_customer_id,
                start_date=datetime.utcnow(),
                current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end),
                trial_end_date=datetime.fromtimestamp(stripe_subscription.trial_end) if stripe_subscription.trial_end else None
            )
            
            db.add(user_subscription)
            db.commit()
            db.refresh(user_subscription)
            
            return user_subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create subscription for user {user.id}: {e}")
            db.rollback()
            raise StripeError(f"Failed to create subscription: {str(e)}")
    
    @stripe_circuit_breaker(fallback=stripe_fallback)
    async def cancel_subscription(self, db: Session, subscription: UserSubscription) -> UserSubscription:
        """Cancel a user's subscription."""
        try:
            if not subscription.stripe_subscription_id:
                raise StripeError("No Stripe subscription ID found")
            
            # Cancel at period end to allow user to use remaining time
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            subscription.status = SubscriptionStatus.CANCELED
            subscription.canceled_at = datetime.utcnow()
            
            db.commit()
            db.refresh(subscription)
            
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription {subscription.id}: {e}")
            raise StripeError(f"Failed to cancel subscription: {str(e)}")
    
    @stripe_circuit_breaker(fallback=stripe_fallback)
    async def reactivate_subscription(self, db: Session, subscription: UserSubscription) -> UserSubscription:
        """Reactivate a canceled subscription."""
        try:
            if not subscription.stripe_subscription_id:
                raise StripeError("No Stripe subscription ID found")
            
            # Remove the cancellation
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=False
            )
            
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.canceled_at = None
            
            db.commit()
            db.refresh(subscription)
            
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to reactivate subscription {subscription.id}: {e}")
            raise StripeError(f"Failed to reactivate subscription: {str(e)}")
    
    @stripe_circuit_breaker(fallback=stripe_fallback)
    async def update_payment_method(
        self, 
        subscription: UserSubscription, 
        payment_method_id: str
    ) -> bool:
        """Update the payment method for a subscription."""
        try:
            if not subscription.stripe_customer_id:
                raise StripeError("No Stripe customer ID found")
            
            # Attach new payment method
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=subscription.stripe_customer_id
            )
            
            # Set as default
            stripe.Customer.modify(
                subscription.stripe_customer_id,
                invoice_settings={'default_payment_method': payment_method_id}
            )
            
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to update payment method for subscription {subscription.id}: {e}")
            raise StripeError(f"Failed to update payment method: {str(e)}")
    
    @stripe_circuit_breaker(fallback=stripe_fallback)
    async def create_setup_intent(self, customer_id: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Create a setup intent for saving payment methods."""
        try:
            setup_intent_params = {
                'customer': customer_id,
                'payment_method_types': ['card'],
                'usage': 'off_session'
            }
            
            # Add idempotency key if provided
            if idempotency_key:
                setup_intent_params['idempotency_key'] = idempotency_key
            
            setup_intent = stripe.SetupIntent.create(**setup_intent_params)
            
            return {
                'client_secret': setup_intent.client_secret,
                'setup_intent_id': setup_intent.id
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create setup intent for customer {customer_id}: {e}")
            raise StripeError(f"Failed to create setup intent: {str(e)}")
    
    @stripe_circuit_breaker(fallback=stripe_fallback)
    async def get_payment_methods(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get all payment methods for a customer."""
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type='card'
            )
            
            return [
                {
                    'id': pm.id,
                    'brand': pm.card.brand,
                    'last4': pm.card.last4,
                    'exp_month': pm.card.exp_month,
                    'exp_year': pm.card.exp_year,
                    'is_default': False  # You'd need to check against customer's default
                }
                for pm in payment_methods.data
            ]
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get payment methods for customer {customer_id}: {e}")
            raise StripeError(f"Failed to get payment methods: {str(e)}")
    
    def verify_webhook_signature(self, payload: str, sig_header: str) -> tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Verify Stripe webhook signature and parse event.
        
        Returns:
            Tuple of (is_valid, event_dict, error_message)
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return True, event, None
            
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            return False, None, "Invalid payload"
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            return False, None, "Invalid signature"
        except Exception as e:
            logger.error(f"Error verifying webhook: {e}")
            return False, None, str(e)
    
    async def handle_webhook(self, payload: str, sig_header: str, db: Session) -> bool:
        """
        Handle Stripe webhook events (DEPRECATED - use webhook endpoint with Celery instead).
        
        This method is kept for backward compatibility but should not be used for new implementations.
        Use the /webhooks/stripe endpoint which queues events to Celery for processing.
        """
        logger.warning("Using deprecated handle_webhook method. Consider migrating to Celery-based webhook processing.")
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'invoice.payment_succeeded':
                await self._handle_payment_succeeded(event['data']['object'], db)
            elif event['type'] == 'invoice.payment_failed':
                await self._handle_payment_failed(event['data']['object'], db)
            elif event['type'] == 'customer.subscription.updated':
                await self._handle_subscription_updated(event['data']['object'], db)
            elif event['type'] == 'customer.subscription.deleted':
                await self._handle_subscription_deleted(event['data']['object'], db)
            
            return True
            
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            return False
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            return False
        except Exception as e:
            logger.error(f"Error handling webhook: {e}")
            return False
    
    async def _get_or_create_customer(self, user: User) -> str:
        """Get existing Stripe customer or create new one."""
        # First check if user already has a subscription with customer ID
        if hasattr(user, 'subscription') and user.subscription and user.subscription.stripe_customer_id:
            return user.subscription.stripe_customer_id
        
        # Create new customer
        return await self.create_customer(user)
    
    async def _handle_payment_succeeded(self, invoice: Dict[str, Any], db: Session):
        """Handle successful payment webhook."""
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return
        
        # Find local subscription
        subscription = db.query(UserSubscription).filter(
            UserSubscription.stripe_subscription_id == subscription_id
        ).first()
        
        if not subscription:
            logger.warning(f"Subscription not found for Stripe ID: {subscription_id}")
            return
        
        # Create payment record
        payment = SubscriptionPayment(
            subscription_id=subscription.id,
            amount=invoice['amount_paid'] / 100,  # Convert from cents
            currency=invoice['currency'].upper(),
            status=PaymentStatus.SUCCEEDED,
            stripe_payment_intent_id=invoice.get('payment_intent'),
            stripe_invoice_id=invoice['id'],
            billing_reason=invoice.get('billing_reason'),
            paid_at=datetime.fromtimestamp(invoice['status_transitions']['paid_at'])
        )
        
        db.add(payment)
        
        # Update subscription status
        if subscription.status != SubscriptionStatus.ACTIVE:
            subscription.status = SubscriptionStatus.ACTIVE
        
        db.commit()
    
    async def _handle_payment_failed(self, invoice: Dict[str, Any], db: Session):
        """Handle failed payment webhook."""
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return
        
        subscription = db.query(UserSubscription).filter(
            UserSubscription.stripe_subscription_id == subscription_id
        ).first()
        
        if not subscription:
            return
        
        # Create failed payment record
        payment = SubscriptionPayment(
            subscription_id=subscription.id,
            amount=invoice['amount_due'] / 100,
            currency=invoice['currency'].upper(),
            status=PaymentStatus.FAILED,
            stripe_invoice_id=invoice['id'],
            billing_reason=invoice.get('billing_reason'),
            failed_at=datetime.utcnow(),
            failure_code=invoice.get('last_finalization_error', {}).get('code'),
            failure_message=invoice.get('last_finalization_error', {}).get('message')
        )
        
        db.add(payment)
        
        # Update subscription status
        subscription.status = SubscriptionStatus.PAST_DUE
        
        db.commit()
    
    async def _handle_subscription_updated(self, subscription_data: Dict[str, Any], db: Session):
        """Handle subscription update webhook."""
        subscription = db.query(UserSubscription).filter(
            UserSubscription.stripe_subscription_id == subscription_data['id']
        ).first()
        
        if not subscription:
            return
        
        # Update subscription details
        subscription.current_period_start = datetime.fromtimestamp(subscription_data['current_period_start'])
        subscription.current_period_end = datetime.fromtimestamp(subscription_data['current_period_end'])
        
        # Map Stripe status to our status
        stripe_status = subscription_data['status']
        status_mapping = {
            'active': SubscriptionStatus.ACTIVE,
            'past_due': SubscriptionStatus.PAST_DUE,
            'canceled': SubscriptionStatus.CANCELED,
            'incomplete': SubscriptionStatus.INCOMPLETE,
            'incomplete_expired': SubscriptionStatus.INCOMPLETE_EXPIRED,
            'trialing': SubscriptionStatus.TRIALING,
            'unpaid': SubscriptionStatus.UNPAID
        }
        
        subscription.status = status_mapping.get(stripe_status, SubscriptionStatus.INACTIVE)
        
        db.commit()
    
    async def _handle_subscription_deleted(self, subscription_data: Dict[str, Any], db: Session):
        """Handle subscription deletion webhook."""
        subscription = db.query(UserSubscription).filter(
            UserSubscription.stripe_subscription_id == subscription_data['id']
        ).first()
        
        if not subscription:
            return
        
        subscription.status = SubscriptionStatus.CANCELED
        subscription.canceled_at = datetime.utcnow()
        subscription.end_date = datetime.utcnow()
        
        db.commit()