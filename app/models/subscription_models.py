from sqlalchemy import Column, String, Boolean, Integer, Float, DateTime, ForeignKey, Text, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.shared_models import TimestampMixin, SoftDeleteMixin, ActiveMixin, IDMixin
from datetime import datetime
import enum

class PlanType(str, enum.Enum):
    """Subscription plan types."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class SubscriptionStatus(str, enum.Enum):
    """Subscription status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    UNPAID = "unpaid"

class PaymentStatus(str, enum.Enum):
    """Payment status for subscriptions."""
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    REFUNDED = "refunded"

class BillingInterval(str, enum.Enum):
    """Billing intervals."""
    MONTHLY = "monthly"
    YEARLY = "yearly"

class SubscriptionPlan(Base, IDMixin, TimestampMixin, ActiveMixin):
    """Subscription plans available."""
    __tablename__ = "subscription_plans"
    
    # Plan details
    name = Column(String(100), nullable=False, unique=True)
    plan_type = Column(SQLEnum(PlanType), nullable=False)
    description = Column(Text, nullable=True)
    
    # Pricing
    price_monthly = Column(Float, nullable=False, default=0.0)
    price_yearly = Column(Float, nullable=False, default=0.0)
    
    # Limits
    max_events = Column(Integer, nullable=True)  # NULL means unlimited
    max_attendees_per_event = Column(Integer, nullable=True)
    max_storage_gb = Column(Float, nullable=True)
    
    # Features
    ai_suggestions = Column(Boolean, default=False, nullable=False)
    advanced_analytics = Column(Boolean, default=False, nullable=False)
    custom_branding = Column(Boolean, default=False, nullable=False)
    priority_support = Column(Boolean, default=False, nullable=False)
    api_access = Column(Boolean, default=False, nullable=False)
    
    # Stripe integration
    stripe_price_id_monthly = Column(String(100), nullable=True)
    stripe_price_id_yearly = Column(String(100), nullable=True)
    stripe_product_id = Column(String(100), nullable=True)
    
    # Relationships
    subscriptions = relationship("UserSubscription", back_populates="plan")
    
    # Database indexes
    __table_args__ = (
        Index('idx_plan_type', 'plan_type'),
        Index('idx_plan_active', 'is_active'),
        Index('idx_stripe_price_monthly', 'stripe_price_id_monthly'),
        Index('idx_stripe_price_yearly', 'stripe_price_id_yearly'),
    )
    
    # Features and limits
    max_events = Column(Integer, nullable=True)  # NULL means unlimited
    max_attendees_per_event = Column(Integer, nullable=True)
    max_storage_gb = Column(Float, nullable=True)
    
    # Feature flags
    ai_suggestions = Column(Boolean, default=False, nullable=False)
    advanced_analytics = Column(Boolean, default=False, nullable=False)
    custom_branding = Column(Boolean, default=False, nullable=False)
    priority_support = Column(Boolean, default=False, nullable=False)
    api_access = Column(Boolean, default=False, nullable=False)
    
    # Stripe integration
    stripe_price_id_monthly = Column(String(100), nullable=True)
    stripe_price_id_yearly = Column(String(100), nullable=True)
    stripe_product_id = Column(String(100), nullable=True)
    
    # Relationships
    subscriptions = relationship("UserSubscription", back_populates="plan")
    
    def __repr__(self):
        return f"<SubscriptionPlan(id={self.id}, name='{self.name}', type='{self.plan_type}')>"

class UserSubscription(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """User subscription details."""
    __tablename__ = "user_subscriptions"
    
    # User and plan
    user_id = Column(ForeignKey("users.id"), nullable=False)
    plan_id = Column(ForeignKey("subscription_plans.id"), nullable=False)
    
    # Subscription details
    status = Column(SQLEnum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.ACTIVE)
    billing_interval = Column(SQLEnum(BillingInterval), nullable=False, default=BillingInterval.MONTHLY)
    
    # Dates
    start_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    trial_end_date = Column(DateTime, nullable=True)
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    
    # Stripe integration
    stripe_subscription_id = Column(String(100), nullable=True, unique=True)
    stripe_customer_id = Column(String(100), nullable=True)
    
    # Usage tracking
    events_created_this_period = Column(Integer, default=0, nullable=False)
    storage_used_gb = Column(Float, default=0.0, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="subscription")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")
    payments = relationship("SubscriptionPayment", back_populates="subscription", cascade="all, delete-orphan")
    
    # Database indexes
    __table_args__ = (
        Index('idx_user_subscription', 'user_id'),
        Index('idx_subscription_status', 'status'),
        Index('idx_subscription_dates', 'start_date', 'end_date'),
        Index('idx_stripe_subscription', 'stripe_subscription_id'),
        Index('idx_stripe_customer', 'stripe_customer_id'),
        Index('idx_subscription_period', 'current_period_start', 'current_period_end'),
        Index('idx_user_status', 'user_id', 'status'),
    )
    
    def __repr__(self):
        return f"<UserSubscription(user_id={self.user_id}, plan='{self.plan.name}', status='{self.status}')>"
    
    @property
    def is_active(self):
        """Check if subscription is currently active."""
        return self.status == SubscriptionStatus.ACTIVE and (
            self.end_date is None or self.end_date > datetime.utcnow()
        )
    
    @property
    def is_trial(self):
        """Check if subscription is in trial period."""
        return (
            self.status == SubscriptionStatus.TRIALING and 
            self.trial_end_date and 
            self.trial_end_date > datetime.utcnow()
        )
    
    @property
    def days_remaining(self):
        """Get days remaining in current period."""
        if self.current_period_end:
            delta = self.current_period_end - datetime.utcnow()
            return max(0, delta.days)
        return 0

class SubscriptionPayment(Base, IDMixin, TimestampMixin):
    """Payment records for subscriptions."""
    __tablename__ = "subscription_payments"
    
    # Subscription reference
    subscription_id = Column(ForeignKey("user_subscriptions.id"), nullable=False)
    
    # Payment details
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    status = Column(SQLEnum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    
    # Stripe integration
    stripe_payment_intent_id = Column(String(100), nullable=True)
    stripe_invoice_id = Column(String(100), nullable=True)
    
    # Payment metadata
    billing_reason = Column(String(50), nullable=True)  # subscription_create, subscription_cycle, etc.
    payment_method_type = Column(String(50), nullable=True)  # card, bank_account, etc.
    
    # Dates
    paid_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    refunded_at = Column(DateTime, nullable=True)
    
    # Error handling
    failure_code = Column(String(50), nullable=True)
    failure_message = Column(Text, nullable=True)
    
    # Relationships
    subscription = relationship("UserSubscription", back_populates="payments")
    
    # Database indexes
    __table_args__ = (
        Index('idx_payment_subscription', 'subscription_id'),
        Index('idx_payment_status', 'status'),
        Index('idx_payment_dates', 'paid_at'),
        Index('idx_stripe_payment_intent', 'stripe_payment_intent_id'),
        Index('idx_stripe_invoice', 'stripe_invoice_id'),
        Index('idx_payment_amount', 'amount'),
    )
    
    def __repr__(self):
        return f"<SubscriptionPayment(id={self.id}, amount={self.amount}, status='{self.status}')>"

class StripeEventLog(Base, IDMixin, TimestampMixin):
    """Log of processed Stripe webhook events for idempotency."""
    __tablename__ = "stripe_event_logs"
    
    # Stripe event ID (unique per event)
    event_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # Event type (e.g., invoice.payment_succeeded)
    event_type = Column(String(100), nullable=True)
    
    # Processing status
    processing_status = Column(String(50), default="pending", nullable=False)  # pending, processing, completed, failed
    
    # Event metadata (stored as JSON string)
    event_metadata = Column(Text, nullable=True)
    
    # Processing details
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    
    # Database indexes
    __table_args__ = (
        Index('idx_stripe_event_id', 'event_id'),
        Index('idx_stripe_event_type', 'event_type'),
        Index('idx_stripe_processing_status', 'processing_status'),
        Index('idx_stripe_processed_at', 'processed_at'),
    )
    
    def __repr__(self):
        return f"<StripeEventLog(event_id='{self.event_id}', type='{self.event_type}', status='{self.processing_status}')>"

class UsageLimit(Base, IDMixin, TimestampMixin):
    """Track usage limits and overages."""
    __tablename__ = "usage_limits"
    
    # User reference
    user_id = Column(ForeignKey("users.id"), nullable=False)
    
    # Current period tracking
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Usage counters
    events_created = Column(Integer, default=0, nullable=False)
    storage_used_gb = Column(Float, default=0.0, nullable=False)
    api_calls_made = Column(Integer, default=0, nullable=False)
    
    # Limit tracking
    events_limit = Column(Integer, nullable=True)
    storage_limit_gb = Column(Float, nullable=True)
    api_calls_limit = Column(Integer, nullable=True)
    
    # Overage flags
    events_exceeded = Column(Boolean, default=False, nullable=False)
    storage_exceeded = Column(Boolean, default=False, nullable=False)
    api_calls_exceeded = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="usage_limits")
    
    # Database indexes
    __table_args__ = (
        Index('idx_usage_user', 'user_id'),
        Index('idx_usage_period', 'period_start', 'period_end'),
        Index('idx_usage_exceeded', 'events_exceeded', 'storage_exceeded', 'api_calls_exceeded'),
        Index('idx_usage_user_period', 'user_id', 'period_start', 'period_end'),
    )
    
    def __repr__(self):
        return f"<UsageLimit(user_id={self.user_id}, events={self.events_created}/{self.events_limit})>"
    
    @property
    def events_remaining(self):
        """Get remaining events for current period."""
        if self.events_limit is None:
            return float('inf')
        return max(0, self.events_limit - self.events_created)
    
    @property
    def storage_remaining_gb(self):
        """Get remaining storage in GB."""
        if self.storage_limit_gb is None:
            return float('inf')
        return max(0, self.storage_limit_gb - self.storage_used_gb)