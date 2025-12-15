import json
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, time
from app.models.vendor_models import (
    VendorCategory, VendorStatus, BookingStatus, PaymentStatus, ServiceType
)

# Base schemas
class UserBasic(BaseModel):
    """Basic user info for vendor responses."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None

# Vendor schemas
class VendorBase(BaseModel):
    """Base vendor schema."""
    business_name: str = Field(..., min_length=1, max_length=200, description="Business name")
    display_name: str = Field(..., min_length=1, max_length=200, description="Display name")
    description: Optional[str] = Field(None, max_length=2000, description="Business description")
    email: str = Field(..., description="Business email")
    phone: Optional[str] = Field(None, description="Business phone")
    website: Optional[str] = Field(None, description="Business website")
    category: VendorCategory = Field(..., description="Vendor category")
    subcategories: Optional[List[str]] = Field(None, description="Subcategories")
    address: Optional[str] = Field(None, description="Business address")
    city: Optional[str] = Field(None, max_length=100, description="City")
    state: Optional[str] = Field(None, max_length=100, description="State/Province")
    country: Optional[str] = Field(None, max_length=100, description="Country")
    postal_code: Optional[str] = Field(None, max_length=20, description="Postal code")
    service_radius_km: Optional[int] = Field(None, ge=0, le=1000, description="Service radius in km")
    service_areas: Optional[List[str]] = Field(None, description="Service areas")
    years_in_business: Optional[int] = Field(None, ge=0, le=100, description="Years in business")
    license_number: Optional[str] = Field(None, description="Business license number")
    base_price: Optional[float] = Field(None, ge=0, description="Base price")
    currency: str = Field(default="USD", description="Currency")
    pricing_model: ServiceType = Field(default=ServiceType.CUSTOM_QUOTE, description="Pricing model")
    logo_url: Optional[str] = Field(None, description="Logo URL")
    cover_image_url: Optional[str] = Field(None, description="Cover image URL")
    booking_lead_time_days: int = Field(default=7, ge=0, le=365, description="Booking lead time")
    accepts_online_payment: bool = Field(default=True, description="Accepts online payment")
    payment_methods: Optional[List[str]] = Field(None, description="Accepted payment methods")

    @field_validator("subcategories", "service_areas", "payment_methods", mode="before")
    @classmethod
    def _parse_optional_list(cls, value):
        if value is None or isinstance(value, list):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = stripped
            if parsed is None or isinstance(parsed, list):
                return parsed
            return [parsed]
        return value

class VendorCreate(VendorBase):
    """Schema for creating a vendor."""
    pass

class VendorUpdate(BaseModel):
    """Schema for updating a vendor."""
    business_name: Optional[str] = Field(None, min_length=1, max_length=200)
    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    phone: Optional[str] = None
    website: Optional[str] = None
    subcategories: Optional[List[str]] = None
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    service_radius_km: Optional[int] = Field(None, ge=0, le=1000)
    service_areas: Optional[List[str]] = None
    years_in_business: Optional[int] = Field(None, ge=0, le=100)
    license_number: Optional[str] = None
    base_price: Optional[float] = Field(None, ge=0)
    pricing_model: Optional[ServiceType] = None
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    booking_lead_time_days: Optional[int] = Field(None, ge=0, le=365)
    accepts_online_payment: Optional[bool] = None
    payment_methods: Optional[List[str]] = None

class VendorResponse(VendorBase):
    """Schema for vendor response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    status: VendorStatus
    is_featured: bool
    verification_date: Optional[datetime] = None
    average_rating: float
    total_reviews: int
    total_bookings: int
    insurance_verified: bool
    is_available_for_booking: bool
    user: Optional[UserBasic] = None
    created_at: datetime
    updated_at: datetime
    
    @field_validator('subcategories', 'service_areas', 'payment_methods', mode='before')
    def _parse_json_list(cls, value):
        """Normalize JSON strings stored in the database."""
        if value is None or value == []:
            return None
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped or stripped.lower() == 'null':
                return None
            try:
                parsed = json.loads(stripped)
                return parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                return [stripped]
        return value

# Vendor Service schemas
class VendorServiceBase(BaseModel):
    """Base vendor service schema."""
    name: str = Field(..., min_length=1, max_length=200, description="Service name")
    description: str = Field(..., min_length=1, max_length=2000, description="Service description")
    base_price: float = Field(..., ge=0, description="Base price")
    currency: str = Field(default="USD", description="Currency")
    service_type: ServiceType = Field(..., description="Service type")
    duration_hours: Optional[int] = Field(None, ge=1, le=24, description="Service duration")
    max_guests: Optional[int] = Field(None, ge=1, description="Maximum guests")
    includes: Optional[List[str]] = Field(None, description="What's included")
    excludes: Optional[List[str]] = Field(None, description="What's not included")
    advance_booking_days: int = Field(default=7, ge=0, le=365, description="Advance booking required")
    cancellation_policy: Optional[str] = Field(None, description="Cancellation policy")

class VendorServiceCreate(VendorServiceBase):
    """Schema for creating a vendor service."""
    pass

class VendorServiceUpdate(BaseModel):
    """Schema for updating a vendor service."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1, max_length=2000)
    base_price: Optional[float] = Field(None, ge=0)
    service_type: Optional[ServiceType] = None
    duration_hours: Optional[int] = Field(None, ge=1, le=24)
    max_guests: Optional[int] = Field(None, ge=1)
    includes: Optional[List[str]] = None
    excludes: Optional[List[str]] = None
    is_active: Optional[bool] = None
    advance_booking_days: Optional[int] = Field(None, ge=0, le=365)
    cancellation_policy: Optional[str] = None

class VendorServiceResponse(VendorServiceBase):
    """Schema for vendor service response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    vendor_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

# Vendor Booking schemas
class VendorBookingBase(BaseModel):
    """Base vendor booking schema."""
    service_date: datetime = Field(..., description="Service date and time")
    service_duration_hours: Optional[int] = Field(None, ge=1, le=24, description="Service duration")
    guest_count: Optional[int] = Field(None, ge=1, description="Number of guests")
    special_requests: Optional[str] = Field(None, max_length=2000, description="Special requests")
    venue_details: Optional[str] = Field(None, max_length=1000, description="Venue details")
    contact_person: Optional[str] = Field(None, max_length=200, description="Contact person")
    contact_phone: Optional[str] = Field(None, description="Contact phone")

class VendorBookingCreate(VendorBookingBase):
    """Schema for creating a vendor booking."""
    service_id: int = Field(..., description="Service ID")

class VendorBookingUpdate(BaseModel):
    """Schema for updating a vendor booking."""
    service_date: Optional[datetime] = None
    service_duration_hours: Optional[int] = Field(None, ge=1, le=24)
    guest_count: Optional[int] = Field(None, ge=1)
    special_requests: Optional[str] = Field(None, max_length=2000)
    venue_details: Optional[str] = Field(None, max_length=1000)
    contact_person: Optional[str] = Field(None, max_length=200)
    contact_phone: Optional[str] = None
    status: Optional[BookingStatus] = None
    cancellation_reason: Optional[str] = None

class VendorBookingResponse(VendorBookingBase):
    """Schema for vendor booking response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    booking_reference: str
    vendor_id: int
    service_id: int
    event_id: int
    quoted_price: float
    final_price: Optional[float] = None
    currency: str
    deposit_amount: Optional[float] = None
    deposit_paid: bool
    deposit_paid_at: Optional[datetime] = None
    status: BookingStatus
    confirmed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    contract_signed: bool
    contract_url: Optional[str] = None
    terms_accepted: bool
    total_paid: float
    remaining_balance: float
    vendor: VendorResponse
    service: VendorServiceResponse
    booked_by: UserBasic
    created_at: datetime
    updated_at: datetime

# Vendor Payment schemas
class VendorPaymentBase(BaseModel):
    """Base vendor payment schema."""
    amount: float = Field(..., gt=0, description="Payment amount")
    currency: str = Field(default="USD", description="Currency")
    payment_method: str = Field(..., description="Payment method")
    is_deposit: bool = Field(default=False, description="Is this a deposit payment")
    description: Optional[str] = Field(None, max_length=200, description="Payment description")

class VendorPaymentCreate(VendorPaymentBase):
    """Schema for creating a vendor payment."""
    idempotency_key: Optional[str] = Field(None, max_length=255, description="Idempotency key to prevent duplicate payments")

class VendorPaymentResponse(VendorPaymentBase):
    """Schema for vendor payment response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    payment_reference: str
    booking_id: int
    status: PaymentStatus
    payment_provider_id: Optional[str] = None
    paid_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    paid_by: UserBasic
    created_at: datetime
    updated_at: datetime

# Vendor Review schemas
class VendorReviewBase(BaseModel):
    """Base vendor review schema."""
    rating: int = Field(..., ge=1, le=5, description="Overall rating (1-5 stars)")
    title: Optional[str] = Field(None, max_length=200, description="Review title")
    review_text: str = Field(..., min_length=10, max_length=2000, description="Review content")
    service_quality: Optional[int] = Field(None, ge=1, le=5, description="Service quality rating")
    communication: Optional[int] = Field(None, ge=1, le=5, description="Communication rating")
    value_for_money: Optional[int] = Field(None, ge=1, le=5, description="Value for money rating")
    punctuality: Optional[int] = Field(None, ge=1, le=5, description="Punctuality rating")

class VendorReviewCreate(VendorReviewBase):
    """Schema for creating a vendor review."""
    booking_id: Optional[int] = Field(None, description="Related booking ID")

class VendorReviewUpdate(BaseModel):
    """Schema for updating a vendor review."""
    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = Field(None, max_length=200)
    review_text: Optional[str] = Field(None, min_length=10, max_length=2000)
    service_quality: Optional[int] = Field(None, ge=1, le=5)
    communication: Optional[int] = Field(None, ge=1, le=5)
    value_for_money: Optional[int] = Field(None, ge=1, le=5)
    punctuality: Optional[int] = Field(None, ge=1, le=5)

class VendorReviewResponse(VendorReviewBase):
    """Schema for vendor review response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    vendor_id: int
    booking_id: Optional[int] = None
    is_verified: bool
    verified_at: Optional[datetime] = None
    is_approved: bool
    is_featured: bool
    reviewer: UserBasic
    created_at: datetime
    updated_at: datetime

# Vendor Portfolio schemas
class VendorPortfolioBase(BaseModel):
    """Base vendor portfolio schema."""
    title: str = Field(..., min_length=1, max_length=200, description="Portfolio item title")
    description: Optional[str] = Field(None, max_length=1000, description="Portfolio item description")
    image_url: str = Field(..., description="Portfolio image URL")
    event_type: Optional[str] = Field(None, max_length=100, description="Event type")
    event_date: Optional[datetime] = Field(None, description="Event date")
    guest_count: Optional[int] = Field(None, ge=1, description="Number of guests")
    is_featured: bool = Field(default=False, description="Is featured item")
    display_order: int = Field(default=0, description="Display order")

class VendorPortfolioCreate(VendorPortfolioBase):
    """Schema for creating a vendor portfolio item."""
    pass

class VendorPortfolioUpdate(BaseModel):
    """Schema for updating a vendor portfolio item."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    image_url: Optional[str] = None
    event_type: Optional[str] = Field(None, max_length=100)
    event_date: Optional[datetime] = None
    guest_count: Optional[int] = Field(None, ge=1)
    is_featured: Optional[bool] = None
    display_order: Optional[int] = None

class VendorPortfolioResponse(VendorPortfolioBase):
    """Schema for vendor portfolio response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    vendor_id: int
    thumbnail_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# Search and filter schemas
class VendorSearchParams(BaseModel):
    """Schema for vendor search parameters."""
    query: Optional[str] = Field(None, description="Search query")
    category: Optional[VendorCategory] = Field(None, description="Filter by category")
    city: Optional[str] = Field(None, description="Filter by city")
    state: Optional[str] = Field(None, description="Filter by state")
    country: Optional[str] = Field(None, description="Filter by country")
    min_rating: Optional[float] = Field(None, ge=0, le=5, description="Minimum rating")
    max_price: Optional[float] = Field(None, ge=0, description="Maximum price")
    service_date: Optional[datetime] = Field(None, description="Required service date")
    guest_count: Optional[int] = Field(None, ge=1, description="Number of guests")
    verified_only: Optional[bool] = Field(None, description="Verified vendors only")
    featured_first: bool = Field(default=True, description="Show featured vendors first")
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")

class BookingSearchParams(BaseModel):
    """Schema for booking search parameters."""
    status: Optional[BookingStatus] = Field(None, description="Filter by status")
    vendor_id: Optional[int] = Field(None, description="Filter by vendor")
    service_date_from: Optional[datetime] = Field(None, description="Service date from")
    service_date_to: Optional[datetime] = Field(None, description="Service date to")
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")

# List response schemas
class VendorListResponse(BaseModel):
    """Schema for paginated vendor list."""
    vendors: List[VendorResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

class VendorServiceListResponse(BaseModel):
    """Schema for paginated vendor service list."""
    services: List[VendorServiceResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

class VendorBookingListResponse(BaseModel):
    """Schema for paginated vendor booking list."""
    bookings: List[VendorBookingResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

class VendorReviewListResponse(BaseModel):
    """Schema for paginated vendor review list."""
    reviews: List[VendorReviewResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

# Availability schemas
class VendorAvailabilityBase(BaseModel):
    """Base vendor availability schema."""
    date: datetime = Field(..., description="Availability date")
    start_time: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', description="Start time (HH:MM)")
    end_time: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', description="End time (HH:MM)")
    is_available: bool = Field(default=True, description="Is available")
    is_blocked: bool = Field(default=False, description="Is blocked")
    block_reason: Optional[str] = Field(None, max_length=200, description="Block reason")
    price_multiplier: float = Field(default=1.0, ge=0.1, le=10.0, description="Price multiplier")

class VendorAvailabilityCreate(VendorAvailabilityBase):
    """Schema for creating vendor availability."""
    pass

class VendorAvailabilityResponse(VendorAvailabilityBase):
    """Schema for vendor availability response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    vendor_id: int
    created_at: datetime
    updated_at: datetime

# Quote request schema
class VendorQuoteRequest(BaseModel):
    """Schema for requesting a quote from a vendor."""
    service_id: int = Field(..., description="Service ID")
    event_date: datetime = Field(..., description="Event date")
    guest_count: Optional[int] = Field(None, ge=1, description="Number of guests")
    duration_hours: Optional[int] = Field(None, ge=1, le=24, description="Event duration")
    venue_address: Optional[str] = Field(None, description="Venue address")
    special_requirements: Optional[str] = Field(None, max_length=2000, description="Special requirements")
    budget_range: Optional[str] = Field(None, description="Budget range")
    contact_preference: str = Field(default="email", description="Preferred contact method")

class VendorQuoteResponse(BaseModel):
    """Schema for vendor quote response."""
    quote_id: str
    vendor: VendorResponse
    service: VendorServiceResponse
    quoted_price: Optional[float] = None
    quote_details: Optional[str] = None
    valid_until: Optional[datetime] = None
    response_time_hours: Optional[int] = None
    status: str = "pending"  # pending, quoted, accepted, declined

# Statistics schemas
class VendorStatistics(BaseModel):
    """Schema for vendor statistics."""
    total_bookings: int
    completed_bookings: int
    cancelled_bookings: int
    total_revenue: float
    average_rating: float
    total_reviews: int
    response_rate: float
    booking_conversion_rate: float
    repeat_customer_rate: float

# Bulk operations
class BulkVendorServiceCreate(BaseModel):
    """Schema for bulk creating vendor services."""
    services: List[VendorServiceCreate] = Field(..., min_items=1, max_items=20)

class BulkAvailabilityUpdate(BaseModel):
    """Schema for bulk updating availability."""
    availability_updates: List[VendorAvailabilityCreate] = Field(..., min_items=1, max_items=100)

# Contract schemas
class VendorContractBase(BaseModel):
    """Base vendor contract schema."""
    title: str = Field(..., min_length=1, max_length=200, description="Contract title")
    terms_and_conditions: str = Field(..., min_length=1, description="Terms and conditions")
    cancellation_policy: str = Field(..., min_length=1, description="Cancellation policy")
    expires_at: Optional[datetime] = Field(None, description="Contract expiration")

class VendorContractCreate(VendorContractBase):
    """Schema for creating a vendor contract."""
    pass

class VendorContractResponse(VendorContractBase):
    """Schema for vendor contract response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    contract_number: str
    booking_id: int
    client_signed: bool
    client_signed_at: Optional[datetime] = None
    vendor_signed: bool
    vendor_signed_at: Optional[datetime] = None
    is_active: bool
    is_fully_signed: bool
    contract_pdf_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime