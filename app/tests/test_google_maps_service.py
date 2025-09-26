"""
Tests for Google Maps service and location optimization functionality.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.google_maps_service import GoogleMapsService, LocationSuggestion, GeocodeResult
from app.schemas.location import Coordinates, LocationValidation, LocationOptimizationRequest
from app.core.config import settings


class TestGoogleMapsService:
    """Test cases for GoogleMapsService"""
    
    @pytest.fixture
    def mock_googlemaps_client(self):
        """Mock Google Maps client"""
        with patch('app.services.google_maps_service.googlemaps.Client') as mock_client:
            yield mock_client.return_value
    
    @pytest.fixture
    def google_maps_service(self, mock_googlemaps_client):
        """Google Maps service instance with mocked client"""
        service = GoogleMapsService()
        service.client = mock_googlemaps_client
        return service
    
    def test_service_initialization(self):
        """Test service initialization with API key"""
        with patch('app.services.google_maps_service.googlemaps.Client') as mock_client:
            service = GoogleMapsService()
            mock_client.assert_called_once_with(key=settings.GOOGLE_MAPS_API_KEY)
    
    @pytest.mark.asyncio
    async def test_geocode_address_success(self, google_maps_service, mock_googlemaps_client):
        """Test successful address geocoding"""
        # Mock response
        mock_response = [{
            'formatted_address': '1600 Amphitheatre Parkway, Mountain View, CA 94043, USA',
            'geometry': {
                'location': {'lat': 37.4224764, 'lng': -122.0842499},
                'location_type': 'ROOFTOP'
            },
            'place_id': 'ChIJ2eUgeAK6j4ARbn5u_wAGqWA'
        }]
        mock_googlemaps_client.geocode.return_value = mock_response
        
        # Test geocoding
        result = await google_maps_service.geocode_address("1600 Amphitheatre Parkway")
        
        assert result is not None
        assert result.formatted_address == '1600 Amphitheatre Parkway, Mountain View, CA 94043, USA'
        assert result.coordinates.latitude == 37.4224764
        assert result.coordinates.longitude == -122.0842499
        assert result.place_id == 'ChIJ2eUgeAK6j4ARbn5u_wAGqWA'
        mock_googlemaps_client.geocode.assert_called_once_with("1600 Amphitheatre Parkway")
    
    @pytest.mark.asyncio
    async def test_geocode_address_no_results(self, google_maps_service, mock_googlemaps_client):
        """Test geocoding with no results"""
        mock_googlemaps_client.geocode.return_value = []
        
        result = await google_maps_service.geocode_address("invalid address")
        
        assert result is None
        mock_googlemaps_client.geocode.assert_called_once_with("invalid address")
    
    @pytest.mark.asyncio
    async def test_reverse_geocode_success(self, google_maps_service, mock_googlemaps_client):
        """Test successful reverse geocoding"""
        # Mock response
        mock_response = [{
            'formatted_address': '1600 Amphitheatre Parkway, Mountain View, CA 94043, USA',
            'place_id': 'ChIJ2eUgeAK6j4ARbn5u_wAGqWA'
        }]
        mock_googlemaps_client.reverse_geocode.return_value = mock_response
        
        coordinates = Coordinates(latitude=37.4224764, longitude=-122.0842499)
        result = await google_maps_service.reverse_geocode(coordinates)
        
        assert result is not None
        assert result.formatted_address == '1600 Amphitheatre Parkway, Mountain View, CA 94043, USA'
        assert result.place_id == 'ChIJ2eUgeAK6j4ARbn5u_wAGqWA'
        mock_googlemaps_client.reverse_geocode.assert_called_once_with((37.4224764, -122.0842499))
    
    @pytest.mark.asyncio
    async def test_get_place_autocomplete_success(self, google_maps_service, mock_googlemaps_client):
        """Test successful place autocomplete"""
        # Mock response
        mock_response = {
            'predictions': [{
                'place_id': 'ChIJ2eUgeAK6j4ARbn5u_wAGqWA',
                'description': 'Googleplex, Amphitheatre Parkway, Mountain View, CA, USA',
                'structured_formatting': {
                    'main_text': 'Googleplex',
                    'secondary_text': 'Amphitheatre Parkway, Mountain View, CA, USA'
                },
                'types': ['establishment', 'point_of_interest']
            }]
        }
        mock_googlemaps_client.places_autocomplete.return_value = mock_response
        
        # Mock place details
        mock_place_details = {
            'result': {
                'geometry': {
                    'location': {'lat': 37.4224764, 'lng': -122.0842499}
                },
                'rating': 4.5,
                'price_level': 2
            }
        }
        mock_googlemaps_client.place.return_value = mock_place_details
        
        user_coords = Coordinates(latitude=37.4, longitude=-122.1)
        suggestions = await google_maps_service.get_place_autocomplete(
            query="Googleplex",
            user_coordinates=user_coords,
            radius_meters=5000
        )
        
        assert len(suggestions) == 1
        suggestion = suggestions[0]
        assert suggestion.place_id == 'ChIJ2eUgeAK6j4ARbn5u_wAGqWA'
        assert suggestion.name == 'Googleplex'
        assert suggestion.formatted_address == 'Amphitheatre Parkway, Mountain View, CA, USA'
        assert suggestion.rating == 4.5
        assert suggestion.price_level == 2
    
    @pytest.mark.asyncio
    async def test_search_nearby_places_success(self, google_maps_service, mock_googlemaps_client):
        """Test successful nearby places search"""
        # Mock response
        mock_response = {
            'results': [{
                'place_id': 'ChIJ2eUgeAK6j4ARbn5u_wAGqWA',
                'name': 'Test Restaurant',
                'formatted_address': '123 Test St, Test City, CA 94043, USA',
                'geometry': {
                    'location': {'lat': 37.4224764, 'lng': -122.0842499}
                },
                'types': ['restaurant', 'food'],
                'rating': 4.2,
                'price_level': 3
            }]
        }
        mock_googlemaps_client.places_nearby.return_value = mock_response
        
        coordinates = Coordinates(latitude=37.4224764, longitude=-122.0842499)
        places = await google_maps_service.search_nearby_places(
            coordinates=coordinates,
            radius_meters=1000,
            place_type="restaurant"
        )
        
        assert len(places) == 1
        place = places[0]
        assert place.place_id == 'ChIJ2eUgeAK6j4ARbn5u_wAGqWA'
        assert place.name == 'Test Restaurant'
        assert place.rating == 4.2
        assert place.price_level == 3
    
    @pytest.mark.asyncio
    async def test_validate_address_valid(self, google_maps_service, mock_googlemaps_client):
        """Test address validation with valid address"""
        # Mock geocoding response
        mock_response = [{
            'formatted_address': '1600 Amphitheatre Parkway, Mountain View, CA 94043, USA',
            'geometry': {
                'location': {'lat': 37.4224764, 'lng': -122.0842499},
                'location_type': 'ROOFTOP'
            },
            'place_id': 'ChIJ2eUgeAK6j4ARbn5u_wAGqWA'
        }]
        mock_googlemaps_client.geocode.return_value = mock_response
        
        validation = await google_maps_service.validate_address("1600 Amphitheatre Parkway")
        
        assert validation.is_valid is True
        assert validation.formatted_address == '1600 Amphitheatre Parkway, Mountain View, CA 94043, USA'
        assert validation.coordinates.latitude == 37.4224764
        assert validation.coordinates.longitude == -122.0842499
        assert validation.place_id == 'ChIJ2eUgeAK6j4ARbn5u_wAGqWA'
        assert validation.error is None
    
    @pytest.mark.asyncio
    async def test_validate_address_invalid(self, google_maps_service, mock_googlemaps_client):
        """Test address validation with invalid address"""
        mock_googlemaps_client.geocode.return_value = []
        
        validation = await google_maps_service.validate_address("invalid address")
        
        assert validation.is_valid is False
        assert validation.formatted_address is None
        assert validation.coordinates is None
        assert validation.place_id is None
        assert "No results found" in validation.error
    
    @pytest.mark.asyncio
    async def test_optimize_location_input_success(self, google_maps_service, mock_googlemaps_client):
        """Test successful location input optimization"""
        # Mock geocoding response
        mock_geocode_response = [{
            'formatted_address': '1600 Amphitheatre Parkway, Mountain View, CA 94043, USA',
            'geometry': {
                'location': {'lat': 37.4224764, 'lng': -122.0842499},
                'location_type': 'ROOFTOP'
            },
            'place_id': 'ChIJ2eUgeAK6j4ARbn5u_wAGqWA'
        }]
        mock_googlemaps_client.geocode.return_value = mock_geocode_response
        
        # Mock autocomplete response
        mock_autocomplete_response = {
            'predictions': [{
                'place_id': 'ChIJ2eUgeAK6j4ARbn5u_wAGqWA',
                'description': 'Googleplex, Amphitheatre Parkway, Mountain View, CA, USA',
                'structured_formatting': {
                    'main_text': 'Googleplex',
                    'secondary_text': 'Amphitheatre Parkway, Mountain View, CA, USA'
                },
                'types': ['establishment']
            }]
        }
        mock_googlemaps_client.places_autocomplete.return_value = mock_autocomplete_response
        
        # Mock place details
        mock_place_details = {
            'result': {
                'geometry': {
                    'location': {'lat': 37.4224764, 'lng': -122.0842499}
                }
            }
        }
        mock_googlemaps_client.place.return_value = mock_place_details
        
        user_coords = Coordinates(latitude=37.4, longitude=-122.1)
        result = await google_maps_service.optimize_location_input(
            user_input="Googleplex",
            user_coordinates=user_coords,
            include_nearby=True,
            max_suggestions=5
        )
        
        assert result.optimized is True
        assert result.original_input == "Googleplex"
        assert result.validation.is_valid is True
        assert len(result.autocomplete_suggestions) == 1
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_optimize_location_input_api_error(self, google_maps_service, mock_googlemaps_client):
        """Test location optimization with API error"""
        mock_googlemaps_client.geocode.side_effect = Exception("API Error")
        
        result = await google_maps_service.optimize_location_input(
            user_input="test location",
            user_coordinates=None,
            include_nearby=False,
            max_suggestions=5
        )
        
        assert result.optimized is False
        assert result.original_input == "test location"
        assert result.validation.is_valid is False
        assert "API Error" in result.error
    
    def test_calculate_distance(self, google_maps_service):
        """Test distance calculation between coordinates"""
        coord1 = Coordinates(latitude=37.4224764, longitude=-122.0842499)
        coord2 = Coordinates(latitude=37.4419, longitude=-122.1430)
        
        distance = google_maps_service._calculate_distance(coord1, coord2)
        
        # Distance should be approximately 5.5 km
        assert 5000 < distance < 6000
    
    def test_calculate_distance_same_point(self, google_maps_service):
        """Test distance calculation for same coordinates"""
        coord = Coordinates(latitude=37.4224764, longitude=-122.0842499)
        
        distance = google_maps_service._calculate_distance(coord, coord)
        
        assert distance == 0.0


class TestLocationOptimizationIntegration:
    """Integration tests for location optimization in event creation"""
    
    @pytest.mark.asyncio
    async def test_event_creation_with_location_optimization(self):
        """Test event creation with location optimization enabled"""
        # This would require setting up test database and mocking Google Maps API
        # Implementation would depend on your testing setup
        pass
    
    @pytest.mark.asyncio
    async def test_event_creation_without_location_optimization(self):
        """Test event creation with location optimization disabled"""
        # This would test the fallback behavior
        pass
    
    @pytest.mark.asyncio
    async def test_location_optimization_endpoints(self):
        """Test the location optimization API endpoints"""
        # This would test the FastAPI endpoints with test client
        pass


# Fixtures for common test data
@pytest.fixture
def sample_coordinates():
    """Sample coordinates for testing"""
    return Coordinates(latitude=37.4224764, longitude=-122.0842499)


@pytest.fixture
def sample_location_request():
    """Sample location optimization request"""
    return LocationOptimizationRequest(
        user_input="Central Park, New York",
        user_coordinates=Coordinates(latitude=40.7589, longitude=-73.9851),
        include_nearby=True,
        max_suggestions=10
    )


@pytest.fixture
def sample_geocode_result():
    """Sample geocode result for testing"""
    return GeocodeResult(
        formatted_address="1600 Amphitheatre Parkway, Mountain View, CA 94043, USA",
        coordinates=Coordinates(latitude=37.4224764, longitude=-122.0842499),
        place_id="ChIJ2eUgeAK6j4ARbn5u_wAGqWA",
        location_type="ROOFTOP"
    )


@pytest.fixture
def sample_location_suggestion():
    """Sample location suggestion for testing"""
    return LocationSuggestion(
        place_id="ChIJ2eUgeAK6j4ARbn5u_wAGqWA",
        name="Googleplex",
        formatted_address="1600 Amphitheatre Parkway, Mountain View, CA 94043, USA",
        coordinates=Coordinates(latitude=37.4224764, longitude=-122.0842499),
        types=["establishment", "point_of_interest"],
        distance_meters=1500.0,
        rating=4.5,
        price_level=2
    )