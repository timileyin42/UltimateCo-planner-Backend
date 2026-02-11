from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.deps import get_db, get_current_active_user
from app.core.errors import http_400_bad_request, http_404_not_found, http_403_forbidden
from app.services.vendor_service import VendorService
from app.models.vendor_models import VendorBooking
from sqlalchemy.orm import joinedload
import uuid
from app.models.vendor_models import Vendor, VendorPortfolio
from app.models.vendor_models import VendorService as VendorServiceModel
from app.schemas.vendor import (
    # Vendor schemas
    VendorCreate, VendorUpdate, VendorResponse, VendorListResponse, VendorSearchParams,
    
    # Service schemas
    VendorServiceCreate, VendorServiceUpdate, VendorServiceResponse, VendorServiceListResponse,
    
    # Booking schemas
    VendorBookingCreate, VendorBookingUpdate, VendorBookingResponse, VendorBookingListResponse,
    BookingSearchParams,
    
    # Payment schemas
    VendorPaymentCreate, VendorPaymentResponse,
    
    # Review schemas
    VendorReviewCreate, VendorReviewUpdate, VendorReviewResponse, VendorReviewListResponse,
    
    # Portfolio schemas
    VendorPortfolioCreate, VendorPortfolioUpdate, VendorPortfolioResponse,
    
    # Availability schemas
    VendorAvailabilityCreate, VendorAvailabilityResponse, BulkAvailabilityUpdate,
    
    # Quote and statistics
    VendorQuoteRequest, VendorQuoteResponse, VendorStatistics,
    
    # Contract schemas
    VendorContractCreate, VendorContractResponse,
    
    # Bulk operations
    BulkVendorServiceCreate,
    EventVenueSearchParams,
    EventVenueSearchResponse
)
from app.schemas.location import GeoapifyPlaceSearchParams, GeoapifyPlaceSuggestion, EventPlaceSearchParams
from app.models.user_models import User
from app.models.vendor_models import VendorCategory, BookingStatus, PaymentStatus
from datetime import datetime, timedelta
from app.services.gcp_storage_service import gcp_storage_service

vendors_router = APIRouter()

# Vendor profile endpoints
@vendors_router.post("/profile", response_model=VendorResponse)
async def create_vendor_profile(
    vendor_data: VendorCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a vendor profile for the current user"""
    try:
        vendor_service = VendorService(db)
        vendor = vendor_service.create_vendor(current_user.id, vendor_data.model_dump())
        
        return VendorResponse.model_validate(vendor)
        
    except Exception as e:
        if "already has a vendor profile" in str(e):
            raise http_400_bad_request("User already has a vendor profile")
        else:
            raise http_400_bad_request("Failed to create vendor profile")

@vendors_router.get("/profile", response_model=VendorResponse)
async def get_my_vendor_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get the current user's vendor profile"""
    try:
        
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        
        if not vendor:
            raise http_404_not_found("Vendor profile not found")
        
        return VendorResponse.model_validate(vendor)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request("Failed to get vendor profile")

@vendors_router.put("/profile", response_model=VendorResponse)
async def update_vendor_profile(
    update_data: VendorUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update the current user's vendor profile"""
    try:
        
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        
        if not vendor:
            raise http_404_not_found("Vendor profile not found")
        
        vendor_service = VendorService(db)
        updated_vendor = vendor_service.update_vendor(
            vendor.id, current_user.id, update_data.model_dump(exclude_unset=True)
        )
        
        return VendorResponse.model_validate(updated_vendor)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to update vendor profile")

# Public vendor endpoints
@vendors_router.get("/search", response_model=VendorListResponse)
async def search_vendors(
    search_params: VendorSearchParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Search for vendors with filters"""
    try:
        vendor_service = VendorService(db)
        vendors, total = vendor_service.search_vendors(search_params.model_dump())
        
        vendor_responses = [VendorResponse.model_validate(vendor) for vendor in vendors]
        
        return VendorListResponse(
            vendors=vendor_responses,
            total=total,
            page=search_params.page,
            per_page=search_params.per_page,
            has_next=(search_params.page * search_params.per_page) < total,
            has_prev=search_params.page > 1
        )
        
    except Exception as e:
        raise http_400_bad_request("Failed to search vendors")

@vendors_router.get("/places/search", response_model=List[GeoapifyPlaceSuggestion])
async def search_places_geoapify(
    search_params: GeoapifyPlaceSearchParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Search for venues and restaurants via Geoapify"""
    try:
        vendor_service = VendorService(db)
        return await vendor_service.search_geoapify_places(search_params.model_dump())
    except Exception as e:
        raise http_400_bad_request("Failed to search places")

@vendors_router.get("/events/{event_id}/places", response_model=List[GeoapifyPlaceSuggestion])
async def search_event_places_geoapify(
    event_id: int,
    search_params: EventPlaceSearchParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Search for places based on an event venue"""
    try:
        vendor_service = VendorService(db)
        return await vendor_service.search_event_places(
            event_id, current_user.id, search_params.model_dump()
        )
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access" in str(e).lower() or "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to search event places")

@vendors_router.get("/events/{event_id}/venue-search", response_model=EventVenueSearchResponse)
async def search_event_places_and_vendors(
    event_id: int,
    search_params: EventVenueSearchParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Search external places and internal vendors based on an event venue"""
    try:
        vendor_service = VendorService(db)
        result = await vendor_service.search_event_places_and_vendors(
            event_id, current_user.id, search_params.model_dump()
        )

        vendor_responses = [VendorResponse.model_validate(vendor) for vendor in result["vendors"]]
        vendor_list = VendorListResponse(
            vendors=vendor_responses,
            total=result["total"],
            page=result["page"],
            per_page=result["per_page"],
            has_next=(result["page"] * result["per_page"]) < result["total"],
            has_prev=result["page"] > 1
        )

        return EventVenueSearchResponse(
            places=result["places"],
            vendors=vendor_list
        )
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access" in str(e).lower() or "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to search event venues")

@vendors_router.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor(
    vendor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific vendor by ID"""
    try:
        vendor_service = VendorService(db)
        vendor = vendor_service.get_vendor(vendor_id)
        
        if not vendor:
            raise http_404_not_found("Vendor not found")
        
        return VendorResponse.model_validate(vendor)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request("Failed to get vendor")

# Vendor service endpoints
@vendors_router.post("/{vendor_id}/services", response_model=VendorServiceResponse)
async def create_vendor_service(
    vendor_id: int,
    service_data: VendorServiceCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new service for a vendor"""
    try:
        vendor_service = VendorService(db)
        service = vendor_service.create_vendor_service(
            vendor_id, current_user.id, service_data.model_dump()
        )
        
        return VendorServiceResponse.model_validate(service)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to create vendor service")

@vendors_router.get("/{vendor_id}/services", response_model=List[VendorServiceResponse])
async def get_vendor_services(
    vendor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all services for a vendor"""
    try:
        vendor_service = VendorService(db)
        services = vendor_service.get_vendor_services(vendor_id)
        
        return [VendorServiceResponse.model_validate(service) for service in services]
        
    except Exception as e:
        raise http_400_bad_request("Failed to get vendor services")

@vendors_router.post("/{vendor_id}/services/bulk", response_model=List[VendorServiceResponse])
async def bulk_create_vendor_services(
    vendor_id: int,
    bulk_data: BulkVendorServiceCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Bulk create services for a vendor"""
    try:
        vendor_service = VendorService(db)
        created_services = []
        
        for service_data in bulk_data.services:
            service = vendor_service.create_vendor_service(
                vendor_id, current_user.id, service_data.model_dump()
            )
            created_services.append(VendorServiceResponse.model_validate(service))
        
        return created_services
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to bulk create vendor services")

# Booking endpoints
@vendors_router.post("/services/{service_id}/book", response_model=VendorBookingResponse)
async def create_booking(
    service_id: int,
    booking_data: VendorBookingCreate,
    event_id: int = Query(..., description="Event ID for this booking"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new booking for a vendor service"""
    try:
        vendor_service = VendorService(db)
        booking = vendor_service.create_booking(
            service_id, event_id, current_user.id, booking_data.model_dump()
        )
        
        return VendorBookingResponse.model_validate(booking)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "not available" in str(e).lower():
            raise http_400_bad_request(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to create booking")

@vendors_router.get("/bookings/{booking_id}", response_model=VendorBookingResponse)
async def get_booking(
    booking_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific booking by ID"""
    try:
        vendor_service = VendorService(db)
        booking = vendor_service.get_booking(booking_id, current_user.id)
        
        if not booking:
            raise http_404_not_found("Booking not found")
        
        return VendorBookingResponse.model_validate(booking)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get booking")

@vendors_router.put("/bookings/{booking_id}/status", response_model=VendorBookingResponse)
async def update_booking_status(
    booking_id: int,
    status: BookingStatus = Query(..., description="New booking status"),
    reason: Optional[str] = Query(None, description="Reason for status change"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update booking status"""
    try:
        vendor_service = VendorService(db)
        booking = vendor_service.update_booking_status(
            booking_id, current_user.id, status, reason
        )
        
        return VendorBookingResponse.model_validate(booking)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to update booking status")

@vendors_router.get("/my-bookings", response_model=VendorBookingListResponse)
async def get_my_bookings(
    search_params: BookingSearchParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get bookings for the current user (as client)"""
    try:
        
        # Build query
        query = db.query(VendorBooking).options(
            joinedload(VendorBooking.vendor),
            joinedload(VendorBooking.service),
            joinedload(VendorBooking.booked_by)
        ).filter(VendorBooking.booked_by_id == current_user.id)
        
        # Apply filters
        if search_params.status:
            query = query.filter(VendorBooking.status == search_params.status)
        
        if search_params.vendor_id:
            query = query.filter(VendorBooking.vendor_id == search_params.vendor_id)
        
        if search_params.service_date_from:
            query = query.filter(VendorBooking.service_date >= search_params.service_date_from)
        
        if search_params.service_date_to:
            query = query.filter(VendorBooking.service_date <= search_params.service_date_to)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        bookings = query.order_by(VendorBooking.created_at.desc()).offset(
            (search_params.page - 1) * search_params.per_page
        ).limit(search_params.per_page).all()
        
        booking_responses = [VendorBookingResponse.model_validate(booking) for booking in bookings]
        
        return VendorBookingListResponse(
            bookings=booking_responses,
            total=total,
            page=search_params.page,
            per_page=search_params.per_page,
            has_next=(search_params.page * search_params.per_page) < total,
            has_prev=search_params.page > 1
        )
        
    except Exception as e:
        raise http_400_bad_request("Failed to get bookings")

@vendors_router.get("/vendor-bookings", response_model=VendorBookingListResponse)
async def get_vendor_bookings(
    search_params: BookingSearchParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get bookings for the current user's vendor (as vendor)"""
    try:
        
        # Get user's vendor profile
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        
        if not vendor:
            raise http_404_not_found("Vendor profile not found")
        
        # Build query
        query = db.query(VendorBooking).options(
            joinedload(VendorBooking.vendor),
            joinedload(VendorBooking.service),
            joinedload(VendorBooking.booked_by)
        ).filter(VendorBooking.vendor_id == vendor.id)
        
        # Apply filters
        if search_params.status:
            query = query.filter(VendorBooking.status == search_params.status)
        
        if search_params.service_date_from:
            query = query.filter(VendorBooking.service_date >= search_params.service_date_from)
        
        if search_params.service_date_to:
            query = query.filter(VendorBooking.service_date <= search_params.service_date_to)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        bookings = query.order_by(VendorBooking.created_at.desc()).offset(
            (search_params.page - 1) * search_params.per_page
        ).limit(search_params.per_page).all()
        
        booking_responses = [VendorBookingResponse.model_validate(booking) for booking in bookings]
        
        return VendorBookingListResponse(
            bookings=booking_responses,
            total=total,
            page=search_params.page,
            per_page=search_params.per_page,
            has_next=(search_params.page * search_params.per_page) < total,
            has_prev=search_params.page > 1
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request("Failed to get vendor bookings")

# Payment endpoints
@vendors_router.post("/bookings/{booking_id}/payments", response_model=VendorPaymentResponse)
async def create_payment(
    booking_id: int,
    payment_data: VendorPaymentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a payment for a booking"""
    try:
        vendor_service = VendorService(db)
        
        # Extract payment data and pass idempotency_key separately
        payment_dict = payment_data.model_dump()
        idempotency_key = payment_dict.pop('idempotency_key', None)
        
        payment = vendor_service.create_payment(
            booking_id, current_user.id, payment_dict, idempotency_key=idempotency_key
        )
        
        return VendorPaymentResponse.model_validate(payment)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to create payment")

@vendors_router.post("/payments/{payment_id}/process")
async def process_payment_webhook(
    payment_id: int,
    payment_provider_id: str = Query(..., description="Payment provider ID"),
    status: PaymentStatus = Query(..., description="Payment status"),
    idempotency_key: Optional[str] = Query(None, description="Idempotency key for webhook deduplication"),
    db: Session = Depends(get_db)
):
    """Process payment webhook (called by payment provider)"""
    try:
        vendor_service = VendorService(db)
        payment = vendor_service.process_payment(
            payment_id, payment_provider_id, status, idempotency_key=idempotency_key
        )
        
        return {"message": "Payment processed successfully", "payment_id": payment.id}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request("Failed to process payment")

# Review endpoints
@vendors_router.post("/{vendor_id}/reviews", response_model=VendorReviewResponse)
async def create_review(
    vendor_id: int,
    review_data: VendorReviewCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a review for a vendor"""
    try:
        vendor_service = VendorService(db)
        review = vendor_service.create_review(
            vendor_id, current_user.id, review_data.model_dump()
        )
        
        return VendorReviewResponse.model_validate(review)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "already reviewed" in str(e).lower() or "only review" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request("Failed to create review")

@vendors_router.get("/{vendor_id}/reviews", response_model=VendorReviewListResponse)
async def get_vendor_reviews(
    vendor_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get reviews for a vendor"""
    try:
        vendor_service = VendorService(db)
        reviews, total = vendor_service.get_vendor_reviews(vendor_id, page, per_page)
        
        review_responses = [VendorReviewResponse.model_validate(review) for review in reviews]
        
        return VendorReviewListResponse(
            reviews=review_responses,
            total=total,
            page=page,
            per_page=per_page,
            has_next=(page * per_page) < total,
            has_prev=page > 1
        )
        
    except Exception as e:
        raise http_400_bad_request("Failed to get vendor reviews")

# Portfolio endpoints
@vendors_router.post("/{vendor_id}/portfolio", response_model=VendorPortfolioResponse)
async def add_portfolio_item(
    vendor_id: int,
    portfolio_data: VendorPortfolioCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add a portfolio item to a vendor"""
    try:
        vendor_service = VendorService(db)
        portfolio_item = vendor_service.add_portfolio_item(
            vendor_id, current_user.id, portfolio_data.model_dump()
        )
        
        return VendorPortfolioResponse.model_validate(portfolio_item)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to add portfolio item")

@vendors_router.get("/{vendor_id}/portfolio", response_model=List[VendorPortfolioResponse])
async def get_vendor_portfolio(
    vendor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get portfolio items for a vendor"""
    try:
        
        portfolio_items = db.query(VendorPortfolio).filter(
            VendorPortfolio.vendor_id == vendor_id
        ).order_by(
            VendorPortfolio.is_featured.desc(),
            VendorPortfolio.display_order,
            VendorPortfolio.created_at.desc()
        ).all()
        
        return [VendorPortfolioResponse.model_validate(item) for item in portfolio_items]
        
    except Exception as e:
        raise http_400_bad_request("Failed to get vendor portfolio")

# Availability endpoints
@vendors_router.post("/{vendor_id}/availability", response_model=List[VendorAvailabilityResponse])
async def set_vendor_availability(
    vendor_id: int,
    availability_data: BulkAvailabilityUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Set availability for a vendor"""
    try:
        vendor_service = VendorService(db)
        availability = vendor_service.set_availability(
            vendor_id, current_user.id, 
            [avail.model_dump() for avail in availability_data.availability_updates]
        )
        
        return [VendorAvailabilityResponse.model_validate(avail) for avail in availability]
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to set vendor availability")

@vendors_router.get("/{vendor_id}/availability", response_model=List[VendorAvailabilityResponse])
async def get_vendor_availability(
    vendor_id: int,
    start_date: datetime = Query(..., description="Start date for availability check"),
    end_date: datetime = Query(..., description="End date for availability check"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get vendor availability for a date range"""
    try:
        vendor_service = VendorService(db)
        availability = vendor_service.get_vendor_availability(vendor_id, start_date, end_date)
        
        return [VendorAvailabilityResponse.model_validate(avail) for avail in availability]
        
    except Exception as e:
        raise http_400_bad_request("Failed to get vendor availability")

# Quote request endpoints
@vendors_router.post("/quote-request", response_model=VendorQuoteResponse)
async def request_quote(
    quote_request: VendorQuoteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Request a quote from a vendor"""
    try:
        vendor_service = VendorService(db)
        
        # Create quote request in database
        quote = vendor_service.create_quote_request(
            service_id=quote_request.service_id,
            user_id=current_user.id,
            quote_data=quote_request.model_dump()
        )
        
        # Load relationships for response
        db.refresh(quote)
        
        return VendorQuoteResponse(
            quote_id=quote.quote_id,
            vendor=VendorResponse.model_validate(quote.vendor),
            service=VendorServiceResponse.model_validate(quote.service),
            quoted_price=quote.quoted_price,
            quote_details=quote.quote_details,
            valid_until=quote.valid_until,
            response_time_hours=quote.response_time_hours,
            status=quote.status
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request(f"Failed to request quote: {str(e)}")

@vendors_router.put("/quotes/{quote_id}/respond", response_model=VendorQuoteResponse)
async def respond_to_quote(
    quote_id: int,
    quoted_price: float = Query(..., description="Price quoted by vendor"),
    quote_details: Optional[str] = Query(None, description="Details of the quote"),
    quote_notes: Optional[str] = Query(None, description="Additional notes"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Vendor responds to a quote request with pricing"""
    try:
        vendor_service = VendorService(db)
        
        quote = vendor_service.update_quote_response(
            quote_id=quote_id,
            vendor_user_id=current_user.id,
            quoted_price=quoted_price,
            quote_details=quote_details,
            quote_notes=quote_notes
        )
        
        return VendorQuoteResponse(
            quote_id=quote.quote_id,
            vendor=VendorResponse.model_validate(quote.vendor),
            service=VendorServiceResponse.model_validate(quote.service),
            quoted_price=quote.quoted_price,
            quote_details=quote.quote_details,
            valid_until=quote.valid_until,
            response_time_hours=quote.response_time_hours,
            status=quote.status
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower() or "authorization" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request(f"Failed to respond to quote: {str(e)}")

@vendors_router.post("/quotes/{quote_id}/accept", response_model=VendorQuoteResponse)
async def accept_quote(
    quote_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Client accepts a quote from vendor"""
    try:
        vendor_service = VendorService(db)
        
        quote = vendor_service.accept_quote(quote_id, current_user.id)
        
        return VendorQuoteResponse(
            quote_id=quote.quote_id,
            vendor=VendorResponse.model_validate(quote.vendor),
            service=VendorServiceResponse.model_validate(quote.service),
            quoted_price=quote.quoted_price,
            quote_details=quote.quote_details,
            valid_until=quote.valid_until,
            response_time_hours=quote.response_time_hours,
            status=quote.status
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower() or "authorization" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request(f"Failed to accept quote: {str(e)}")

@vendors_router.post("/quotes/{quote_id}/decline", response_model=VendorQuoteResponse)
async def decline_quote(
    quote_id: int,
    decline_reason: Optional[str] = Query(None, description="Reason for declining"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Client or vendor declines a quote"""
    try:
        vendor_service = VendorService(db)
        
        quote = vendor_service.decline_quote(quote_id, current_user.id, decline_reason)
        
        return VendorQuoteResponse(
            quote_id=quote.quote_id,
            vendor=VendorResponse.model_validate(quote.vendor),
            service=VendorServiceResponse.model_validate(quote.service),
            quoted_price=quote.quoted_price,
            quote_details=quote.quote_details,
            valid_until=quote.valid_until,
            response_time_hours=quote.response_time_hours,
            status=quote.status
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower() or "authorization" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request(f"Failed to decline quote: {str(e)}")

@vendors_router.get("/my-quotes", response_model=List[VendorQuoteResponse])
async def get_my_quote_requests(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all quote requests made by the current user"""
    try:
        vendor_service = VendorService(db)
        
        quotes, total = vendor_service.get_user_quotes(current_user.id, page=page, per_page=per_page)
        
        return [
            VendorQuoteResponse(
                quote_id=quote.quote_id,
                vendor=VendorResponse.model_validate(quote.vendor),
                service=VendorServiceResponse.model_validate(quote.service),
                quoted_price=quote.quoted_price,
                quote_details=quote.quote_details,
                valid_until=quote.valid_until,
                response_time_hours=quote.response_time_hours,
                status=quote.status
            )
            for quote in quotes
        ]
        
    except Exception as e:
        raise http_400_bad_request(f"Failed to get quote requests: {str(e)}")

@vendors_router.get("/vendor-quotes", response_model=List[VendorQuoteResponse])
async def get_vendor_quote_requests(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all quote requests received by the current user's vendor"""
    try:
        vendor_service = VendorService(db)
        
        quotes, total = vendor_service.get_vendor_quotes(current_user.id, page=page, per_page=per_page)
        
        return [
            VendorQuoteResponse(
                quote_id=quote.quote_id,
                vendor=VendorResponse.model_validate(quote.vendor),
                service=VendorServiceResponse.model_validate(quote.service),
                quoted_price=quote.quoted_price,
                quote_details=quote.quote_details,
                valid_until=quote.valid_until,
                response_time_hours=quote.response_time_hours,
                status=quote.status
            )
            for quote in quotes
        ]
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request(f"Failed to get vendor quotes: {str(e)}")

# Statistics endpoints
@vendors_router.get("/my-statistics", response_model=VendorStatistics)
async def get_my_vendor_statistics(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get statistics for the current user's vendor"""
    try:
        
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        
        if not vendor:
            raise http_404_not_found("Vendor profile not found")
        
        vendor_service = VendorService(db)
        statistics = vendor_service.get_vendor_statistics(vendor.id, current_user.id)
        
        return VendorStatistics(**statistics)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get vendor statistics")

# Categories endpoint
@vendors_router.get("/categories")
async def get_vendor_categories(
    current_user: User = Depends(get_current_active_user)
):
    """Get available vendor categories"""
    return {
        "categories": [
            {
                "name": "venue",
                "display_name": "Venues",
                "description": "Event venues and locations",
                "icon": "🏢"
            },
            {
                "name": "catering",
                "display_name": "Catering",
                "description": "Food and beverage services",
                "icon": "🍽️"
            },
            {
                "name": "photography",
                "display_name": "Photography",
                "description": "Event photography services",
                "icon": "📸"
            },
            {
                "name": "videography",
                "display_name": "Videography",
                "description": "Event videography services",
                "icon": "🎥"
            },
            {
                "name": "music_dj",
                "display_name": "Music & DJ",
                "description": "Music and DJ services",
                "icon": "🎵"
            },
            {
                "name": "entertainment",
                "display_name": "Entertainment",
                "description": "Entertainment and performers",
                "icon": "🎭"
            },
            {
                "name": "florist",
                "display_name": "Florist",
                "description": "Floral arrangements and decorations",
                "icon": "🌸"
            },
            {
                "name": "decoration",
                "display_name": "Decoration",
                "description": "Event decoration services",
                "icon": "🎨"
            },
            {
                "name": "transportation",
                "display_name": "Transportation",
                "description": "Transportation services",
                "icon": "🚗"
            },
            {
                "name": "security",
                "display_name": "Security",
                "description": "Event security services",
                "icon": "🛡️"
            },
            {
                "name": "cleaning",
                "display_name": "Cleaning",
                "description": "Cleaning and maintenance services",
                "icon": "🧹"
            },
            {
                "name": "equipment_rental",
                "display_name": "Equipment Rental",
                "description": "Equipment and furniture rental",
                "icon": "📦"
            },
            {
                "name": "other",
                "display_name": "Other Services",
                "description": "Other event-related services",
                "icon": "⚙️"
            }
        ]
    }

# File upload endpoint
@vendors_router.post("/upload-image")
async def upload_vendor_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """Upload an image for vendor profile or portfolio"""
    try:
        
        # Read file content
        file_content = await file.read()
        
        # Validate file
        validation = gcp_storage_service.validate_file(
            filename=file.filename,
            file_size=len(file_content),
            content_type=file.content_type,
            allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp'],
            max_size_mb=100
        )
        
        if not validation["is_valid"]:
            raise http_400_bad_request(f"File validation failed: {', '.join(validation['errors'])}")
        
        # Upload to GCP Storage
        upload_result = await gcp_storage_service.upload_file(
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type,
            folder="vendors",
            user_id=current_user.id
        )
        
        return {
            "message": "Image uploaded successfully",
            "url": upload_result["file_url"],
            "filename": upload_result["filename"],
            "unique_filename": upload_result["unique_filename"],
            "content_type": upload_result["content_type"],
            "file_size": upload_result["file_size"],
            "uploaded_at": upload_result["uploaded_at"]
        }
        
    except Exception as e:
        if "validation failed" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request("Failed to upload image")
