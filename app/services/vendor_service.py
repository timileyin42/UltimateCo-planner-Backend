from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.repositories.vendor_repo import VendorRepository
from app.repositories.event_repo import EventRepository
from app.models.vendor_models import (
    VendorCategory, VendorStatus, BookingStatus, PaymentStatus, ServiceType
)
from app.core.idempotency import idempotent_operation, IdempotencyManager
from app.core.errors import NotFoundError, AuthorizationError, ValidationError
import json
import uuid
from decimal import Decimal

class VendorService:
    """Service for managing vendor collaboration and bookings."""
    
    def __init__(self, db: Session):
        self.db = db
        self.vendor_repo = VendorRepository(db)
        self.event_repo = EventRepository(db)
    
    # Vendor CRUD operations
    def create_vendor(
        self, 
        user_id: int, 
        vendor_data: Dict[str, Any]
    ):
        """Create a new vendor profile."""
        # Check if user already has a vendor profile
        existing_vendor = self.vendor_repo.get_by_user_id(user_id)
        if existing_vendor:
            raise ValidationError("User already has a vendor profile")
        
        # Prepare vendor data
        processed_data = {
            'business_name': vendor_data['business_name'],
            'display_name': vendor_data['display_name'],
            'description': vendor_data.get('description'),
            'email': vendor_data['email'],
            'phone': vendor_data.get('phone'),
            'website': vendor_data.get('website'),
            'category': VendorCategory(vendor_data['category']),
            'subcategories': json.dumps(vendor_data.get('subcategories', [])),
            'address': vendor_data.get('address'),
            'city': vendor_data.get('city'),
            'state': vendor_data.get('state'),
            'country': vendor_data.get('country'),
            'postal_code': vendor_data.get('postal_code'),
            'service_radius_km': vendor_data.get('service_radius_km'),
            'service_areas': json.dumps(vendor_data.get('service_areas', [])),
            'years_in_business': vendor_data.get('years_in_business'),
            'license_number': vendor_data.get('license_number'),
            'base_price': vendor_data.get('base_price'),
            'currency': vendor_data.get('currency', 'USD'),
            'pricing_model': ServiceType(vendor_data.get('pricing_model', 'custom_quote')),
            'logo_url': vendor_data.get('logo_url'),
            'cover_image_url': vendor_data.get('cover_image_url'),
            'booking_lead_time_days': vendor_data.get('booking_lead_time_days', 7),
            'accepts_online_payment': vendor_data.get('accepts_online_payment', True),
            'payment_methods': json.dumps(vendor_data.get('payment_methods', ['credit_card'])),
            'user_id': user_id
        }
        
        return self.vendor_repo.create(processed_data)
    
    def get_vendor(self, vendor_id: int):
        """Get a vendor by ID."""
        return self.vendor_repo.get_by_id(vendor_id, include_relations=True)
    
    def search_vendors(
        self, 
        search_params: Dict[str, Any]
    ) -> Tuple[List, int]:
        """Search vendors with filters."""
        from app.schemas.pagination import PaginationParams
        
        # Create pagination params
        page = search_params.get('page', 1)
        per_page = search_params.get('per_page', 20)
        pagination = PaginationParams(page=page, per_page=per_page)
        
        return self.vendor_repo.search_vendors(search_params, pagination)
    
    def update_vendor(
        self, 
        vendor_id: int, 
        user_id: int, 
        update_data: Dict[str, Any]
    ):
        """Update a vendor profile."""
        vendor = self.vendor_repo.get_by_id(vendor_id)
        
        if not vendor:
            raise NotFoundError("Vendor not found")
        
        # Check permissions
        if vendor.user_id != user_id:
            raise AuthorizationError("You don't have permission to edit this vendor")
        
        # Process special fields that need JSON encoding
        processed_data = {}
        for field, value in update_data.items():
            if field in ['subcategories', 'service_areas', 'payment_methods'] and value is not None:
                processed_data[field] = json.dumps(value)
            else:
                processed_data[field] = value
        
        return self.vendor_repo.update(vendor_id, processed_data)
    
    # Vendor Service operations
    def create_vendor_service(
        self, 
        vendor_id: int, 
        user_id: int, 
        service_data: Dict[str, Any]
    ) -> VendorService:
        """Create a new service for a vendor."""
        vendor = self.db.query(Vendor).filter(Vendor.id == vendor_id).first()
        
        if not vendor:
            raise NotFoundError("Vendor not found")
        
        # Check permissions
        if vendor.user_id != user_id:
            raise AuthorizationError("You don't have permission to add services to this vendor")
        
        # Create service
        service = VendorService(
            vendor_id=vendor_id,
            name=service_data['name'],
            description=service_data['description'],
            base_price=service_data['base_price'],
            currency=service_data.get('currency', 'USD'),
            service_type=ServiceType(service_data['service_type']),
            duration_hours=service_data.get('duration_hours'),
            max_guests=service_data.get('max_guests'),
            includes=json.dumps(service_data.get('includes', [])),
            excludes=json.dumps(service_data.get('excludes', [])),
            advance_booking_days=service_data.get('advance_booking_days', 7),
            cancellation_policy=service_data.get('cancellation_policy')
        )
        
        self.db.add(service)
        self.db.commit()
        self.db.refresh(service)
        
        return service
    
    def get_vendor_services(self, vendor_id: int) -> List[VendorService]:
        """Get all services for a vendor."""
        return self.db.query(VendorService).filter(
            VendorService.vendor_id == vendor_id,
            VendorService.is_active == True
        ).all()
    
    # Booking operations
    def create_booking(
        self, 
        service_id: int, 
        event_id: int, 
        user_id: int, 
        booking_data: Dict[str, Any]
    ) -> VendorBooking:
        """Create a new vendor booking."""
        service = self.db.query(VendorService).options(
            joinedload(VendorService.vendor)
        ).filter(VendorService.id == service_id).first()
        
        if not service:
            raise NotFoundError("Service not found")
        
        if not service.is_active:
            raise ValidationError("Service is not available for booking")
        
        # Verify event exists and user has access
        event = self._get_event_with_access(event_id, user_id)
        
        # Check availability
        if not self._check_availability(service.vendor_id, booking_data['service_date']):
            raise ValidationError("Vendor is not available on the requested date")
        
        # Generate booking reference
        booking_reference = f"BK-{uuid.uuid4().hex[:8].upper()}"
        
        # Calculate quoted price
        quoted_price = self._calculate_service_price(
            service, 
            booking_data.get('guest_count'),
            booking_data.get('service_duration_hours')
        )
        
        # Create booking
        booking = VendorBooking(
            booking_reference=booking_reference,
            vendor_id=service.vendor_id,
            service_id=service_id,
            event_id=event_id,
            booked_by_id=user_id,
            service_date=booking_data['service_date'],
            service_duration_hours=booking_data.get('service_duration_hours'),
            guest_count=booking_data.get('guest_count'),
            quoted_price=quoted_price,
            currency=service.currency,
            special_requests=booking_data.get('special_requests'),
            venue_details=booking_data.get('venue_details'),
            contact_person=booking_data.get('contact_person'),
            contact_phone=booking_data.get('contact_phone')
        )
        
        self.db.add(booking)
        self.db.commit()
        self.db.refresh(booking)
        
        # Update vendor booking count
        service.vendor.total_bookings += 1
        self.db.commit()
        
        return booking
    
    def get_booking(self, booking_id: int, user_id: int) -> Optional[VendorBooking]:
        """Get a booking by ID."""
        booking = self.db.query(VendorBooking).options(
            joinedload(VendorBooking.vendor),
            joinedload(VendorBooking.service),
            joinedload(VendorBooking.booked_by),
            joinedload(VendorBooking.payments)
        ).filter(VendorBooking.id == booking_id).first()
        
        if not booking:
            return None
        
        # Check access permissions
        if (booking.booked_by_id != user_id and 
            booking.vendor.user_id != user_id):
            raise AuthorizationError("You don't have access to this booking")
        
        return booking
    
    def update_booking_status(
        self, 
        booking_id: int, 
        user_id: int, 
        status: BookingStatus,
        reason: Optional[str] = None
    ) -> VendorBooking:
        """Update booking status."""
        booking = self.db.query(VendorBooking).filter(VendorBooking.id == booking_id).first()
        
        if not booking:
            raise NotFoundError("Booking not found")
        
        # Check permissions (vendor or client can update)
        vendor = self.db.query(Vendor).filter(Vendor.id == booking.vendor_id).first()
        if booking.booked_by_id != user_id and vendor.user_id != user_id:
            raise AuthorizationError("You don't have permission to update this booking")
        
        old_status = booking.status
        booking.status = status
        
        if status == BookingStatus.CONFIRMED:
            booking.confirmed_at = datetime.utcnow()
        elif status == BookingStatus.CANCELLED:
            booking.cancelled_at = datetime.utcnow()
            booking.cancellation_reason = reason
        
        self.db.commit()
        self.db.refresh(booking)
        
        return booking
    
    # Payment operations
    @idempotent_operation(resource_type="vendor_payment", expiry_hours=24)
    def create_payment(
        self, 
        booking_id: int, 
        user_id: int, 
        payment_data: Dict[str, Any],
        idempotency_key: Optional[str] = None
    ) -> VendorPayment:
        """Create a payment for a booking."""
        booking = self.db.query(VendorBooking).filter(VendorBooking.id == booking_id).first()
        
        if not booking:
            raise NotFoundError("Booking not found")
        
        # Check permissions
        if booking.booked_by_id != user_id:
            raise AuthorizationError("You don't have permission to make payments for this booking")
        
        # Generate payment reference
        payment_reference = f"PAY-{uuid.uuid4().hex[:8].upper()}"
        
        # Create payment
        payment = VendorPayment(
            payment_reference=payment_reference,
            booking_id=booking_id,
            paid_by_id=user_id,
            amount=payment_data['amount'],
            currency=payment_data.get('currency', booking.currency),
            payment_method=payment_data['payment_method'],
            is_deposit=payment_data.get('is_deposit', False),
            description=payment_data.get('description')
        )
        
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        
        # Update booking deposit status if this is a deposit
        if payment_data.get('is_deposit', False):
            booking.deposit_amount = payment_data['amount']
            booking.deposit_paid = True
            booking.deposit_paid_at = datetime.utcnow()
            self.db.commit()
        
        return payment
    
    def process_payment(
        self, 
        payment_id: int, 
        payment_provider_id: str,
        status: PaymentStatus,
        idempotency_key: Optional[str] = None
    ) -> VendorPayment:
        """Process a payment (called by payment webhook)."""
        payment = self.db.query(VendorPayment).filter(VendorPayment.id == payment_id).first()
        
        if not payment:
            raise NotFoundError("Payment not found")
        
        # If idempotency key is provided, check for duplicate processing
        if idempotency_key:
            manager = IdempotencyManager(self.db)
            # Check if this webhook has already been processed
            existing_result = manager.get_completed_operation(idempotency_key)
            if existing_result:
                # Return the existing payment without processing again
                return payment
        
        payment.payment_provider_id = payment_provider_id
        payment.status = status
        
        if status == PaymentStatus.PAID:
            payment.paid_at = datetime.utcnow()
        elif status == PaymentStatus.FAILED:
            payment.failed_at = datetime.utcnow()
        elif status == PaymentStatus.REFUNDED:
            payment.refunded_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(payment)
        
        # Mark idempotency operation as completed if key was provided
        if idempotency_key:
            manager.complete_operation(
                idempotency_key, 
                payment.id, 
                {"payment_id": payment.id, "status": payment.status.value}
            )
        
        return payment
    
    # Review operations
    def create_review(
        self, 
        vendor_id: int, 
        user_id: int, 
        review_data: Dict[str, Any]
    ) -> VendorReview:
        """Create a review for a vendor."""
        vendor = self.db.query(Vendor).filter(Vendor.id == vendor_id).first()
        
        if not vendor:
            raise NotFoundError("Vendor not found")
        
        # Check if user has a completed booking with this vendor
        booking = None
        if review_data.get('booking_id'):
            booking = self.db.query(VendorBooking).filter(
                VendorBooking.id == review_data['booking_id'],
                VendorBooking.booked_by_id == user_id,
                VendorBooking.vendor_id == vendor_id,
                VendorBooking.status == BookingStatus.COMPLETED
            ).first()
            
            if not booking:
                raise ValidationError("You can only review vendors after a completed booking")
        
        # Check if user already reviewed this vendor
        existing_review = self.db.query(VendorReview).filter(
            VendorReview.vendor_id == vendor_id,
            VendorReview.reviewer_id == user_id
        ).first()
        
        if existing_review:
            raise ValidationError("You have already reviewed this vendor")
        
        # Create review
        review = VendorReview(
            vendor_id=vendor_id,
            reviewer_id=user_id,
            booking_id=review_data.get('booking_id'),
            rating=review_data['rating'],
            title=review_data.get('title'),
            review_text=review_data['review_text'],
            service_quality=review_data.get('service_quality'),
            communication=review_data.get('communication'),
            value_for_money=review_data.get('value_for_money'),
            punctuality=review_data.get('punctuality'),
            is_verified=booking is not None
        )
        
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        
        # Update vendor rating
        self._update_vendor_rating(vendor_id)
        
        return review
    
    def get_vendor_reviews(
        self, 
        vendor_id: int, 
        page: int = 1, 
        per_page: int = 20
    ) -> Tuple[List[VendorReview], int]:
        """Get reviews for a vendor."""
        query = self.db.query(VendorReview).options(
            joinedload(VendorReview.reviewer)
        ).filter(
            VendorReview.vendor_id == vendor_id,
            VendorReview.is_approved == True
        )
        
        total = query.count()
        
        reviews = query.order_by(
            desc(VendorReview.is_featured),
            desc(VendorReview.created_at)
        ).offset((page - 1) * per_page).limit(per_page).all()
        
        return reviews, total
    
    # Portfolio operations
    def add_portfolio_item(
        self, 
        vendor_id: int, 
        user_id: int, 
        portfolio_data: Dict[str, Any]
    ) -> VendorPortfolio:
        """Add a portfolio item to a vendor."""
        vendor = self.db.query(Vendor).filter(Vendor.id == vendor_id).first()
        
        if not vendor:
            raise NotFoundError("Vendor not found")
        
        # Check permissions
        if vendor.user_id != user_id:
            raise AuthorizationError("You don't have permission to add portfolio items to this vendor")
        
        # Create portfolio item
        portfolio_item = VendorPortfolio(
            vendor_id=vendor_id,
            title=portfolio_data['title'],
            description=portfolio_data.get('description'),
            image_url=portfolio_data['image_url'],
            event_type=portfolio_data.get('event_type'),
            event_date=portfolio_data.get('event_date'),
            guest_count=portfolio_data.get('guest_count'),
            is_featured=portfolio_data.get('is_featured', False),
            display_order=portfolio_data.get('display_order', 0)
        )
        
        self.db.add(portfolio_item)
        self.db.commit()
        self.db.refresh(portfolio_item)
        
        return portfolio_item
    
    # Availability operations
    def set_availability(
        self, 
        vendor_id: int, 
        user_id: int, 
        availability_data: List[Dict[str, Any]]
    ) -> List[VendorAvailability]:
        """Set availability for a vendor."""
        vendor = self.db.query(Vendor).filter(Vendor.id == vendor_id).first()
        
        if not vendor:
            raise NotFoundError("Vendor not found")
        
        # Check permissions
        if vendor.user_id != user_id:
            raise AuthorizationError("You don't have permission to set availability for this vendor")
        
        created_availability = []
        
        for avail_data in availability_data:
            # Check if availability already exists for this date
            existing = self.db.query(VendorAvailability).filter(
                VendorAvailability.vendor_id == vendor_id,
                VendorAvailability.date == avail_data['date']
            ).first()
            
            if existing:
                # Update existing
                for field, value in avail_data.items():
                    if hasattr(existing, field):
                        setattr(existing, field, value)
                created_availability.append(existing)
            else:
                # Create new
                availability = VendorAvailability(
                    vendor_id=vendor_id,
                    **avail_data
                )
                self.db.add(availability)
                created_availability.append(availability)
        
        self.db.commit()
        
        return created_availability
    
    def get_vendor_availability(
        self, 
        vendor_id: int, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[VendorAvailability]:
        """Get vendor availability for a date range."""
        return self.db.query(VendorAvailability).filter(
            VendorAvailability.vendor_id == vendor_id,
            VendorAvailability.date >= start_date,
            VendorAvailability.date <= end_date
        ).order_by(VendorAvailability.date).all()
    
    # Statistics and analytics
    def get_vendor_statistics(self, vendor_id: int, user_id: int) -> Dict[str, Any]:
        """Get statistics for a vendor."""
        vendor = self.db.query(Vendor).filter(Vendor.id == vendor_id).first()
        
        if not vendor:
            raise NotFoundError("Vendor not found")
        
        # Check permissions
        if vendor.user_id != user_id:
            raise AuthorizationError("You don't have permission to view statistics for this vendor")
        
        # Get booking statistics
        total_bookings = self.db.query(func.count(VendorBooking.id)).filter(
            VendorBooking.vendor_id == vendor_id
        ).scalar() or 0
        
        completed_bookings = self.db.query(func.count(VendorBooking.id)).filter(
            VendorBooking.vendor_id == vendor_id,
            VendorBooking.status == BookingStatus.COMPLETED
        ).scalar() or 0
        
        cancelled_bookings = self.db.query(func.count(VendorBooking.id)).filter(
            VendorBooking.vendor_id == vendor_id,
            VendorBooking.status == BookingStatus.CANCELLED
        ).scalar() or 0
        
        # Get revenue statistics
        total_revenue = self.db.query(func.sum(VendorPayment.amount)).join(
            VendorBooking, VendorPayment.booking_id == VendorBooking.id
        ).filter(
            VendorBooking.vendor_id == vendor_id,
            VendorPayment.status == PaymentStatus.PAID
        ).scalar() or 0
        
        # Calculate rates
        booking_conversion_rate = 0
        if total_bookings > 0:
            booking_conversion_rate = (completed_bookings / total_bookings) * 100
        
        return {
            "total_bookings": total_bookings,
            "completed_bookings": completed_bookings,
            "cancelled_bookings": cancelled_bookings,
            "total_revenue": float(total_revenue),
            "average_rating": vendor.average_rating,
            "total_reviews": vendor.total_reviews,
            "booking_conversion_rate": booking_conversion_rate,
            "response_rate": 95.0,  # This would be calculated based on response times
            "repeat_customer_rate": 25.0  # This would be calculated based on repeat bookings
        }
    
    # Helper methods
    def _get_event_with_access(self, event_id: int, user_id: int) -> Event:
        """Get event and verify user has access."""
        event = self.db.query(Event).filter(Event.id == event_id).first()
        
        if not event:
            raise NotFoundError("Event not found")
        
        # Check access (creator, collaborator, or invited)
        if event.creator_id != user_id:
            # Check if user is collaborator or invited
            from app.models.event_models import EventInvitation
            invitation = self.db.query(EventInvitation).filter(
                EventInvitation.event_id == event_id,
                EventInvitation.user_id == user_id
            ).first()
            
            if not invitation:
                raise AuthorizationError("You don't have access to this event")
        
        return event
    
    def _check_availability(self, vendor_id: int, service_date: datetime) -> bool:
        """Check if vendor is available on a specific date."""
        availability = self.db.query(VendorAvailability).filter(
            VendorAvailability.vendor_id == vendor_id,
            VendorAvailability.date == service_date.date()
        ).first()
        
        if availability:
            return availability.is_available and not availability.is_blocked
        
        # If no specific availability set, assume available
        return True
    
    def _calculate_service_price(
        self, 
        service: VendorService, 
        guest_count: Optional[int] = None,
        duration_hours: Optional[int] = None
    ) -> float:
        """Calculate service price based on parameters."""
        base_price = service.base_price
        
        if service.service_type == ServiceType.HOURLY and duration_hours:
            return base_price * duration_hours
        elif service.service_type == ServiceType.FIXED_PRICE:
            return base_price
        elif service.service_type == ServiceType.PACKAGE:
            # Package pricing might have guest-based multipliers
            if guest_count and service.max_guests:
                if guest_count > service.max_guests:
                    # Add surcharge for extra guests
                    extra_guests = guest_count - service.max_guests
                    surcharge = extra_guests * (base_price * 0.1)  # 10% per extra guest
                    return base_price + surcharge
            return base_price
        else:
            # Custom quote - return base price as estimate
            return base_price
    
    def _update_vendor_rating(self, vendor_id: int):
        """Update vendor's average rating based on reviews."""
        vendor = self.db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if not vendor:
            return
        
        # Calculate new average rating
        reviews = self.db.query(VendorReview).filter(
            VendorReview.vendor_id == vendor_id,
            VendorReview.is_approved == True
        ).all()
        
        if reviews:
            total_rating = sum(review.rating for review in reviews)
            vendor.average_rating = total_rating / len(reviews)
            vendor.total_reviews = len(reviews)
        else:
            vendor.average_rating = 0.0
            vendor.total_reviews = 0
        
        self.db.commit()

# Global vendor service instance
def get_vendor_service(db: Session) -> VendorService:
    return VendorService(db)