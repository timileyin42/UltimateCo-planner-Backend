"""Schemas for the LLM planning tool layer."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.location import Coordinates


class BudgetRange(BaseModel):
    """Normalized budget hint for Google Places and internal planning tools."""

    model_config = ConfigDict(from_attributes=True)

    min_amount: Optional[float] = Field(None, ge=0)
    max_amount: Optional[float] = Field(None, ge=0)
    currency: str = Field("USD", min_length=3, max_length=3)
    label: Optional[str] = Field(None, max_length=32)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Optional[str]) -> str:
        return (value or "USD").upper()

    @field_validator("label", mode="before")
    @classmethod
    def normalize_label(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        label = value.strip().lower()
        return label or None

    @model_validator(mode="after")
    def validate_bounds(self) -> "BudgetRange":
        if self.min_amount is not None and self.max_amount is not None:
            if self.min_amount > self.max_amount:
                raise ValueError("min_amount cannot be greater than max_amount")
        return self


class VenueSearchInput(BaseModel):
    """Inputs for venue search."""

    city: str = Field(..., min_length=1, max_length=120)
    event_type: str = Field(..., min_length=1, max_length=120)
    indoor_outdoor: Literal["indoor", "outdoor", "either"] = "either"
    guest_count: Optional[int] = Field(None, ge=1)
    budget: Optional[BudgetRange] = None


class PlaceDetailsInput(BaseModel):
    """Inputs for place details lookup."""

    place_id: str = Field(..., min_length=1)


class CatererSearchInput(BaseModel):
    """Inputs for caterer search."""

    city: str = Field(..., min_length=1, max_length=120)
    cuisine: Optional[str] = Field(None, min_length=1, max_length=120)
    budget_range: Optional[BudgetRange] = None


class DecoratorSearchInput(BaseModel):
    """Inputs for decorator search."""

    city: str = Field(..., min_length=1, max_length=120)
    vibe: Optional[str] = Field(None, min_length=1, max_length=120)
    budget_range: Optional[BudgetRange] = None


class EntertainmentSearchInput(BaseModel):
    """Inputs for entertainment search."""

    city: str = Field(..., min_length=1, max_length=120)
    event_type: str = Field(..., min_length=1, max_length=120)
    budget_range: Optional[BudgetRange] = None


class BudgetBreakdownInput(BaseModel):
    """Inputs for deterministic budget planning."""

    total_budget: float = Field(..., gt=0)
    event_type: str = Field(..., min_length=1, max_length=120)
    guest_count: Optional[int] = Field(None, ge=1)
    currency: str = Field("USD", min_length=3, max_length=3)
    priorities: Dict[str, float] = Field(default_factory=dict)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Optional[str]) -> str:
        return (value or "USD").upper()

    @field_validator("priorities", mode="before")
    @classmethod
    def normalize_priorities(cls, value: Optional[Dict[str, Any]]) -> Dict[str, float]:
        normalized: Dict[str, float] = {}
        if not value:
            return normalized
        for raw_key, raw_weight in value.items():
            try:
                weight = float(raw_weight)
            except (TypeError, ValueError):
                continue
            if weight <= 0:
                continue
            key = str(raw_key).strip().lower()
            if key:
                normalized[key] = weight
        return normalized


class TaskPlanInput(BaseModel):
    """Inputs for deterministic task-plan generation."""

    date: date
    event_type: str = Field(..., min_length=1, max_length=120)


class GooglePlacePhoto(BaseModel):
    """Photo metadata returned by Google Places."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    width_px: Optional[int] = None
    height_px: Optional[int] = None
    google_maps_uri: Optional[str] = None
    author_attributions: List[str] = Field(default_factory=list)


class GooglePlaceCandidate(BaseModel):
    """Normalized candidate returned from Places text search."""

    model_config = ConfigDict(from_attributes=True)

    place_id: str
    name: str
    formatted_address: Optional[str] = None
    short_formatted_address: Optional[str] = None
    coordinates: Optional[Coordinates] = None
    primary_type: Optional[str] = None
    types: List[str] = Field(default_factory=list)
    rating: Optional[float] = None
    user_rating_count: Optional[int] = None
    price_level: Optional[str] = None
    price_level_rank: Optional[int] = None
    business_status: Optional[str] = None
    open_now: Optional[bool] = None
    pure_service_area_business: Optional[bool] = None
    google_maps_uri: Optional[str] = None
    fit_score: float = 0.0
    fit_reasons: List[str] = Field(default_factory=list)
    source: str = Field(default="google_places")


class GooglePlaceDetails(BaseModel):
    """Normalized place details returned from Google Places."""

    model_config = ConfigDict(from_attributes=True)

    place_id: str
    name: str
    formatted_address: Optional[str] = None
    short_formatted_address: Optional[str] = None
    coordinates: Optional[Coordinates] = None
    primary_type: Optional[str] = None
    types: List[str] = Field(default_factory=list)
    rating: Optional[float] = None
    user_rating_count: Optional[int] = None
    price_level: Optional[str] = None
    price_level_rank: Optional[int] = None
    business_status: Optional[str] = None
    open_now: Optional[bool] = None
    pure_service_area_business: Optional[bool] = None
    google_maps_uri: Optional[str] = None
    website_uri: Optional[str] = None
    national_phone_number: Optional[str] = None
    regular_opening_hours: List[str] = Field(default_factory=list)
    photos: List[GooglePlacePhoto] = Field(default_factory=list)
    source: str = Field(default="google_places")


class GooglePlacesSearchResponse(BaseModel):
    """Response envelope for Google-backed tool searches."""

    model_config = ConfigDict(from_attributes=True)

    tool_name: str
    query: str
    city: str
    included_type: Optional[str] = None
    budget: Optional[BudgetRange] = None
    candidates: List[GooglePlaceCandidate] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)


class BudgetAllocation(BaseModel):
    """Single category in a generated budget breakdown."""

    model_config = ConfigDict(from_attributes=True)

    category: str
    percentage: float
    amount: float
    rationale: str


class BudgetBreakdownResponse(BaseModel):
    """Deterministic budget breakdown for event planning."""

    model_config = ConfigDict(from_attributes=True)

    event_type: str
    total_budget: float
    currency: str
    guest_count: Optional[int] = None
    allocations: List[BudgetAllocation] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)


class TaskPlanItem(BaseModel):
    """Single task in a generated planning timeline."""

    model_config = ConfigDict(from_attributes=True)

    title: str
    category: str
    due_date: date
    lead_time_days: int


class TaskPlanCategory(BaseModel):
    """Task-plan category and its generated checklist items."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    items: List[TaskPlanItem] = Field(default_factory=list)


class TaskPlanResponse(BaseModel):
    """Deterministic task plan generated from shared templates."""

    model_config = ConfigDict(from_attributes=True)

    event_type: str
    event_date: date
    generated_on: date
    task_categories: List[TaskPlanCategory] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
