from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.subscription_models import (
    UserSubscription, SubscriptionPlan, UsageLimit, SubscriptionPayment,
    SubscriptionStatus, PlanType, BillingInterval
)
from app.models.user_models import User
from app.models.event_models import Event
from app.services.stripe_service import StripeService
from app.core.errors import PlanEtalException
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class SubscriptionError(PlanEtalException):
    """Subscription-related errors."""
    pass

class UsageLimitExceededError(SubscriptionError):
    """Raised when user exceeds their plan limits."""
    pass

class SubscriptionService:
    """Service for managing subscriptions and usage limits."""
    
    def __init__(self):
        self.stripe_service = StripeService()
    
    async def get_user_subscription(self, db: Session, user_id: int) -> Optional[UserSubscription]:
        """Get user's current subscription."""
        return db.query(UserSubscription).filter(
            and_(
                UserSubscription.user_id == user_id,
                UserSubscription.deleted_at.is_(None)
            )
        ).first()
    
    async def get_available_plans(self, db: Session) -> List[SubscriptionPlan]:
        """Get all available subscription plans."""
        return db.query(SubscriptionPlan).filter(
            SubscriptionPlan.is_active == True
        ).order_by(SubscriptionPlan.price_monthly).all()
    
    async def create_subscription(
        self,
        db: Session,
        user: User,
        plan_id: int,
        billing_interval: BillingInterval,
        payment_method_id: str,
        trial_days: Optional[int] = None
    ) -> UserSubscription:
        """Create a new subscription for a user."""
        # Check if user already has an active subscription
        existing_subscription = await self.get_user_subscription(db, user.id)
        if existing_subscription and existing_subscription.is_active:
            raise SubscriptionError("User already has an active subscription")
        
        # Get the plan
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if not plan:
            raise SubscriptionError("Subscription plan not found")
        
        # Create subscription via Stripe
        subscription = await self.stripe_service.create_subscription(
            db, user, plan, billing_interval, payment_method_id, trial_days
        )
        
        # Initialize usage limits
        await self._initialize_usage_limits(db, user.id, plan)
        
        return subscription
    
    async def cancel_subscription(self, db: Session, user_id: int) -> UserSubscription:
        """Cancel user's subscription."""
        subscription = await self.get_user_subscription(db, user_id)
        if not subscription:
            raise SubscriptionError("No active subscription found")
        
        return await self.stripe_service.cancel_subscription(db, subscription)
    
    async def reactivate_subscription(self, db: Session, user_id: int) -> UserSubscription:
        """Reactivate a canceled subscription."""
        subscription = await self.get_user_subscription(db, user_id)
        if not subscription:
            raise SubscriptionError("No subscription found")
        
        if subscription.status != SubscriptionStatus.CANCELED:
            raise SubscriptionError("Subscription is not canceled")
        
        return await self.stripe_service.reactivate_subscription(db, subscription)
    
    async def upgrade_subscription(
        self,
        db: Session,
        user_id: int,
        new_plan_id: int,
        billing_interval: Optional[BillingInterval] = None
    ) -> UserSubscription:
        """Upgrade user's subscription to a higher plan."""
        current_subscription = await self.get_user_subscription(db, user_id)
        if not current_subscription:
            raise SubscriptionError("No active subscription found")
        
        new_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == new_plan_id).first()
        if not new_plan:
            raise SubscriptionError("New subscription plan not found")
        
        # TODO: Implement plan upgrade logic with Stripe
        # This would involve prorating the current subscription and switching to new plan
        raise NotImplementedError("Subscription upgrades not yet implemented")
    
    async def check_event_creation_limit(self, db: Session, user_id: int) -> bool:
        """Check if user can create more events."""
        subscription = await self.get_user_subscription(db, user_id)
        
        # If no subscription, user is on free plan
        if not subscription:
            return await self._check_free_plan_limits(db, user_id)
        
        # Check plan limits
        if subscription.plan.max_events is None:  # Unlimited
            return True
        
        # Get current usage
        usage = await self._get_or_create_usage_limit(db, user_id, subscription.plan)
        
        return usage.events_created < subscription.plan.max_events
    
    async def increment_event_usage(self, db: Session, user_id: int) -> None:
        """Increment user's event usage counter."""
        subscription = await self.get_user_subscription(db, user_id)
        
        if not subscription:
            # Handle free plan usage
            await self._increment_free_plan_usage(db, user_id)
            return
        
        usage = await self._get_or_create_usage_limit(db, user_id, subscription.plan)
        usage.events_created += 1
        
        # Check if limit exceeded
        if (subscription.plan.max_events is not None and 
            usage.events_created > subscription.plan.max_events):
            usage.events_exceeded = True
        
        db.commit()
    
    async def get_usage_summary(self, db: Session, user_id: int) -> Dict[str, Any]:
        """Get user's current usage summary."""
        subscription = await self.get_user_subscription(db, user_id)
        
        if not subscription:
            # Free plan usage
            free_plan_usage = await self._get_free_plan_usage(db, user_id)
            return {
                'plan_name': 'Free',
                'plan_type': PlanType.FREE,
                'events_created': free_plan_usage,
                'events_limit': settings.FREE_PLAN_EVENT_LIMIT,
                'events_remaining': max(0, settings.FREE_PLAN_EVENT_LIMIT - free_plan_usage),
                'is_unlimited': False,
                'subscription_status': None,
                'billing_interval': None,
                'next_billing_date': None
            }
        
        usage = await self._get_or_create_usage_limit(db, user_id, subscription.plan)
        
        return {
            'plan_name': subscription.plan.name,
            'plan_type': subscription.plan.plan_type,
            'events_created': usage.events_created,
            'events_limit': subscription.plan.max_events,
            'events_remaining': usage.events_remaining,
            'is_unlimited': subscription.plan.max_events is None,
            'subscription_status': subscription.status,
            'billing_interval': subscription.billing_interval,
            'next_billing_date': subscription.current_period_end,
            'storage_used_gb': usage.storage_used_gb,
            'storage_limit_gb': subscription.plan.max_storage_gb,
            'features': {
                'ai_suggestions': subscription.plan.ai_suggestions,
                'advanced_analytics': subscription.plan.advanced_analytics,
                'custom_branding': subscription.plan.custom_branding,
                'priority_support': subscription.plan.priority_support,
                'api_access': subscription.plan.api_access
            }
        }
    
    async def get_billing_history(self, db: Session, user_id: int) -> List[Dict[str, Any]]:
        """Get user's billing history."""
        subscription = await self.get_user_subscription(db, user_id)
        if not subscription:
            return []
        
        payments = db.query(SubscriptionPayment).filter(
            SubscriptionPayment.subscription_id == subscription.id
        ).order_by(SubscriptionPayment.created_at.desc()).all()
        
        return [
            {
                'id': payment.id,
                'amount': payment.amount,
                'currency': payment.currency,
                'status': payment.status,
                'billing_reason': payment.billing_reason,
                'paid_at': payment.paid_at,
                'created_at': payment.created_at,
                'stripe_invoice_id': payment.stripe_invoice_id
            }
            for payment in payments
        ]
    
    async def has_feature_access(self, db: Session, user_id: int, feature: str) -> bool:
        """Check if user has access to a specific feature."""
        subscription = await self.get_user_subscription(db, user_id)
        
        if not subscription or not subscription.is_active:
            # Free plan features
            free_features = ['basic_events', 'basic_planning']
            return feature in free_features
        
        # Check plan features
        feature_mapping = {
            'ai_suggestions': subscription.plan.ai_suggestions,
            'advanced_analytics': subscription.plan.advanced_analytics,
            'custom_branding': subscription.plan.custom_branding,
            'priority_support': subscription.plan.priority_support,
            'api_access': subscription.plan.api_access
        }
        
        return feature_mapping.get(feature, False)
    
    async def _check_free_plan_limits(self, db: Session, user_id: int) -> bool:
        """Check if free plan user can create more events."""
        current_usage = await self._get_free_plan_usage(db, user_id)
        return current_usage < settings.FREE_PLAN_EVENT_LIMIT  # Free plan limit
    
    async def _get_free_plan_usage(self, db: Session, user_id: int) -> int:
        """Get current month's event count for free plan user."""
        # Get events created this month
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        event_count = db.query(Event).filter(
            and_(
                Event.creator_id == user_id,
                Event.created_at >= month_start,
                Event.deleted_at.is_(None)
            )
        ).count()
        
        return event_count
    
    async def _increment_free_plan_usage(self, db: Session, user_id: int) -> None:
        """Increment free plan usage (no action needed as we count events directly)."""
        # For free plan, we count events directly from the events table
        # No need to maintain separate usage counters
        pass
    
    async def _get_or_create_usage_limit(
        self, 
        db: Session, 
        user_id: int, 
        plan: SubscriptionPlan
    ) -> UsageLimit:
        """Get or create usage limit record for current period."""
        now = datetime.utcnow()
        
        # Find current period usage limit
        usage = db.query(UsageLimit).filter(
            and_(
                UsageLimit.user_id == user_id,
                UsageLimit.period_start <= now,
                UsageLimit.period_end > now
            )
        ).first()
        
        if not usage:
            # Create new usage limit for current period
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                period_end = period_start.replace(year=period_start.year + 1, month=1)
            else:
                period_end = period_start.replace(month=period_start.month + 1)
            
            usage = UsageLimit(
                user_id=user_id,
                period_start=period_start,
                period_end=period_end,
                events_limit=plan.max_events,
                storage_limit_gb=plan.max_storage_gb,
                api_calls_limit=10000 if plan.api_access else 0  # Default API limit
            )
            
            db.add(usage)
            db.commit()
            db.refresh(usage)
        
        return usage
    
    async def _initialize_usage_limits(
        self, 
        db: Session, 
        user_id: int, 
        plan: SubscriptionPlan
    ) -> None:
        """Initialize usage limits for a new subscription."""
        await self._get_or_create_usage_limit(db, user_id, plan)
    
    async def reset_monthly_usage(self, db: Session) -> None:
        """Reset usage counters for all users (called monthly via cron)."""
        # This would be called by a scheduled task
        now = datetime.utcnow()
        
        # Find all usage limits that have expired
        expired_limits = db.query(UsageLimit).filter(
            UsageLimit.period_end <= now
        ).all()
        
        for limit in expired_limits:
            # Create new period
            user_subscription = await self.get_user_subscription(db, limit.user_id)
            if user_subscription and user_subscription.is_active:
                await self._get_or_create_usage_limit(db, limit.user_id, user_subscription.plan)
        
        db.commit()
        logger.info(f"Reset usage limits for {len(expired_limits)} users")