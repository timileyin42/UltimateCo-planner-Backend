from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc
from datetime import datetime, timedelta
from app.models.vendor_models import (
    Vendor, VendorService, VendorBooking, VendorPayment, VendorReview,
    VendorPortfolio, VendorAvailability, VendorContract,
    VendorCategory, VendorStatus, BookingStatus, PaymentStatus
)
from app.models.user_models import User
from app.schemas.pagination import PaginationParams, SortParams

class VendorRepository:
    """Repository for vendor data access operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Vendor CRUD operations
    def get_by_id(
        self, 
        vendor_id: int, 
        include_relations: bool = False
    ) -> Optional[Vendor]:
        """Get vendor by ID with optional relation loading"""
        query = self.db.query(Vendor).filter(Vendor.id == vendor_id)
        
        if include_relations:
            query = query.options(
                joinedload(Vendor.user),
                joinedload(Vendor.services),
                joinedload(Vendor.reviews),
                joinedload(Vendor.portfolio_items)
            )
        
        return query.first()
    
    def get_by_user_id(self, user_id: int) -> Optional[Vendor]:
        """Get vendor by user ID"""
        return self.db.query(Vendor).filter(Vendor.user_id == user_id).first()
    
    def get_by_email(self, email: str) -> Optional[Vendor]:
        """Get vendor by email"""
        return self.db.query(Vendor).filter(Vendor.email == email).first()
    
    def search_vendors(
        self,
        search_params: Dict[str, Any],
        pagination: PaginationParams
    ) -> Tuple[List[Vendor], int]:
        """Search vendors with filters and pagination"""
        query = self.db.query(Vendor).options(
            joinedload(Vendor.user)
        ).filter(Vendor.status.in_([VendorStatus.ACTIVE, VendorStatus.VERIFIED]))
        
        # Apply search filters
        if search_params.get('query'):
            search_term = f"%{search_params['query']}%"
            query = query.filter(
                or_(
                    Vendor.business_name.ilike(search_term),
                    Vendor.display_name.ilike(search_term),
                    Vendor.description.ilike(search_term)
                )
            )
        
        if search_params.get('category'):
            query = query.filter(Vendor.category == search_params['category'])
        
        if search_params.get('city'):
            query = query.filter(Vendor.city.ilike(f"%{search_params['city']}%"))
        
        if search_params.get('state'):
            query = query.filter(Vendor.state.ilike(f"%{search_params['state']}%"))
        
        if search_params.get('country'):
            query = query.filter(Vendor.country.ilike(f"%{search_params['country']}%"))
        
        if search_params.get('min_rating'):
            query = query.filter(Vendor.average_rating >= search_params['min_rating'])
        
        if search_params.get('max_price'):
            query = query.filter(Vendor.base_price <= search_params['max_price'])
        
        if search_params.get('verified_only'):
            query = query.filter(Vendor.status == VendorStatus.VERIFIED)
        
        # Order by featured first, then rating
        if search_params.get('featured_first', True):
            query = query.order_by(
                desc(Vendor.is_featured),
                desc(Vendor.average_rating),
                desc(Vendor.total_reviews)
            )
        else:
            query = query.order_by(
                desc(Vendor.average_rating),
                desc(Vendor.total_reviews)
            )
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        vendors = query.offset(pagination.offset).limit(pagination.limit).all()
        
        return vendors, total
    
    def create(self, vendor_data: Dict[str, Any]) -> Vendor:
        """Create a new vendor"""
        vendor = Vendor(**vendor_data)
        self.db.add(vendor)
        self.db.commit()
        self.db.refresh(vendor)
        return vendor
    
    def update(self, vendor_id: int, update_data: Dict[str, Any]) -> Optional[Vendor]:
        """Update vendor by ID"""
        vendor = self.get_by_id(vendor_id)
        if not vendor:
            return None
        
        for field, value in update_data.items():
            if hasattr(vendor, field):
                setattr(vendor, field, value)
        
        self.db.commit()
        self.db.refresh(vendor)
        return vendor
    
    def delete(self, vendor_id: int) -> bool:
        """Soft delete vendor by ID"""
        vendor = self.get_by_id(vendor_id)
        if not vendor:
            return False
        
        vendor.status = VendorStatus.INACTIVE
        self.db.commit()
        return True
    
    # Vendor Service operations
    def get_vendor_services(self, vendor_id: int) -> List[VendorService]:
        """Get all services for a vendor"""
        return self.db.query(VendorService).filter(
            VendorService.vendor_id == vendor_id,
            VendorService.is_active == True
        ).all()
    
    def get_service_by_id(self, service_id: int) -> Optional[VendorService]:
        """Get vendor service by ID"""
        return self.db.query(VendorService).options(
            joinedload(VendorService.vendor)
        ).filter(VendorService.id == service_id).first()
    
    def create_service(self, service_data: Dict[str, Any]) -> VendorService:
        """Create a new vendor service"""
        service = VendorService(**service_data)
        self.db.add(service)
        self.db.commit()
        self.db.refresh(service)
        return service
    
    # Booking operations
    def get_booking_by_id(self, booking_id: int) -> Optional[VendorBooking]:
        """Get booking by ID with relations"""
        return self.db.query(VendorBooking).options(
            joinedload(VendorBooking.vendor),
            joinedload(VendorBooking.service),
            joinedload(VendorBooking.booked_by),
            joinedload(VendorBooking.payments)
        ).filter(VendorBooking.id == booking_id).first()
    
    def get_vendor_bookings(
        self,
        vendor_id: int,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[VendorBooking], int]:
        """Get bookings for a vendor"""
        query = self.db.query(VendorBooking).options(
            joinedload(VendorBooking.service),
            joinedload(VendorBooking.booked_by)
        ).filter(VendorBooking.vendor_id == vendor_id)
        
        if filters:
            if filters.get('status'):
                query = query.filter(VendorBooking.status == filters['status'])
            
            if filters.get('service_date_from'):
                query = query.filter(VendorBooking.service_date >= filters['service_date_from'])
            
            if filters.get('service_date_to'):
                query = query.filter(VendorBooking.service_date <= filters['service_date_to'])
        
        total = query.count()
        bookings = query.order_by(desc(VendorBooking.created_at)).offset(
            pagination.offset
        ).limit(pagination.limit).all()
        
        return bookings, total
    
    def get_user_bookings(
        self,
        user_id: int,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[VendorBooking], int]:
        """Get bookings for a user"""
        query = self.db.query(VendorBooking).options(
            joinedload(VendorBooking.vendor),
            joinedload(VendorBooking.service)
        ).filter(VendorBooking.booked_by_id == user_id)
        
        if filters:
            if filters.get('status'):
                query = query.filter(VendorBooking.status == filters['status'])
            
            if filters.get('vendor_id'):
                query = query.filter(VendorBooking.vendor_id == filters['vendor_id'])
        
        total = query.count()
        bookings = query.order_by(desc(VendorBooking.created_at)).offset(
            pagination.offset
        ).limit(pagination.limit).all()
        
        return bookings, total
    
    def create_booking(self, booking_data: Dict[str, Any]) -> VendorBooking:
        """Create a new booking"""
        booking = VendorBooking(**booking_data)
        self.db.add(booking)
        self.db.commit()
        self.db.refresh(booking)
        return booking
    
    def update_booking(self, booking_id: int, update_data: Dict[str, Any]) -> Optional[VendorBooking]:
        """Update booking by ID"""
        booking = self.get_booking_by_id(booking_id)
        if not booking:
            return None
        
        for field, value in update_data.items():
            if hasattr(booking, field):
                setattr(booking, field, value)
        
        self.db.commit()
        self.db.refresh(booking)
        return booking
    
    # Payment operations
    def create_payment(self, payment_data: Dict[str, Any]) -> VendorPayment:
        """Create a new payment"""
        payment = VendorPayment(**payment_data)
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        return payment
    
    def get_payment_by_id(self, payment_id: int) -> Optional[VendorPayment]:
        """Get payment by ID"""
        return self.db.query(VendorPayment).filter(VendorPayment.id == payment_id).first()
    
    def update_payment(self, payment_id: int, update_data: Dict[str, Any]) -> Optional[VendorPayment]:
        """Update payment by ID"""
        payment = self.get_payment_by_id(payment_id)
        if not payment:
            return None
        
        for field, value in update_data.items():
            if hasattr(payment, field):
                setattr(payment, field, value)
        
        self.db.commit()
        self.db.refresh(payment)
        return payment
    
    # Review operations
    def get_vendor_reviews(
        self,
        vendor_id: int,
        pagination: PaginationParams
    ) -> Tuple[List[VendorReview], int]:
        """Get reviews for a vendor"""
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
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return reviews, total
    
    def create_review(self, review_data: Dict[str, Any]) -> VendorReview:
        """Create a new review"""
        review = VendorReview(**review_data)
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review
    
    def get_user_review_for_vendor(self, user_id: int, vendor_id: int) -> Optional[VendorReview]:
        """Check if user already reviewed a vendor"""
        return self.db.query(VendorReview).filter(
            VendorReview.vendor_id == vendor_id,
            VendorReview.reviewer_id == user_id
        ).first()
    
    # Portfolio operations
    def get_vendor_portfolio(self, vendor_id: int) -> List[VendorPortfolio]:
        """Get portfolio items for a vendor"""
        return self.db.query(VendorPortfolio).filter(
            VendorPortfolio.vendor_id == vendor_id
        ).order_by(
            VendorPortfolio.is_featured.desc(),
            VendorPortfolio.display_order,
            VendorPortfolio.created_at.desc()
        ).all()
    
    def create_portfolio_item(self, portfolio_data: Dict[str, Any]) -> VendorPortfolio:
        """Create a new portfolio item"""
        portfolio_item = VendorPortfolio(**portfolio_data)
        self.db.add(portfolio_item)
        self.db.commit()
        self.db.refresh(portfolio_item)
        return portfolio_item
    
    # Availability operations
    def get_vendor_availability(
        self,
        vendor_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[VendorAvailability]:
        """Get vendor availability for a date range"""
        return self.db.query(VendorAvailability).filter(
            VendorAvailability.vendor_id == vendor_id,
            VendorAvailability.date >= start_date,
            VendorAvailability.date <= end_date
        ).order_by(VendorAvailability.date).all()
    
    def set_availability(self, availability_data: Dict[str, Any]) -> VendorAvailability:
        """Set vendor availability"""
        # Check if availability already exists for this date
        existing = self.db.query(VendorAvailability).filter(
            VendorAvailability.vendor_id == availability_data['vendor_id'],
            VendorAvailability.date == availability_data['date']
        ).first()
        
        if existing:
            # Update existing
            for field, value in availability_data.items():
                if hasattr(existing, field):
                    setattr(existing, field, value)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            # Create new
            availability = VendorAvailability(**availability_data)
            self.db.add(availability)
            self.db.commit()
            self.db.refresh(availability)
            return availability
    
    def check_availability(self, vendor_id: int, service_date: datetime) -> bool:
        """Check if vendor is available on a specific date"""
        availability = self.db.query(VendorAvailability).filter(
            VendorAvailability.vendor_id == vendor_id,
            VendorAvailability.date == service_date.date()
        ).first()
        
        if availability:
            return availability.is_available and not availability.is_blocked
        
        # If no specific availability set, assume available
        return True
    
    # Statistics operations
    def get_vendor_statistics(self, vendor_id: int) -> Dict[str, Any]:
        """Get comprehensive statistics for a vendor"""
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
        
        # Get vendor info for ratings
        vendor = self.get_by_id(vendor_id)
        
        # Calculate rates
        booking_conversion_rate = 0
        if total_bookings > 0:
            booking_conversion_rate = (completed_bookings / total_bookings) * 100
        
        return {
            "total_bookings": total_bookings,
            "completed_bookings": completed_bookings,
            "cancelled_bookings": cancelled_bookings,
            "total_revenue": float(total_revenue),
            "average_rating": vendor.average_rating if vendor else 0.0,
            "total_reviews": vendor.total_reviews if vendor else 0,
            "booking_conversion_rate": booking_conversion_rate,
            "response_rate": 95.0,  # This would be calculated based on response times
            "repeat_customer_rate": 25.0  # This would be calculated based on repeat bookings
        }
    
    def update_vendor_rating(self, vendor_id: int):
        """Update vendor's average rating based on reviews"""
        vendor = self.get_by_id(vendor_id)
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
    
    def exists_by_email(self, email: str, exclude_vendor_id: Optional[int] = None) -> bool:
        """Check if vendor exists by email"""
        query = self.db.query(Vendor).filter(Vendor.email == email)
        
        if exclude_vendor_id:
            query = query.filter(Vendor.id != exclude_vendor_id)
        
        return query.first() is not None
    
    def count_total(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count total vendors with optional filters"""
        query = self.db.query(Vendor)
        
        if filters:
            if filters.get('status'):
                query = query.filter(Vendor.status == filters['status'])
            
            if filters.get('category'):
                query = query.filter(Vendor.category == filters['category'])
        
        return query.count()