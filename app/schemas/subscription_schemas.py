from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from app.models.subscription_models import PlanType, SubscriptionStatus, BillingInterval, PaymentStatus

class PlanTypeEnum(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class SubscriptionStatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    UNPAID = "unpaid"

class BillingIntervalEnum(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"

class PaymentStatusEnum(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    REFUNDED = "refunded"

# Base schemas
class SubscriptionPlanBase(BaseModel):
    name: str = Field(..., description="Plan name")
    plan_type: PlanTypeEnum = Field(..., description="Type of plan")
    description: Optional[str] = Field(None, description="Plan description")
    price_monthly: float = Field(..., ge=0, description="Monthly price")
    price_yearly: float = Field(..., ge=0, description="Yearly price")
    max_events: Optional[int] = Field(None, ge=0, description="Maximum events per month (null = unlimited)")
    max_attendees_per_event: Optional[int] = Field(None, ge=0, description="Maximum attendees per event")
    max_storage_gb: Optional[float] = Field(None, ge=0, description="Maximum storage in GB")
    ai_suggestions: bool = Field(False, description="AI suggestions feature")
    advanced_analytics: bool = Field(False, description="Advanced analytics feature")
    custom_branding: bool = Field(False, description="Custom branding feature")
    priority_support: bool = Field(False, description="Priority support feature")
    api_access: bool = Field(False, description="API access feature")

class SubscriptionPlanCreate(SubscriptionPlanBase):
    stripe_price_id_monthly: Optional[str] = Field(None, description="Stripe monthly price ID")
    stripe_price_id_yearly: Optional[str] = Field(None, description="Stripe yearly price ID")
    stripe_product_id: Optional[str] = Field(None, description="Stripe product ID")

class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_monthly: Optional[float] = Field(None, ge=0)
    price_yearly: Optional[float] = Field(None, ge=0)
    max_events: Optional[int] = Field(None, ge=0)
    max_attendees_per_event: Optional[int] = Field(None, ge=0)
    max_storage_gb: Optional[float] = Field(None, ge=0)
    ai_suggestions: Optional[bool] = None
    advanced_analytics: Optional[bool] = None
    custom_branding: Optional[bool] = None
    priority_support: Optional[bool] = None
    api_access: Optional[bool] = None
    is_active: Optional[bool] = None

class SubscriptionPlan(SubscriptionPlanBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

# Subscription schemas
class SubscriptionCreate(BaseModel):
    plan_id: int = Field(..., description="ID of the subscription plan")
    billing_interval: BillingIntervalEnum = Field(..., description="Billing interval")
    payment_method_id: str = Field(..., description="Stripe payment method ID")
    trial_days: Optional[int] = Field(None, ge=0, le=365, description="Trial period in days")

class UserSubscriptionBase(BaseModel):
    status: SubscriptionStatusEnum
    billing_interval: BillingIntervalEnum
    start_date: datetime
    end_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    events_created_this_period: int = 0
    storage_used_gb: float = 0.0

class UserSubscription(UserSubscriptionBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    plan_id: int
    plan: SubscriptionPlan
    created_at: datetime
    updated_at: datetime
    
    @property
    def is_active(self) -> bool:
        return self.status == SubscriptionStatusEnum.ACTIVE and (
            self.end_date is None or self.end_date > datetime.utcnow()
        )
    
    @property
    def is_trial(self) -> bool:
        return (
            self.status == SubscriptionStatusEnum.TRIALING and 
            self.trial_end_date and 
            self.trial_end_date > datetime.utcnow()
        )

# Payment schemas
class SubscriptionPaymentBase(BaseModel):
    amount: float = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=3)
    status: PaymentStatusEnum
    billing_reason: Optional[str] = None
    payment_method_type: Optional[str] = None
    paid_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None

class SubscriptionPayment(SubscriptionPaymentBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    subscription_id: int
    created_at: datetime
    updated_at: datetime

# Usage schemas
class UsageLimitBase(BaseModel):
    period_start: datetime
    period_end: datetime
    events_created: int = 0
    storage_used_gb: float = 0.0
    api_calls_made: int = 0
    events_limit: Optional[int] = None
    storage_limit_gb: Optional[float] = None
    api_calls_limit: Optional[int] = None
    events_exceeded: bool = False
    storage_exceeded: bool = False
    api_calls_exceeded: bool = False

class UsageLimit(UsageLimitBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    @property
    def events_remaining(self) -> float:
        if self.events_limit is None:
            return float('inf')
        return max(0, self.events_limit - self.events_created)
    
    @property
    def storage_remaining_gb(self) -> float:
        if self.storage_limit_gb is None:
            return float('inf')
        return max(0, self.storage_limit_gb - self.storage_used_gb)

# Response schemas
class UsageSummary(BaseModel):
    plan_name: str
    plan_type: PlanTypeEnum
    events_created: int
    events_limit: Optional[int]
    events_remaining: float
    is_unlimited: bool
    subscription_status: Optional[SubscriptionStatusEnum]
    billing_interval: Optional[BillingIntervalEnum]
    next_billing_date: Optional[datetime]
    storage_used_gb: Optional[float] = 0.0
    storage_limit_gb: Optional[float] = None
    features: Dict[str, bool] = {}

class BillingHistory(BaseModel):
    id: int
    amount: float
    currency: str
    status: PaymentStatusEnum
    billing_reason: Optional[str]
    paid_at: Optional[datetime]
    created_at: datetime
    stripe_invoice_id: Optional[str]

class PaymentMethodInfo(BaseModel):
    id: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_default: bool

class SetupIntentResponse(BaseModel):
    client_secret: str
    setup_intent_id: str

# Request schemas
class UpdatePaymentMethodRequest(BaseModel):
    payment_method_id: str = Field(..., description="New Stripe payment method ID")

class CancelSubscriptionRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Reason for cancellation")
    feedback: Optional[str] = Field(None, description="Additional feedback")

class UpgradeSubscriptionRequest(BaseModel):
    new_plan_id: int = Field(..., description="ID of the new plan")
    billing_interval: Optional[BillingIntervalEnum] = Field(None, description="New billing interval")

# Webhook schemas
class StripeWebhookEvent(BaseModel):
    id: str
    type: str
    data: Dict[str, Any]
    created: int

# Feature access schemas
class FeatureAccessRequest(BaseModel):
    feature: str = Field(..., description="Feature name to check access for")

class FeatureAccessResponse(BaseModel):
    feature: str
    has_access: bool
    plan_required: Optional[str] = None
    upgrade_url: Optional[str] = None

# Plan comparison schema
class PlanComparison(BaseModel):
    plans: List[SubscriptionPlan]
    current_plan_id: Optional[int] = None
    recommendations: List[str] = []

# Subscription analytics (for admin)
class SubscriptionAnalytics(BaseModel):
    total_subscribers: int
    active_subscribers: int
    trial_subscribers: int
    canceled_subscribers: int
    monthly_recurring_revenue: float
    annual_recurring_revenue: float
    churn_rate: float
    plan_distribution: Dict[str, int]
    recent_signups: int
    recent_cancellations: int