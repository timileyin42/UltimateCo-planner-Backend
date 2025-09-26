from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum, Float, JSON, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.models.shared_models import BaseModel, TimestampMixin
import enum

class VendorCategory(str, enum.Enum):
    """Categories of vendors."""
    VENUE = "venue"
    CATERING = "catering"
    PHOTOGRAPHY = "photography"
    VIDEOGRAPHY = "videography"
    MUSIC_DJ = "music_dj"
    ENTERTAINMENT = "entertainment"
    FLORIST = "florist"
    DECORATION = "decoration"
    TRANSPORTATION = "transportation"
    SECURITY = "security"
    CLEANING = "cleaning"
    EQUIPMENT_RENTAL = "equipment_rental"
    OTHER = "other"

class VendorStatus(str, enum.Enum):
    """Status of vendors."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    SUSPENDED = "suspended"

class BookingStatus(str, enum.Enum):
    """Status of vendor bookings."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

class PaymentStatus(str, enum.Enum):
    """Status of payments."""
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_PAID = "partially_paid"

class ServiceType(str, enum.Enum):
    """Types of services offered."""
    HOURLY = "hourly"
    FIXED_PRICE = "fixed_price"
    PACKAGE = "package"
    CUSTOM_QUOTE = "custom_quote"

class Vendor(BaseModel, TimestampMixin):
    """Vendor profiles for service providers."""
    __tablename__ = "vendors"
    
    # Basic info
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Contact info
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Business details
    category: Mapped[VendorCategory] = mapped_column(SQLEnum(VendorCategory), nullable=False)
    subcategories: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    
    # Location
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Service area
    service_radius_km: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    service_areas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of cities/regions
    
    # Business info
    years_in_business: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    license_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    insurance_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Pricing
    base_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    pricing_model: Mapped[ServiceType] = mapped_column(SQLEnum(ServiceType), default=ServiceType.CUSTOM_QUOTE)
    
    # Status and verification
    status: Mapped[VendorStatus] = mapped_column(SQLEnum(VendorStatus), default=VendorStatus.PENDING_VERIFICATION)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Media
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cover_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Ratings and reviews
    average_rating: Mapped[float] = mapped_column(Float, default=0.0)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)
    total_bookings: Mapped[int] = mapped_column(Integer, default=0)
    
    # Availability
    availability_calendar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON object
    booking_lead_time_days: Mapped[int] = mapped_column(Integer, default=7)
    
    # Payment info
    accepts_online_payment: Mapped[bool] = mapped_column(Boolean, default=True)
    payment_methods: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    stripe_account_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Relationships
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)  # If vendor has user account
    
    # Relationships
    user = relationship("User", back_populates="vendor_profile")
    services = relationship("VendorService", back_populates="vendor", cascade="all, delete-orphan")
    bookings = relationship("VendorBooking", back_populates="vendor", cascade="all, delete-orphan")
    reviews = relationship("VendorReview", back_populates="vendor", cascade="all, delete-orphan")
    portfolio_items = relationship("VendorPortfolio", back_populates="vendor", cascade="all, delete-orphan")
    
    # Database indexes for performance
    __table_args__ = (
        Index('idx_vendor_category', 'category'),
        Index('idx_vendor_status', 'status'),
        Index('idx_vendor_city', 'city'),
        Index('idx_vendor_email', 'email'),
        Index('idx_vendor_is_featured', 'is_featured'),
        Index('idx_vendor_average_rating', 'average_rating'),
        Index('idx_vendor_stripe_account_id', 'stripe_account_id'),
        Index('idx_vendor_category_status', 'category', 'status'),
        Index('idx_vendor_city_category', 'city', 'category'),
        Index('idx_vendor_location', 'latitude', 'longitude'),
    )
    
    def __repr__(self):
        return f"<Vendor(id={self.id}, business_name='{self.business_name}', category='{self.category}')>"
    
    @property
    def is_available_for_booking(self) -> bool:
        """Check if vendor is available for new bookings."""
        return self.status in [VendorStatus.ACTIVE, VendorStatus.VERIFIED]

class VendorService(BaseModel, TimestampMixin):
    """Services offered by vendors."""
    __tablename__ = "vendor_services"
    
    # Service info
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Pricing
    base_price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    service_type: Mapped[ServiceType] = mapped_column(SQLEnum(ServiceType), nullable=False)
    
    # Service details
    duration_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_guests: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    includes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of what's included
    excludes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of what's not included
    
    # Availability
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    seasonal_availability: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON object
    
    # Requirements
    advance_booking_days: Mapped[int] = mapped_column(Integer, default=7)
    cancellation_policy: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    
    # Relationships
    vendor = relationship("Vendor", back_populates="services")
    bookings = relationship("VendorBooking", back_populates="service")
    
    def __repr__(self):
        return f"<VendorService(id={self.id}, name='{self.name}', price={self.base_price})>"

class VendorBooking(BaseModel, TimestampMixin):
    """Bookings made with vendors."""
    __tablename__ = "vendor_bookings"
    
    # Booking info
    booking_reference: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    
    # Service details
    service_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    service_duration_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    guest_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Pricing
    quoted_price: Mapped[float] = mapped_column(Float, nullable=False)
    final_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    
    # Payment
    deposit_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deposit_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    deposit_paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Status
    status: Mapped[BookingStatus] = mapped_column(SQLEnum(BookingStatus), default=BookingStatus.PENDING)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Special requirements
    special_requests: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    venue_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_person: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Contract and terms
    contract_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    contract_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    terms_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    service_id: Mapped[int] = mapped_column(ForeignKey("vendor_services.id"), nullable=False)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    booked_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    vendor = relationship("Vendor", back_populates="bookings")
    service = relationship("VendorService", back_populates="bookings")
    event = relationship("Event", back_populates="vendor_bookings")
    booked_by = relationship("User", back_populates="vendor_bookings")
    payments = relationship("VendorPayment", back_populates="booking", cascade="all, delete-orphan")
    
    # Database indexes for performance
    __table_args__ = (
        Index('idx_vendor_booking_reference', 'booking_reference'),
        Index('idx_vendor_booking_vendor_id', 'vendor_id'),
        Index('idx_vendor_booking_status', 'status'),
        Index('idx_vendor_booking_service_date', 'service_date'),
        Index('idx_vendor_booking_event_id', 'event_id'),
        Index('idx_vendor_booking_booked_by_id', 'booked_by_id'),
        Index('idx_vendor_booking_confirmed_at', 'confirmed_at'),
        Index('idx_vendor_booking_vendor_status', 'vendor_id', 'status'),
        Index('idx_vendor_booking_service_date_status', 'service_date', 'status'),
    )
    
    def __repr__(self):
        return f"<VendorBooking(id={self.id}, reference='{self.booking_reference}', status='{self.status}')>"
    
    @property
    def total_paid(self) -> float:
        """Calculate total amount paid for this booking."""
        return sum(payment.amount for payment in self.payments if payment.status == PaymentStatus.PAID)
    
    @property
    def remaining_balance(self) -> float:
        """Calculate remaining balance to be paid."""
        final_amount = self.final_price or self.quoted_price
        return max(0, final_amount - self.total_paid)

class VendorPayment(BaseModel, TimestampMixin):
    """Payments made to vendors."""
    __tablename__ = "vendor_payments"
    
    # Payment info
    payment_reference: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    
    # Payment method
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)  # stripe, paypal, bank_transfer
    payment_provider_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Stripe payment intent ID
    
    # Stripe-specific fields
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    stripe_charge_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    stripe_transfer_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # For vendor payouts
    
    # Status and timing
    status: Mapped[PaymentStatus] = mapped_column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    refunded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Payment details
    is_deposit: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    # Error handling
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Metadata
    metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON object
    
    # Relationships
    booking_id: Mapped[int] = mapped_column(ForeignKey("vendor_bookings.id"), nullable=False)
    paid_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    booking = relationship("VendorBooking", back_populates="payments")
    paid_by = relationship("User", back_populates="vendor_payments")
    
    # Database indexes for performance
    __table_args__ = (
        Index('idx_vendor_payment_booking_id', 'booking_id'),
        Index('idx_vendor_payment_status', 'status'),
        Index('idx_vendor_payment_paid_at', 'paid_at'),
        Index('idx_vendor_payment_stripe_payment_intent_id', 'stripe_payment_intent_id'),
        Index('idx_vendor_payment_stripe_charge_id', 'stripe_charge_id'),
        Index('idx_vendor_payment_amount', 'amount'),
        Index('idx_vendor_payment_booking_status', 'booking_id', 'status'),
    )
    
    def __repr__(self):
        return f"<VendorPayment(id={self.id}, amount={self.amount}, status='{self.status}')>"

class VendorReview(BaseModel, TimestampMixin):
    """Reviews and ratings for vendors."""
    __tablename__ = "vendor_reviews"
    
    # Review content
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5 stars
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Review details
    service_quality: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5
    communication: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5
    value_for_money: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5
    punctuality: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5
    
    # Verification
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Moderation
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    booking_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendor_bookings.id"), nullable=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    vendor = relationship("Vendor", back_populates="reviews")
    booking = relationship("VendorBooking")
    reviewer = relationship("User", back_populates="vendor_reviews")
    
    def __repr__(self):
        return f"<VendorReview(id={self.id}, vendor_id={self.vendor_id}, rating={self.rating})>"

class VendorPortfolio(BaseModel, TimestampMixin):
    """Portfolio items for vendors to showcase their work."""
    __tablename__ = "vendor_portfolio"
    
    # Portfolio item info
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Media
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Event details
    event_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    event_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    guest_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Display settings
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    
    # Relationships
    vendor = relationship("Vendor", back_populates="portfolio_items")
    
    def __repr__(self):
        return f"<VendorPortfolio(id={self.id}, title='{self.title}', vendor_id={self.vendor_id})>"

class VendorAvailability(BaseModel, TimestampMixin):
    """Vendor availability calendar."""
    __tablename__ = "vendor_availability"
    
    # Date and time
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    start_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # "09:00"
    end_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # "17:00"
    
    # Availability status
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    block_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    # Pricing adjustments
    price_multiplier: Mapped[float] = mapped_column(Float, default=1.0)  # For peak/off-peak pricing
    
    # Relationships
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    
    # Relationships
    vendor = relationship("Vendor")
    
    def __repr__(self):
        return f"<VendorAvailability(vendor_id={self.vendor_id}, date='{self.date}', available={self.is_available})>"

class VendorContract(BaseModel, TimestampMixin):
    """Contracts between clients and vendors."""
    __tablename__ = "vendor_contracts"
    
    # Contract info
    contract_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    
    # Contract content
    terms_and_conditions: Mapped[str] = mapped_column(Text, nullable=False)
    cancellation_policy: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Signatures
    client_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    client_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    client_signature_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    vendor_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    vendor_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    vendor_signature_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Contract status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Document
    contract_pdf_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Relationships
    booking_id: Mapped[int] = mapped_column(ForeignKey("vendor_bookings.id"), nullable=False)
    
    # Relationships
    booking = relationship("VendorBooking")
    
    def __repr__(self):
        return f"<VendorContract(id={self.id}, number='{self.contract_number}')>"
    
    @property
    def is_fully_signed(self) -> bool:
        """Check if contract is signed by both parties."""
        return self.client_signed and self.vendor_signed