import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.services.vendor_service import VendorService
from app.models.vendor_models import (
    Vendor, VendorService as VendorServiceModel, VendorBooking, VendorPayment,
    VendorReview, VendorPortfolio, VendorAvailability, VendorContract,
    VendorCategory, VendorStatus, BookingStatus, PaymentStatus, ServiceType
)
from app.models.user_models import User
from app.models.event_models import Event
from app.core.errors import NotFoundError, ValidationError, AuthorizationError

class TestVendorService:
    """Test cases for VendorService."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def vendor_service(self, mock_db):
        """Create VendorService instance with mocked database."""
        return VendorService(mock_db)
    
    @pytest.fixture
    def mock_user(self):
        """Mock user for testing."""
        user = Mock(spec=User)
        user.id = 1
        user.full_name = "Test User"
        user.email = "test@example.com"
        return user
    
    @pytest.fixture
    def mock_event(self):
        """Mock event for testing."""
        event = Mock(spec=Event)
        event.id = 1
        event.title = "Test Event"
        event.creator_id = 1
        event.start_datetime = datetime.utcnow() + timedelta(days=7)
        event.collaborators = []
        return event
    
    @pytest.fixture
    def mock_vendor(self):
        """Mock vendor for testing."""
        vendor = Mock(spec=Vendor)
        vendor.id = 1
        vendor.business_name = "Test Vendor"
        vendor.display_name = "Test Vendor Display"
        vendor.email = "vendor@example.com"
        vendor.category = VendorCategory.CATERING
        vendor.status = VendorStatus.ACTIVE
        vendor.user_id = 1
        vendor.average_rating = 4.5
        vendor.total_reviews = 10
        vendor.total_bookings = 25
        vendor.services = []
        vendor.reviews = []
        vendor.portfolio_items = []
        return vendor
    
    @pytest.fixture
    def mock_vendor_service_model(self):
        """Mock vendor service model for testing."""
        service = Mock(spec=VendorServiceModel)
        service.id = 1
        service.vendor_id = 1
        service.name = "Test Service"
        service.description = "Test service description"
        service.base_price = 100.0
        service.currency = "USD"
        service.service_type = ServiceType.FIXED_PRICE
        service.is_active = True
        service.max_guests = 50
        service.duration_hours = 2
        return service
    
    @pytest.fixture
    def mock_booking(self):
        """Mock booking for testing."""
        booking = Mock(spec=VendorBooking)
        booking.id = 1
        booking.booking_reference = "BK-12345678"
        booking.vendor_id = 1
        booking.service_id = 1
        booking.event_id = 1
        booking.booked_by_id = 1
        booking.status = BookingStatus.PENDING
        booking.quoted_price = 100.0
        booking.currency = "USD"
        booking.service_date = datetime.utcnow() + timedelta(days=7)
        booking.payments = []
        return booking
    
    # Vendor CRUD tests
    def test_create_vendor_success(self, vendor_service, mock_db):
        """Test successful vendor creation."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None  # No existing vendor
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        vendor_data = {
            "business_name": "Test Vendor",
            "display_name": "Test Vendor Display",
            "email": "vendor@example.com",
            "category": "catering",
            "description": "Test vendor description",
            "city": "Test City",
            "state": "Test State",
            "country": "Test Country"
        }
        
        # Execute
        result = vendor_service.create_vendor(1, vendor_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    def test_create_vendor_already_exists(self, vendor_service, mock_db, mock_vendor):
        """Test vendor creation when user already has a vendor profile."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_vendor
        
        vendor_data = {
            "business_name": "Test Vendor",
            "display_name": "Test Vendor Display",
            "email": "vendor@example.com",
            "category": "catering"
        }
        
        # Execute & Assert
        with pytest.raises(ValidationError, match="User already has a vendor profile"):
            vendor_service.create_vendor(1, vendor_data)
    
    def test_get_vendor_success(self, vendor_service, mock_db, mock_vendor):
        """Test successful vendor retrieval."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_vendor
        
        # Execute
        result = vendor_service.get_vendor(1)
        
        # Assert
        assert result == mock_vendor
    
    def test_get_vendor_not_found(self, vendor_service, mock_db):
        """Test vendor retrieval with non-existent vendor."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = None
        
        # Execute
        result = vendor_service.get_vendor(999)
        
        # Assert
        assert result is None
    
    def test_search_vendors_success(self, vendor_service, mock_db):
        """Test successful vendor search."""
        # Setup
        mock_vendors = [Mock(spec=Vendor) for _ in range(3)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 3
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_vendors
        
        mock_db.query.return_value.options.return_value = mock_query
        
        search_params = {
            "query": "catering",
            "category": VendorCategory.CATERING,
            "city": "Test City",
            "min_rating": 4.0,
            "page": 1,
            "per_page": 10
        }
        
        # Execute
        vendors, total = vendor_service.search_vendors(search_params)
        
        # Assert
        assert len(vendors) == 3
        assert total == 3
    
    def test_update_vendor_success(self, vendor_service, mock_db, mock_vendor):
        """Test successful vendor update."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_vendor
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        update_data = {
            "business_name": "Updated Vendor",
            "description": "Updated description"
        }
        
        # Execute
        result = vendor_service.update_vendor(1, 1, update_data)
        
        # Assert
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result == mock_vendor
    
    def test_update_vendor_permission_denied(self, vendor_service, mock_db, mock_vendor):
        """Test vendor update with permission denied."""
        # Setup
        mock_vendor.user_id = 2  # Different user
        mock_db.query.return_value.filter.return_value.first.return_value = mock_vendor
        
        update_data = {"business_name": "Updated Vendor"}
        
        # Execute & Assert
        with pytest.raises(AuthorizationError, match="You don't have permission to edit this vendor"):
            vendor_service.update_vendor(1, 1, update_data)
    
    # Vendor Service tests
    def test_create_vendor_service_success(self, vendor_service, mock_db, mock_vendor):
        """Test successful vendor service creation."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_vendor
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        service_data = {
            "name": "Test Service",
            "description": "Test service description",
            "base_price": 100.0,
            "service_type": "fixed_price",
            "duration_hours": 2,
            "max_guests": 50
        }
        
        # Execute
        result = vendor_service.create_vendor_service(1, 1, service_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    def test_get_vendor_services_success(self, vendor_service, mock_db):
        """Test successful vendor services retrieval."""
        # Setup
        mock_services = [Mock(spec=VendorServiceModel) for _ in range(3)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_services
        
        # Execute
        result = vendor_service.get_vendor_services(1)
        
        # Assert
        assert len(result) == 3
    
    # Booking tests
    def test_create_booking_success(self, vendor_service, mock_db, mock_vendor_service_model, mock_event):
        """Test successful booking creation."""
        # Setup
        mock_vendor_service_model.vendor = mock_vendor_service_model  # Add vendor relationship
        mock_db.query.return_value.options.return_value.filter.return_value.first.side_effect = [
            mock_vendor_service_model,  # Service query
            mock_event  # Event query
        ]
        
        # Mock availability check
        with patch.object(vendor_service, '_check_availability', return_value=True):
            with patch.object(vendor_service, '_calculate_service_price', return_value=100.0):
                mock_db.add = Mock()
                mock_db.commit = Mock()
                mock_db.refresh = Mock()
                
                booking_data = {
                    "service_date": datetime.utcnow() + timedelta(days=7),
                    "guest_count": 25,
                    "service_duration_hours": 2,
                    "special_requests": "Test request"
                }
                
                # Execute
                result = vendor_service.create_booking(1, 1, 1, booking_data)
                
                # Assert
                mock_db.add.assert_called_once()
                mock_db.commit.assert_called_once()
                mock_db.refresh.assert_called_once()
                assert result is not None
    
    def test_create_booking_service_not_found(self, vendor_service, mock_db):
        """Test booking creation with non-existent service."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = None
        
        booking_data = {
            "service_date": datetime.utcnow() + timedelta(days=7),
            "guest_count": 25
        }
        
        # Execute & Assert
        with pytest.raises(NotFoundError, match="Service not found"):
            vendor_service.create_booking(999, 1, 1, booking_data)
    
    def test_create_booking_not_available(self, vendor_service, mock_db, mock_vendor_service_model, mock_event):
        """Test booking creation when vendor is not available."""
        # Setup
        mock_vendor_service_model.vendor = mock_vendor_service_model
        mock_db.query.return_value.options.return_value.filter.return_value.first.side_effect = [
            mock_vendor_service_model,
            mock_event
        ]
        
        # Mock availability check to return False
        with patch.object(vendor_service, '_check_availability', return_value=False):
            booking_data = {
                "service_date": datetime.utcnow() + timedelta(days=7),
                "guest_count": 25
            }
            
            # Execute & Assert
            with pytest.raises(ValidationError, match="Vendor is not available on the requested date"):
                vendor_service.create_booking(1, 1, 1, booking_data)
    
    def test_get_booking_success(self, vendor_service, mock_db, mock_booking):
        """Test successful booking retrieval."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_booking
        
        # Execute
        result = vendor_service.get_booking(1, 1)
        
        # Assert
        assert result == mock_booking
    
    def test_get_booking_access_denied(self, vendor_service, mock_db, mock_booking):
        """Test booking retrieval with access denied."""
        # Setup
        mock_booking.booked_by_id = 2  # Different user
        mock_booking.vendor = Mock()
        mock_booking.vendor.user_id = 3  # Different vendor user
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_booking
        
        # Execute & Assert
        with pytest.raises(AuthorizationError, match="You don't have access to this booking"):
            vendor_service.get_booking(1, 1)
    
    def test_update_booking_status_success(self, vendor_service, mock_db, mock_booking):
        """Test successful booking status update."""
        # Setup
        mock_vendor = Mock()
        mock_vendor.user_id = 1
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_booking, mock_vendor]
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Execute
        result = vendor_service.update_booking_status(1, 1, BookingStatus.CONFIRMED)
        
        # Assert
        assert result.status == BookingStatus.CONFIRMED
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    # Payment tests
    def test_create_payment_success(self, vendor_service, mock_db, mock_booking):
        """Test successful payment creation."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_booking
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        payment_data = {
            "amount": 50.0,
            "payment_method": "credit_card",
            "is_deposit": True,
            "description": "Deposit payment"
        }
        
        # Execute
        result = vendor_service.create_payment(1, 1, payment_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    def test_process_payment_success(self, vendor_service, mock_db):
        """Test successful payment processing."""
        # Setup
        mock_payment = Mock(spec=VendorPayment)
        mock_payment.id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_payment
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Execute
        result = vendor_service.process_payment(1, "stripe_payment_123", PaymentStatus.PAID)
        
        # Assert
        assert result.payment_provider_id == "stripe_payment_123"
        assert result.status == PaymentStatus.PAID
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    # Review tests
    def test_create_review_success(self, vendor_service, mock_db, mock_vendor, mock_booking):
        """Test successful review creation."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_vendor,  # Vendor query
            mock_booking,  # Booking query
            None  # No existing review
        ]
        
        with patch.object(vendor_service, '_update_vendor_rating'):
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()
            
            review_data = {
                "rating": 5,
                "title": "Great service!",
                "review_text": "Excellent catering service for our event.",
                "service_quality": 5,
                "communication": 5,
                "value_for_money": 4,
                "punctuality": 5,
                "booking_id": 1
            }
            
            # Execute
            result = vendor_service.create_review(1, 1, review_data)
            
            # Assert
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
            assert result is not None
    
    def test_create_review_already_exists(self, vendor_service, mock_db, mock_vendor):
        """Test review creation when user already reviewed the vendor."""
        # Setup
        mock_existing_review = Mock(spec=VendorReview)
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_vendor,  # Vendor query
            None,  # No booking query (optional)
            mock_existing_review  # Existing review
        ]
        
        review_data = {
            "rating": 5,
            "review_text": "Great service!"
        }
        
        # Execute & Assert
        with pytest.raises(ValidationError, match="You have already reviewed this vendor"):
            vendor_service.create_review(1, 1, review_data)
    
    def test_get_vendor_reviews_success(self, vendor_service, mock_db):
        """Test successful vendor reviews retrieval."""
        # Setup
        mock_reviews = [Mock(spec=VendorReview) for _ in range(5)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 5
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_reviews
        
        mock_db.query.return_value.options.return_value = mock_query
        
        # Execute
        reviews, total = vendor_service.get_vendor_reviews(1, 1, 10)
        
        # Assert
        assert len(reviews) == 5
        assert total == 5
    
    # Portfolio tests
    def test_add_portfolio_item_success(self, vendor_service, mock_db, mock_vendor):
        """Test successful portfolio item addition."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_vendor
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        portfolio_data = {
            "title": "Wedding Reception",
            "description": "Beautiful wedding reception catering",
            "image_url": "https://example.com/image.jpg",
            "event_type": "wedding",
            "guest_count": 100
        }
        
        # Execute
        result = vendor_service.add_portfolio_item(1, 1, portfolio_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    # Availability tests
    def test_set_availability_success(self, vendor_service, mock_db, mock_vendor):
        """Test successful availability setting."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_vendor,  # Vendor query
            None,  # No existing availability for first date
            None   # No existing availability for second date
        ]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        availability_data = [
            {
                "date": datetime(2024, 1, 15),
                "is_available": True,
                "start_time": "09:00",
                "end_time": "17:00"
            },
            {
                "date": datetime(2024, 1, 16),
                "is_available": False,
                "is_blocked": True,
                "block_reason": "Personal day"
            }
        ]
        
        # Execute
        result = vendor_service.set_availability(1, 1, availability_data)
        
        # Assert
        assert mock_db.add.call_count == 2
        mock_db.commit.assert_called_once()
        assert len(result) == 2
    
    def test_get_vendor_availability_success(self, vendor_service, mock_db):
        """Test successful vendor availability retrieval."""
        # Setup
        mock_availability = [Mock(spec=VendorAvailability) for _ in range(7)]  # Week of availability
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_availability
        
        mock_db.query.return_value = mock_query
        
        start_date = datetime(2025, 1, 15)
        end_date = datetime(2025, 9, 21)
        
        # Execute
        result = vendor_service.get_vendor_availability(1, start_date, end_date)
        
        # Assert
        assert len(result) == 7
    
    # Statistics tests
    def test_get_vendor_statistics_success(self, vendor_service, mock_db, mock_vendor):
        """Test successful vendor statistics retrieval."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_vendor
        
        # Mock scalar queries for statistics
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [
            25,    # total_bookings
            20,    # completed_bookings
            3,     # cancelled_bookings
            2500.0 # total_revenue
        ]
        
        # Execute
        stats = vendor_service.get_vendor_statistics(1, 1)
        
        # Assert
        assert stats["total_bookings"] == 25
        assert stats["completed_bookings"] == 20
        assert stats["cancelled_bookings"] == 3
        assert stats["total_revenue"] == 2500.0
        assert stats["average_rating"] == 4.5
        assert stats["total_reviews"] == 10
        assert stats["booking_conversion_rate"] == 80.0  # 20/25 * 100
    
    # Helper method tests
    def test_get_event_with_access_success(self, vendor_service, mock_db, mock_event):
        """Test successful event access check."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_event
        
        # Execute
        result = vendor_service._get_event_with_access(1, 1)
        
        # Assert
        assert result == mock_event
    
    def test_check_availability_true(self, vendor_service, mock_db):
        """Test availability check returning True."""
        # Setup
        mock_availability = Mock(spec=VendorAvailability)
        mock_availability.is_available = True
        mock_availability.is_blocked = False
        mock_db.query.return_value.filter.return_value.first.return_value = mock_availability
        
        service_date = datetime(2024, 1, 15, 10, 0, 0)
        
        # Execute
        result = vendor_service._check_availability(1, service_date)
        
        # Assert
        assert result is True
    
    def test_check_availability_false(self, vendor_service, mock_db):
        """Test availability check returning False."""
        # Setup
        mock_availability = Mock(spec=VendorAvailability)
        mock_availability.is_available = False
        mock_availability.is_blocked = True
        mock_db.query.return_value.filter.return_value.first.return_value = mock_availability
        
        service_date = datetime(2024, 1, 15, 10, 0, 0)
        
        # Execute
        result = vendor_service._check_availability(1, service_date)
        
        # Assert
        assert result is False
    
    def test_check_availability_no_record(self, vendor_service, mock_db):
        """Test availability check with no availability record (defaults to True)."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service_date = datetime(2024, 1, 15, 10, 0, 0)
        
        # Execute
        result = vendor_service._check_availability(1, service_date)
        
        # Assert
        assert result is True
    
    def test_calculate_service_price_hourly(self, vendor_service, mock_vendor_service_model):
        """Test service price calculation for hourly service."""
        # Setup
        mock_vendor_service_model.service_type = ServiceType.HOURLY
        mock_vendor_service_model.base_price = 50.0
        
        # Execute
        result = vendor_service._calculate_service_price(mock_vendor_service_model, None, 3)
        
        # Assert
        assert result == 150.0  # 50 * 3 hours
    
    def test_calculate_service_price_fixed(self, vendor_service, mock_vendor_service_model):
        """Test service price calculation for fixed price service."""
        # Setup
        mock_vendor_service_model.service_type = ServiceType.FIXED_PRICE
        mock_vendor_service_model.base_price = 200.0
        
        # Execute
        result = vendor_service._calculate_service_price(mock_vendor_service_model, 25, 2)
        
        # Assert
        assert result == 200.0  # Fixed price regardless of duration/guests
    
    def test_calculate_service_price_package_with_extra_guests(self, vendor_service, mock_vendor_service_model):
        """Test service price calculation for package with extra guests."""
        # Setup
        mock_vendor_service_model.service_type = ServiceType.PACKAGE
        mock_vendor_service_model.base_price = 500.0
        mock_vendor_service_model.max_guests = 50
        
        # Execute - 60 guests (10 extra)
        result = vendor_service._calculate_service_price(mock_vendor_service_model, 60, 2)
        
        # Assert
        # Base price + (10 extra guests * 10% surcharge per guest)
        # 500 + (10 * 50) = 500 + 500 = 1000
        assert result == 1000.0
    
    def test_update_vendor_rating_success(self, vendor_service, mock_db, mock_vendor):
        """Test successful vendor rating update."""
        # Setup
        mock_reviews = []
        for i in range(5):
            review = Mock(spec=VendorReview)
            review.rating = 4 + (i % 2)  # Ratings of 4, 5, 4, 5, 4
            mock_reviews.append(review)
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_vendor
        mock_db.query.return_value.filter.return_value.all.return_value = mock_reviews
        mock_db.commit = Mock()
        
        # Execute
        vendor_service._update_vendor_rating(1)
        
        # Assert
        assert mock_vendor.average_rating == 4.4  # (4+5+4+5+4)/5
        assert mock_vendor.total_reviews == 5
        mock_db.commit.assert_called_once()
    
    # Integration-style tests
    def test_vendor_booking_workflow_integration(self, vendor_service, mock_db, mock_vendor, mock_vendor_service_model, mock_event):
        """Test complete vendor booking workflow integration."""
        # Setup mocks for the entire workflow
        mock_booking = Mock(spec=VendorBooking)
        mock_booking.id = 1
        mock_booking.booked_by_id = 1
        mock_booking.vendor = Mock()
        mock_booking.vendor.user_id = 2
        mock_booking.currency = "USD"
        
        mock_payment = Mock(spec=VendorPayment)
        mock_payment.id = 1
        
        # Mock database interactions
        mock_vendor_service_model.vendor = mock_vendor
        mock_db.query.return_value.options.return_value.filter.return_value.first.side_effect = [
            mock_vendor_service_model,  # For create_booking (service)
            mock_event,  # For create_booking (event)
            mock_booking,  # For create_payment
            mock_booking,  # For get_booking
        ]
        
        with patch.object(vendor_service, '_check_availability', return_value=True):
            with patch.object(vendor_service, '_calculate_service_price', return_value=100.0):
                mock_db.add = Mock()
                mock_db.commit = Mock()
                mock_db.refresh = Mock()
                
                # Execute workflow
                # 1. Create booking
                booking_data = {
                    "service_date": datetime.utcnow() + timedelta(days=7),
                    "guest_count": 25,
                    "special_requests": "Vegetarian options"
                }
                booking = vendor_service.create_booking(1, 1, 1, booking_data)
                
                # 2. Create payment
                payment_data = {
                    "amount": 50.0,
                    "payment_method": "credit_card",
                    "is_deposit": True
                }
                payment = vendor_service.create_payment(1, 1, payment_data)
                
                # 3. Get booking details
                retrieved_booking = vendor_service.get_booking(1, 1)
                
                # Assert all operations succeeded
                assert mock_db.add.call_count >= 2  # booking and payment
                assert mock_db.commit.call_count >= 2
                assert booking is not None
                assert payment is not None
                assert retrieved_booking is not None