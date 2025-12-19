"""
Paystack Payment Service
Handles all Paystack API interactions for payment processing and subscriptions.
"""
import hashlib
import hmac
import httpx
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.subscription_models import (
    SubscriptionPlan, UserSubscription, SubscriptionPayment, PaystackEventLog,
    SubscriptionStatus, PaymentStatus, BillingInterval
)
from app.core.errors import PaymentError
import logging

logger = logging.getLogger(__name__)


class PaystackService:
    """Service for handling Paystack payment operations."""
    
    BASE_URL = "https://api.paystack.co"
    
    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.public_key = settings.PAYSTACK_PUBLIC_KEY
        self.webhook_secret = settings.PAYSTACK_WEBHOOK_SECRET
        
        if not self.secret_key:
            raise ValueError("PAYSTACK_SECRET_KEY is not configured")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Paystack API requests."""
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
    
    async def initialize_transaction(
        self,
        email: str,
        amount: float,
        plan_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        currency: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initialize a Paystack transaction.
        
        Args:
            email: Customer email
            amount: Amount in major currency unit (dollars/pounds)
            plan_id: Optional Paystack plan code for subscriptions
            metadata: Optional metadata to attach to transaction
            currency: Currency code (USD or GBP). Defaults to config setting.
        
        Returns:
            Dict with authorization_url, access_code, and reference
        """
        try:
            # Validate and set currency
            payment_currency = (currency or settings.PAYSTACK_CURRENCY).upper()
            if payment_currency not in settings.PAYSTACK_SUPPORTED_CURRENCIES:
                raise PaymentError(f"Currency {payment_currency} not supported. Use USD or GBP.")
            
            async with httpx.AsyncClient() as client:
                payload = {
                    "email": email,
                    "amount": int(amount * 100),  # Convert to cents/pence
                    "currency": payment_currency,
                    "callback_url": settings.PAYSTACK_CALLBACK_URL,
                }
                
                if plan_id:
                    payload["plan"] = plan_id
                
                if metadata:
                    payload["metadata"] = metadata
                
                response = await client.post(
                    f"{self.BASE_URL}/transaction/initialize",
                    json=payload,
                    headers=self._get_headers(),
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                if data.get("status"):
                    return data["data"]
                else:
                    raise PaymentError(f"Paystack initialization failed: {data.get('message')}")
        
        except httpx.HTTPError as e:
            logger.error(f"Paystack API error: {str(e)}")
            raise PaymentError(f"Failed to initialize payment: {str(e)}")
    
    async def verify_transaction(self, reference: str) -> Dict[str, Any]:
        """
        Verify a Paystack transaction.
        
        Args:
            reference: Transaction reference
        
        Returns:
            Transaction data
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/transaction/verify/{reference}",
                    headers=self._get_headers(),
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                if data.get("status"):
                    return data["data"]
                else:
                    raise PaymentError(f"Transaction verification failed: {data.get('message')}")
        
        except httpx.HTTPError as e:
            logger.error(f"Paystack verification error: {str(e)}")
            raise PaymentError(f"Failed to verify transaction: {str(e)}")
    
    async def create_subscription(
        self,
        customer_code: str,
        plan_code: str,
        authorization_code: str
    ) -> Dict[str, Any]:
        """
        Create a subscription on Paystack.
        
        Args:
            customer_code: Paystack customer code
            plan_code: Paystack plan code
            authorization_code: Payment authorization code
        
        Returns:
            Subscription data
        """
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "customer": customer_code,
                    "plan": plan_code,
                    "authorization": authorization_code
                }
                
                response = await client.post(
                    f"{self.BASE_URL}/subscription",
                    json=payload,
                    headers=self._get_headers(),
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                if data.get("status"):
                    return data["data"]
                else:
                    raise PaymentError(f"Subscription creation failed: {data.get('message')}")
        
        except httpx.HTTPError as e:
            logger.error(f"Paystack subscription error: {str(e)}")
            raise PaymentError(f"Failed to create subscription: {str(e)}")
    
    async def cancel_subscription(self, subscription_code: str, email_token: str) -> bool:
        """
        Cancel a Paystack subscription.
        
        Args:
            subscription_code: Subscription code
            email_token: Email token for verification
        
        Returns:
            True if successful
        """
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "code": subscription_code,
                    "token": email_token
                }
                
                response = await client.post(
                    f"{self.BASE_URL}/subscription/disable",
                    json=payload,
                    headers=self._get_headers(),
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                return data.get("status", False)
        
        except httpx.HTTPError as e:
            logger.error(f"Paystack cancel subscription error: {str(e)}")
            raise PaymentError(f"Failed to cancel subscription: {str(e)}")
    
    async def fetch_subscription(self, subscription_code: str) -> Dict[str, Any]:
        """
        Fetch subscription details from Paystack.
        
        Args:
            subscription_code: Subscription code
        
        Returns:
            Subscription data
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/subscription/{subscription_code}",
                    headers=self._get_headers(),
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                if data.get("status"):
                    return data["data"]
                else:
                    raise PaymentError(f"Fetch subscription failed: {data.get('message')}")
        
        except httpx.HTTPError as e:
            logger.error(f"Paystack fetch subscription error: {str(e)}")
            raise PaymentError(f"Failed to fetch subscription: {str(e)}")
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Paystack webhook signature.
        
        Args:
            payload: Raw request body
            signature: X-Paystack-Signature header value
        
        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured, skipping signature verification")
            return True
        
        computed_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, signature)
    
    def process_webhook_event(
        self,
        db: Session,
        event_data: Dict[str, Any]
    ) -> None:
        """
        Process Paystack webhook event.
        
        Args:
            db: Database session
            event_data: Webhook event data
        """
        event_type = event_data.get("event")
        event_id = event_data.get("id") or event_data.get("data", {}).get("reference")
        
        if not event_id:
            logger.warning("Webhook event has no ID, skipping")
            return
        
        # Check if event already processed (idempotency)
        existing_log = db.query(PaystackEventLog).filter(
            PaystackEventLog.event_id == event_id
        ).first()
        
        if existing_log and existing_log.processing_status == "completed":
            logger.info(f"Event {event_id} already processed, skipping")
            return
        
        # Create or update event log
        if not existing_log:
            existing_log = PaystackEventLog(
                event_id=event_id,
                event_type=event_type,
                processing_status="processing",
                event_metadata=str(event_data)
            )
            db.add(existing_log)
            db.commit()
        else:
            existing_log.processing_status = "processing"
            existing_log.retry_count += 1
            db.commit()
        
        try:
            # Process different event types
            if event_type == "charge.success":
                self._handle_charge_success(db, event_data.get("data", {}))
            elif event_type == "subscription.create":
                self._handle_subscription_create(db, event_data.get("data", {}))
            elif event_type == "subscription.disable":
                self._handle_subscription_disable(db, event_data.get("data", {}))
            elif event_type == "subscription.not_renew":
                self._handle_subscription_not_renew(db, event_data.get("data", {}))
            else:
                logger.info(f"Unhandled event type: {event_type}")
            
            # Mark as completed
            existing_log.processing_status = "completed"
            existing_log.processed_at = datetime.utcnow()
            db.commit()
        
        except Exception as e:
            logger.error(f"Error processing webhook event {event_id}: {str(e)}")
            existing_log.processing_status = "failed"
            existing_log.error_message = str(e)
            db.commit()
            raise
    
    def _handle_charge_success(self, db: Session, data: Dict[str, Any]) -> None:
        """Handle successful charge event."""
        reference = data.get("reference")
        if not reference:
            return
        
        # Find payment record
        payment = db.query(SubscriptionPayment).filter(
            SubscriptionPayment.paystack_reference == reference
        ).first()
        
        if payment:
            payment.status = PaymentStatus.SUCCEEDED
            payment.paid_at = datetime.utcnow()
            payment.paystack_authorization_code = data.get("authorization", {}).get("authorization_code")
            db.commit()
            logger.info(f"Payment {reference} marked as succeeded")
    
    def _handle_subscription_create(self, db: Session, data: Dict[str, Any]) -> None:
        """Handle subscription creation event."""
        subscription_code = data.get("subscription_code")
        customer_code = data.get("customer", {}).get("customer_code")
        
        if not subscription_code:
            return
        
        # Find subscription by customer code
        subscription = db.query(UserSubscription).filter(
            UserSubscription.paystack_customer_code == customer_code
        ).first()
        
        if subscription:
            subscription.paystack_subscription_code = subscription_code
            subscription.status = SubscriptionStatus.ACTIVE
            db.commit()
            logger.info(f"Subscription {subscription_code} activated")
    
    def _handle_subscription_disable(self, db: Session, data: Dict[str, Any]) -> None:
        """Handle subscription disable event."""
        subscription_code = data.get("subscription_code")
        
        if not subscription_code:
            return
        
        subscription = db.query(UserSubscription).filter(
            UserSubscription.paystack_subscription_code == subscription_code
        ).first()
        
        if subscription:
            subscription.status = SubscriptionStatus.CANCELED
            subscription.canceled_at = datetime.utcnow()
            db.commit()
            logger.info(f"Subscription {subscription_code} canceled")
    
    def _handle_subscription_not_renew(self, db: Session, data: Dict[str, Any]) -> None:
        """Handle subscription not renewing event."""
        subscription_code = data.get("subscription_code")
        
        if not subscription_code:
            return
        
        subscription = db.query(UserSubscription).filter(
            UserSubscription.paystack_subscription_code == subscription_code
        ).first()
        
        if subscription:
            subscription.status = SubscriptionStatus.CANCELED
            db.commit()
            logger.info(f"Subscription {subscription_code} will not renew")


# Global instance
paystack_service = PaystackService()
