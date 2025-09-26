"""
Location-related schemas for event location optimization and validation.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class LocationType(str, Enum):
    """Types of location accuracy from Google Maps."""
    ROOFTOP = "ROOFTOP"
    RANGE_INTERPOLATED = "RANGE_INTERPOLATED"
    GEOMETRIC_CENTER = "GEOMETRIC_CENTER"
    APPROXIMATE = "APPROXIMATE"


class Coordinates(BaseModel):
    """Geographic coordinates."""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "latitude": 40.7128,
                "longitude": -74.0060
            }
        }


class LocationSuggestion(BaseModel):
    """A location suggestion from Google Maps API."""
    place_id: str = Field(..., description="Google Places ID")
    name: str = Field(..., description="Place name")
    formatted_address: str = Field(..., description="Formatted address")
    coordinates: Coordinates = Field(..., description="Geographic coordinates")
    types: List[str] = Field(default_factory=list, description="Place types")
    distance_meters: Optional[float] = Field(None, description="Distance from user location in meters")
    rating: Optional[float] = Field(None, ge=0, le=5, description="Google rating (0-5)")
    price_level: Optional[int] = Field(None, ge=0, le=4, description="Price level (0-4)")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
                "name": "Central Park",
                "formatted_address": "New York, NY 10024, USA",
                "coordinates": {
                    "latitude": 40.7829,
                    "longitude": -73.9654
                },
                "types": ["park", "point_of_interest"],
                "distance_meters": 1200.5,
                "rating": 4.6,
                "price_level": None
            }
        }


class LocationValidation(BaseModel):
    """Result of location validation."""
    is_valid: bool = Field(..., description="Whether the location is valid")
    formatted_address: Optional[str] = Field(None, description="Validated formatted address")
    coordinates: Optional[Coordinates] = Field(None, description="Validated coordinates")
    location_type: Optional[LocationType] = Field(None, description="Accuracy type of the location")
    place_id: Optional[str] = Field(None, description="Google Places ID")
    error: Optional[str] = Field(None, description="Error message if validation failed")
    suggestions: List[LocationSuggestion] = Field(default_factory=list, description="Alternative suggestions")
    
    class Config:
        from_attributes = True


class LocationOptimizationRequest(BaseModel):
    """Request for location optimization."""
    user_input: str = Field(..., min_length=1, max_length=500, description="User's location input")
    user_coordinates: Optional[Coordinates] = Field(None, description="User's current coordinates for optimization")
    include_nearby: bool = Field(True, description="Include nearby place suggestions")
    max_suggestions: int = Field(10, ge=1, le=20, description="Maximum number of suggestions to return")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "user_input": "Central Park",
                "user_coordinates": {
                    "latitude": 40.7589,
                    "longitude": -73.9851
                },
                "include_nearby": True,
                "max_suggestions": 10
            }
        }


class LocationOptimizationResponse(BaseModel):
    """Response from location optimization."""
    optimized: bool = Field(..., description="Whether optimization was successful")
    original_input: str = Field(..., description="Original user input")
    validation: LocationValidation = Field(..., description="Validation result for the input")
    autocomplete_suggestions: List[LocationSuggestion] = Field(
        default_factory=list, 
        description="Autocomplete suggestions based on input"
    )
    nearby_suggestions: List[LocationSuggestion] = Field(
        default_factory=list, 
        description="Nearby relevant places"
    )
    error: Optional[str] = Field(None, description="Error message if optimization failed")
    
    class Config:
        from_attributes = True


class EnhancedLocation(BaseModel):
    """Enhanced location model with optimization features."""
    # Basic location fields (compatible with existing Event model)
    venue_name: Optional[str] = Field(None, max_length=200, description="Venue name")
    venue_address: Optional[str] = Field(None, max_length=500, description="Venue address")
    venue_city: Optional[str] = Field(None, max_length=100, description="Venue city")
    venue_country: Optional[str] = Field(None, max_length=100, description="Venue country")
    
    # Enhanced fields with Google Maps integration
    coordinates: Optional[Coordinates] = Field(None, description="Precise coordinates")
    place_id: Optional[str] = Field(None, description="Google Places ID for reference")
    formatted_address: Optional[str] = Field(None, description="Google-formatted address")
    location_type: Optional[LocationType] = Field(None, description="Location accuracy type")
    
    # Additional metadata
    is_verified: bool = Field(False, description="Whether location has been verified via Google Maps")
    verification_timestamp: Optional[str] = Field(None, description="When location was last verified")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "venue_name": "Central Park Conservatory Garden",
                "venue_address": "Central Park, New York, NY 10029",
                "venue_city": "New York",
                "venue_country": "United States",
                "coordinates": {
                    "latitude": 40.7947,
                    "longitude": -73.9537
                },
                "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
                "formatted_address": "Central Park Conservatory Garden, New York, NY 10029, USA",
                "location_type": "ROOFTOP",
                "is_verified": True,
                "verification_timestamp": "2024-01-15T10:30:00Z"
            }
        }
    
    @validator('venue_name')
    def validate_venue_name(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        return v
    
    @validator('venue_address')
    def validate_venue_address(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        return v


class LocationAutocompleteRequest(BaseModel):
    """Request for location autocomplete."""
    query: str = Field(..., min_length=1, max_length=200, description="Search query")
    user_coordinates: Optional[Coordinates] = Field(None, description="User coordinates for bias")
    radius_meters: int = Field(50000, ge=1000, le=100000, description="Search radius in meters")
    place_types: Optional[List[str]] = Field(None, description="Filter by place types")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "query": "coffee shop",
                "user_coordinates": {
                    "latitude": 40.7589,
                    "longitude": -73.9851
                },
                "radius_meters": 5000,
                "place_types": ["cafe", "restaurant"]
            }
        }


class NearbyPlacesRequest(BaseModel):
    """Request for nearby places search."""
    coordinates: Coordinates = Field(..., description="Center coordinates for search")
    radius_meters: int = Field(5000, ge=100, le=50000, description="Search radius in meters")
    place_type: str = Field("establishment", description="Type of places to search")
    keyword: Optional[str] = Field(None, max_length=100, description="Keyword filter")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "coordinates": {
                    "latitude": 40.7589,
                    "longitude": -73.9851
                },
                "radius_meters": 2000,
                "place_type": "restaurant",
                "keyword": "italian"
            }
        }


class LocationUpdateRequest(BaseModel):
    """Request to update location with optimization."""
    location_input: str = Field(..., description="Location input to optimize")
    user_coordinates: Optional[Coordinates] = Field(None, description="User's current location")
    auto_verify: bool = Field(True, description="Automatically verify location via Google Maps")
    
    class Config:
        from_attributes = True