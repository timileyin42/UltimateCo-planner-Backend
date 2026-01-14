"""
Google Maps API service for location optimization and geocoding.
Provides intelligent location suggestions, validation, and optimization.
"""

from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
import googlemaps
from googlemaps.exceptions import ApiError, Timeout, TransportError
from app.core.config import get_settings
from app.schemas.location import Coordinates
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LocationSuggestion:
    """Represents a location suggestion from Google Maps."""
    place_id: str
    formatted_address: str
    name: str
    latitude: float
    longitude: float
    types: List[str]
    distance_meters: Optional[float] = None
    rating: Optional[float] = None
    price_level: Optional[int] = None


@dataclass
class GeocodeResult:
    """Represents a geocoding result."""
    latitude: float
    longitude: float
    formatted_address: str
    place_id: str
    address_components: Dict[str, Any]
    location_type: str


class GoogleMapsService:
    """Service for Google Maps API operations."""
    
    def __init__(self):
        """Initialize the Google Maps service."""
        self.settings = get_settings()
        self._client = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize the Google Maps client."""
        try:
            if not self.settings.GOOGLE_MAPS_API_KEY:
                logger.warning("Google Maps API key not configured")
                return
            
            self._client = googlemaps.Client(key=self.settings.GOOGLE_MAPS_API_KEY)
            logger.info("Google Maps client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Maps client: {e}")
            self._client = None
    
    def is_available(self) -> bool:
        """Check if the Google Maps service is available."""
        return self._client is not None
    
    async def geocode_address(self, address: str) -> Optional[GeocodeResult]:
        """
        Geocode an address to get coordinates and detailed information.
        
        Args:
            address: The address to geocode
            
        Returns:
            GeocodeResult if successful, None otherwise
        """
        if not self.is_available():
            logger.warning("Google Maps service not available for geocoding")
            return None
        
        try:
            results = self._client.geocode(address)
            
            if not results:
                logger.info(f"No geocoding results found for address: {address}")
                return None
            
            result = results[0]  # Take the first (best) result
            geometry = result['geometry']
            location = geometry['location']
            
            return GeocodeResult(
                latitude=location['lat'],
                longitude=location['lng'],
                formatted_address=result['formatted_address'],
                place_id=result['place_id'],
                address_components=result.get('address_components', {}),
                location_type=geometry.get('location_type', 'APPROXIMATE')
            )
            
        except (ApiError, Timeout, TransportError) as e:
            logger.error(f"Google Maps API error during geocoding: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during geocoding: {e}")
            return None
    
    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Reverse geocode coordinates to get a formatted address.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Formatted address if successful, None otherwise
        """
        if not self.is_available():
            logger.warning("Google Maps service not available for reverse geocoding")
            return None
        
        try:
            results = self._client.reverse_geocode((latitude, longitude))
            
            if not results:
                logger.info(f"No reverse geocoding results found for coordinates: {latitude}, {longitude}")
                return None
            
            return results[0]['formatted_address']
            
        except (ApiError, Timeout, TransportError) as e:
            logger.error(f"Google Maps API error during reverse geocoding: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during reverse geocoding: {e}")
            return None
    
    async def get_place_autocomplete(
        self, 
        input_text: str, 
        user_location: Optional[Tuple[float, float]] = None,
        radius: int = 50000,
        types: Optional[List[str]] = None
    ) -> List[LocationSuggestion]:
        """
        Get place autocomplete suggestions based on input text.
        
        Args:
            input_text: The text input for autocomplete
            user_location: User's current location (lat, lng) for bias
            radius: Search radius in meters (default: 50km)
            types: Place types to filter by
            
        Returns:
            List of location suggestions
        """
        if not self.is_available():
            logger.warning("Google Maps service not available for autocomplete")
            return []
        
        try:
            # Prepare autocomplete parameters
            params = {
                'input': input_text,
                'types': types or ['establishment', 'geocode']
            }
            
            # Add location bias if user location is provided
            if user_location:
                params['location'] = user_location
                params['radius'] = radius
            
            results = self._client.places_autocomplete(**params)
            
            suggestions = []
            for result in results:
                # Get place details for each suggestion
                place_details = await self._get_place_details(result['place_id'])
                
                if place_details:
                    suggestion = LocationSuggestion(
                        place_id=result['place_id'],
                        formatted_address=result['description'],
                        name=result['structured_formatting'].get('main_text', ''),
                        latitude=place_details['latitude'],
                        longitude=place_details['longitude'],
                        types=result.get('types', []),
                        rating=place_details.get('rating'),
                        price_level=place_details.get('price_level')
                    )
                    
                    # Calculate distance if user location is provided
                    if user_location:
                        suggestion.distance_meters = self._calculate_distance(
                            user_location[0], user_location[1],
                            suggestion.latitude, suggestion.longitude
                        )
                    
                    suggestions.append(suggestion)
            
            return suggestions
            
        except (ApiError, Timeout, TransportError) as e:
            logger.error(f"Google Maps API error during autocomplete: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during autocomplete: {e}")
            return []
    
    async def find_nearby_places(
        self,
        latitude: float,
        longitude: float,
        radius: int = 5000,
        place_type: str = 'establishment',
        keyword: Optional[str] = None
    ) -> List[LocationSuggestion]:
        """
        Find nearby places based on coordinates.
        
        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius: Search radius in meters (default: 5km)
            place_type: Type of places to search for
            keyword: Optional keyword filter
            
        Returns:
            List of nearby location suggestions
        """
        if not self.is_available():
            logger.warning("Google Maps service not available for nearby search")
            return []
        
        try:
            params = {
                'location': (latitude, longitude),
                'radius': radius,
                'type': place_type
            }
            
            if keyword:
                params['keyword'] = keyword
            
            results = self._client.places_nearby(**params)
            
            suggestions = []
            for result in results.get('results', []):
                geometry = result.get('geometry', {})
                location = geometry.get('location', {})
                
                if location:
                    suggestion = LocationSuggestion(
                        place_id=result['place_id'],
                        formatted_address=result.get('vicinity', ''),
                        name=result.get('name', ''),
                        latitude=location['lat'],
                        longitude=location['lng'],
                        types=result.get('types', []),
                        rating=result.get('rating'),
                        price_level=result.get('price_level')
                    )
                    
                    # Calculate distance from search center
                    suggestion.distance_meters = self._calculate_distance(
                        latitude, longitude,
                        suggestion.latitude, suggestion.longitude
                    )
                    
                    suggestions.append(suggestion)
            
            # Sort by distance
            suggestions.sort(key=lambda x: x.distance_meters or float('inf'))
            
            return suggestions
            
        except (ApiError, Timeout, TransportError) as e:
            logger.error(f"Google Maps API error during nearby search: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during nearby search: {e}")
            return []
    
    async def validate_address(self, address: str) -> Dict[str, Any]:
        """
        Validate an address and return validation details.
        
        Args:
            address: The address to validate
            
        Returns:
            Dictionary with validation results
        """
        if not self.is_available():
            return {
                'is_valid': False,
                'error': 'Google Maps service not available',
                'suggestions': []
            }
        
        try:
            geocode_result = await self.geocode_address(address)
            
            if geocode_result:
                return {
                    'is_valid': True,
                    'formatted_address': geocode_result.formatted_address,
                    'coordinates': {
                        'latitude': geocode_result.latitude,
                        'longitude': geocode_result.longitude
                    },
                    'location_type': geocode_result.location_type,
                    'place_id': geocode_result.place_id
                }
            else:
                # Try to get suggestions for partial matches
                suggestions = await self.get_place_autocomplete(address)
                
                return {
                    'is_valid': False,
                    'error': 'Address not found',
                    'suggestions': [
                        {
                            'formatted_address': s.formatted_address,
                            'name': s.name,
                            'place_id': s.place_id
                        }
                        for s in suggestions[:5]  # Limit to top 5 suggestions
                    ]
                }
                
        except Exception as e:
            logger.error(f"Error validating address: {e}")
            return {
                'is_valid': False,
                'error': f'Validation error: {str(e)}',
                'suggestions': []
            }
    
    async def optimize_location_input(
        self,
        user_input: str,
        user_coordinates: Optional[Coordinates] = None,
        include_nearby: bool = True,
        max_suggestions: int = 10
    ) -> Dict[str, Any]:
        """
        Optimize location input by providing suggestions and validation.
        
        Args:
            user_input: The user's location input
            user_coordinates: User's current coordinates (Coordinates object)
            include_nearby: Whether to include nearby places
            max_suggestions: Maximum number of suggestions to return
            
        Returns:
            Dictionary with optimization results
        """
        if not self.is_available():
            return {
                'optimized': False,
                'error': 'Location optimization service not available',
                'original_input': user_input,
                'suggestions': []
            }
        
        # Convert Coordinates object to tuple for internal methods
        user_location = None
        if user_coordinates:
            user_location = (user_coordinates.latitude, user_coordinates.longitude)
        
        try:
            # First, try to validate the exact input
            validation_result = await self.validate_address(user_input)
            
            # Get autocomplete suggestions
            suggestions = await self.get_place_autocomplete(
                user_input, 
                user_location=user_location
            )
            
            # If user location is provided, also get nearby relevant places
            nearby_places = []
            if user_location and include_nearby and len(user_input.strip()) > 2:
                nearby_places = await self.find_nearby_places(
                    user_location[0], 
                    user_location[1],
                    keyword=user_input
                )
            
            return {
                'optimized': True,
                'original_input': user_input,
                'validation': validation_result,
                'autocomplete_suggestions': [
                    {
                        'place_id': s.place_id,
                        'name': s.name,
                        'formatted_address': s.formatted_address,
                        'coordinates': {
                            'latitude': s.latitude,
                            'longitude': s.longitude
                        },
                        'distance_meters': s.distance_meters,
                        'types': s.types,
                        'rating': s.rating
                    }
                    for s in suggestions[:max_suggestions]
                ],
                'nearby_suggestions': [
                    {
                        'place_id': s.place_id,
                        'name': s.name,
                        'formatted_address': s.formatted_address,
                        'coordinates': {
                            'latitude': s.latitude,
                            'longitude': s.longitude
                        },
                        'distance_meters': s.distance_meters,
                        'types': s.types,
                        'rating': s.rating
                    }
                    for s in nearby_places[:5]
                ]
            }
            
        except Exception as e:
            logger.error(f"Error optimizing location input: {e}")
            return {
                'optimized': False,
                'error': f'Optimization error: {str(e)}',
                'original_input': user_input,
                'suggestions': []
            }
    
    async def _get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a place."""
        try:
            result = self._client.place(
                place_id=place_id,
                fields=['geometry', 'rating', 'price_level']
            )
            
            if result and 'result' in result:
                place = result['result']
                geometry = place.get('geometry', {})
                location = geometry.get('location', {})
                
                if location:
                    return {
                        'latitude': location['lat'],
                        'longitude': location['lng'],
                        'rating': place.get('rating'),
                        'price_level': place.get('price_level')
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting place details for {place_id}: {e}")
            return None
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two coordinates using Haversine formula."""
        import math
        
        # Convert latitude and longitude from degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Radius of earth in meters
        r = 6371000
        
        return c * r


# Global service instance
google_maps_service = GoogleMapsService()