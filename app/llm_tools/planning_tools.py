"""LLM-callable planning tools backed by Google Places and internal templates."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import math
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from app.core.errors import ValidationError
from app.core.logger import get_logger
from app.llm_tools.google_places import GooglePlacesClient
from app.llm_tools.schemas import (
    BudgetAllocation,
    BudgetBreakdownInput,
    BudgetBreakdownResponse,
    BudgetRange,
    CatererSearchInput,
    DecoratorSearchInput,
    EntertainmentSearchInput,
    GooglePlaceCandidate,
    GooglePlaceDetails,
    GooglePlacePhoto,
    GooglePlacesSearchResponse,
    PlaceDetailsInput,
    TaskPlanCategory,
    TaskPlanInput,
    TaskPlanItem,
    TaskPlanResponse,
    VenueSearchInput,
)
from app.llm_tools.task_templates import get_task_templates_for_type
from app.schemas.location import Coordinates

logger = get_logger(__name__)

SEARCH_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.shortFormattedAddress",
        "places.location",
        "places.primaryType",
        "places.types",
        "places.rating",
        "places.userRatingCount",
        "places.priceLevel",
        "places.businessStatus",
        "places.googleMapsUri",
        "places.regularOpeningHours",
        "places.pureServiceAreaBusiness",
    ]
)

DETAIL_FIELD_MASK = ",".join(
    [
        "id",
        "displayName",
        "formattedAddress",
        "shortFormattedAddress",
        "location",
        "primaryType",
        "types",
        "rating",
        "userRatingCount",
        "priceLevel",
        "businessStatus",
        "googleMapsUri",
        "websiteUri",
        "nationalPhoneNumber",
        "regularOpeningHours",
        "currentOpeningHours",
        "photos",
        "pureServiceAreaBusiness",
    ]
)

PRICE_LEVEL_RANKS = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

PRICE_LEVEL_LABELS = {
    "PRICE_LEVEL_FREE": "free",
    "PRICE_LEVEL_INEXPENSIVE": "budget-friendly",
    "PRICE_LEVEL_MODERATE": "mid-range",
    "PRICE_LEVEL_EXPENSIVE": "premium",
    "PRICE_LEVEL_VERY_EXPENSIVE": "luxury",
}

BASE_BUDGET_ALLOCATIONS: Dict[str, Dict[str, float]] = {
    "WEDDING": {
        "venue": 0.30,
        "catering": 0.25,
        "decor": 0.18,
        "entertainment": 0.10,
        "logistics": 0.10,
        "contingency": 0.07,
    },
    "BIRTHDAY": {
        "venue": 0.26,
        "catering": 0.28,
        "decor": 0.12,
        "entertainment": 0.14,
        "logistics": 0.10,
        "contingency": 0.10,
    },
    "PARTY": {
        "venue": 0.25,
        "catering": 0.25,
        "decor": 0.10,
        "entertainment": 0.15,
        "logistics": 0.15,
        "contingency": 0.10,
    },
    "CONFERENCE": {
        "venue": 0.35,
        "catering": 0.20,
        "decor": 0.05,
        "entertainment": 0.05,
        "logistics": 0.25,
        "contingency": 0.10,
    },
    "MEETING": {
        "venue": 0.22,
        "catering": 0.18,
        "decor": 0.05,
        "entertainment": 0.00,
        "logistics": 0.45,
        "contingency": 0.10,
    },
    "DEFAULT": {
        "venue": 0.28,
        "catering": 0.25,
        "decor": 0.10,
        "entertainment": 0.10,
        "logistics": 0.17,
        "contingency": 0.10,
    },
}

CATEGORY_RATIONALES = {
    "venue": "Reserve enough for shortlisting, deposits, and venue upgrades if the first options do not convert.",
    "catering": "Food and drink costs usually scale fastest with guest count and should be ring-fenced early.",
    "decor": "Decor spend is best treated as a controlled mood-setting budget rather than an open-ended category.",
    "entertainment": "Entertainment budgets need room for booking fees, equipment, and event-day coverage.",
    "logistics": "Logistics covers transport, coordination, rentals, printing, and the smaller operational costs that add up.",
    "contingency": "Holdback budget protects the plan against quote variance, rush fees, and last-minute changes.",
}

CATEGORY_LEAD_DAYS = {
    "Venue": 90,
    "Guests": 45,
    "Food": 30,
    "Decor": 21,
    "Entertainment": 21,
    "Logistics": 30,
    "Extras": 14,
}

EVENT_TYPE_LEAD_MULTIPLIER = {
    "WEDDING": 1.5,
    "CONFERENCE": 1.3,
    "MEETING": 0.75,
}

VENUE_INCLUDED_TYPES = {
    "WEDDING": "wedding_venue",
    "CONFERENCE": "convention_center",
    "MEETING": "convention_center",
    "DEFAULT": "event_venue",
}

PREFERRED_TYPES = {
    "venue": {
        "event_venue",
        "wedding_venue",
        "banquet_hall",
        "convention_center",
        "hotel",
        "restaurant",
    },
    "caterer": {
        "catering_service",
        "restaurant",
        "bakery",
        "meal_delivery",
    },
    "decorator": {
        "florist",
        "art_studio",
        "event_venue",
        "wedding_venue",
    },
    "entertainment": {
        "live_music_venue",
        "night_club",
        "dance_hall",
        "performing_arts_theater",
        "event_venue",
    },
}

_LOW_BUDGET_LABELS = {"low", "budget", "cheap", "affordable", "economy"}
_MID_BUDGET_LABELS = {"mid", "moderate", "medium"}
_HIGH_BUDGET_LABELS = {"high", "premium", "luxury"}


class EventPlanningLLMTools:
    """Google Places-backed tools prepared for later LLM function calling."""

    def __init__(self, places_client: Optional[GooglePlacesClient] = None) -> None:
        self.places_client = places_client or GooglePlacesClient()

    def get_tool_registry(self) -> Dict[str, Callable[..., Any]]:
        """Return a callable registry for later LLM integration."""

        return {
            "search_venues": self.search_venues,
            "get_place_details": self.get_place_details,
            "search_caterers": self.search_caterers,
            "search_decorators": self.search_decorators,
            "search_entertainment": self.search_entertainment,
            "generate_budget_breakdown": self.generate_budget_breakdown,
            "create_task_plan": self.create_task_plan,
        }

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return JSON-schema friendly definitions for the tool layer."""

        return [
            {
                "name": "search_venues",
                "description": (
                    "Search venues in a city using Google Places and score them "
                    "against event type, guest count, and budget hints."
                ),
                "parameters": VenueSearchInput.model_json_schema(),
            },
            {
                "name": "get_place_details",
                "description": "Fetch detailed Google Places metadata for a single place ID.",
                "parameters": PlaceDetailsInput.model_json_schema(),
            },
            {
                "name": "search_caterers",
                "description": "Search catering businesses in a city using Google Places.",
                "parameters": CatererSearchInput.model_json_schema(),
            },
            {
                "name": "search_decorators",
                "description": "Search decorator-style businesses in a city using Google Places.",
                "parameters": DecoratorSearchInput.model_json_schema(),
            },
            {
                "name": "search_entertainment",
                "description": "Search entertainment vendors in a city using Google Places.",
                "parameters": EntertainmentSearchInput.model_json_schema(),
            },
            {
                "name": "generate_budget_breakdown",
                "description": "Generate a deterministic event budget breakdown.",
                "parameters": BudgetBreakdownInput.model_json_schema(),
            },
            {
                "name": "create_task_plan",
                "description": "Generate a deterministic task plan from shared event templates.",
                "parameters": TaskPlanInput.model_json_schema(),
            },
        ]

    async def search_venues(
        self,
        city: str,
        event_type: str,
        indoor_outdoor: str = "either",
        guest_count: Optional[int] = None,
        budget: Any = None,
    ) -> GooglePlacesSearchResponse:
        request = VenueSearchInput(
            city=city,
            event_type=event_type,
            indoor_outdoor=indoor_outdoor,
            guest_count=guest_count,
            budget=self._normalize_budget_range(budget),
        )
        query = self._build_venue_query(request)
        included_type = self._resolve_venue_type(request.event_type)
        budget_levels = self._price_levels_for_budget(
            request.budget,
            guest_count=request.guest_count,
            search_kind="venue",
        )
        assumptions = [
            "Google price levels are relative hints, not hard quotes.",
            "Guest count and indoor/outdoor preferences are used as search hints because Places does not expose reliable capacity metadata.",
        ]
        return await self._search_places(
            tool_name="search_venues",
            city=request.city,
            query=query,
            budget=request.budget,
            included_type=included_type,
            budget_levels=budget_levels,
            preferred_types=PREFERRED_TYPES["venue"],
            preferred_keywords=[
                request.event_type,
                request.indoor_outdoor,
                "venue",
                "banquet",
                "private event",
            ],
            include_pure_service_area_businesses=False,
            assumptions=assumptions,
        )

    async def get_place_details(self, place_id: str) -> GooglePlaceDetails:
        request = PlaceDetailsInput(place_id=place_id)
        place = await self.places_client.get_place_details(
            request.place_id,
            field_mask=DETAIL_FIELD_MASK,
        )
        return self._to_place_details(place)

    async def search_caterers(
        self,
        city: str,
        cuisine: Optional[str] = None,
        budget_range: Any = None,
    ) -> GooglePlacesSearchResponse:
        request = CatererSearchInput(
            city=city,
            cuisine=cuisine,
            budget_range=self._normalize_budget_range(budget_range),
        )
        cuisine_hint = f"{request.cuisine} " if request.cuisine else ""
        query = f"{cuisine_hint}caterer in {request.city}".strip()
        assumptions = [
            "Google Places can return restaurants and catering-service businesses for this search.",
            "Service-area businesses are included where Google exposes them.",
        ]
        return await self._search_places(
            tool_name="search_caterers",
            city=request.city,
            query=query,
            budget=request.budget_range,
            included_type="catering_service",
            budget_levels=self._price_levels_for_budget(request.budget_range),
            preferred_types=PREFERRED_TYPES["caterer"],
            preferred_keywords=[request.cuisine or "", "caterer", "catering", "restaurant"],
            include_pure_service_area_businesses=True,
            assumptions=assumptions,
        )

    async def search_decorators(
        self,
        city: str,
        vibe: Optional[str] = None,
        budget_range: Any = None,
    ) -> GooglePlacesSearchResponse:
        request = DecoratorSearchInput(
            city=city,
            vibe=vibe,
            budget_range=self._normalize_budget_range(budget_range),
        )
        vibe_hint = f"{request.vibe} " if request.vibe else ""
        query = f"{vibe_hint}event decorator in {request.city}".strip()
        assumptions = [
            "Decorator discovery is query-driven because Places does not have a dedicated event-decorator type.",
            "Results often include florists and event styling businesses.",
        ]
        return await self._search_places(
            tool_name="search_decorators",
            city=request.city,
            query=query,
            budget=request.budget_range,
            included_type="florist",
            budget_levels=self._price_levels_for_budget(request.budget_range),
            preferred_types=PREFERRED_TYPES["decorator"],
            preferred_keywords=[request.vibe or "", "decorator", "stylist", "event design"],
            include_pure_service_area_businesses=True,
            assumptions=assumptions,
        )

    async def search_entertainment(
        self,
        city: str,
        event_type: str,
        budget_range: Any = None,
    ) -> GooglePlacesSearchResponse:
        request = EntertainmentSearchInput(
            city=city,
            event_type=event_type,
            budget_range=self._normalize_budget_range(budget_range),
        )
        query = f"{request.event_type} DJ MC live band entertainment in {request.city}"
        assumptions = [
            "Entertainment discovery is query-driven because performer profiles are not always structured as venue types in Places.",
            "Results may include live music venues and entertainment vendors with public listings.",
        ]
        return await self._search_places(
            tool_name="search_entertainment",
            city=request.city,
            query=query,
            budget=request.budget_range,
            included_type="live_music_venue",
            budget_levels=self._price_levels_for_budget(request.budget_range),
            preferred_types=PREFERRED_TYPES["entertainment"],
            preferred_keywords=[request.event_type, "dj", "mc", "band", "entertainment"],
            include_pure_service_area_businesses=True,
            assumptions=assumptions,
        )

    def generate_budget_breakdown(
        self,
        total_budget: float,
        event_type: str,
        guest_count: Optional[int] = None,
        currency: str = "USD",
        priorities: Optional[Dict[str, float]] = None,
    ) -> BudgetBreakdownResponse:
        request = BudgetBreakdownInput(
            total_budget=total_budget,
            event_type=event_type,
            guest_count=guest_count,
            currency=currency,
            priorities=priorities or {},
        )
        ratios = dict(
            BASE_BUDGET_ALLOCATIONS.get(
                request.event_type.strip().upper(),
                BASE_BUDGET_ALLOCATIONS["DEFAULT"],
            )
        )
        ratios = self._apply_priority_adjustments(ratios, request.priorities)

        allocations: List[BudgetAllocation] = []
        remaining_budget = round(request.total_budget, 2)
        items = [(category, ratio) for category, ratio in ratios.items() if ratio > 0]
        for index, (category, ratio) in enumerate(items):
            is_last = index == len(items) - 1
            amount = remaining_budget if is_last else round(request.total_budget * ratio, 2)
            remaining_budget = round(remaining_budget - amount, 2)
            allocations.append(
                BudgetAllocation(
                    category=category,
                    percentage=round(ratio * 100, 2),
                    amount=amount,
                    rationale=CATEGORY_RATIONALES[category],
                )
            )

        assumptions = [
            "Budget allocations are deterministic planning heuristics and should be refined with live vendor quotes.",
        ]
        if request.guest_count:
            per_guest = round(request.total_budget / request.guest_count, 2)
            assumptions.append(
                f"Working per-guest budget is {per_guest:.2f} {request.currency}."
            )
        if request.priorities:
            assumptions.append(
                "Priority categories were given extra weight while keeping the overall total fixed."
            )

        return BudgetBreakdownResponse(
            event_type=request.event_type,
            total_budget=request.total_budget,
            currency=request.currency,
            guest_count=request.guest_count,
            allocations=allocations,
            assumptions=assumptions,
        )

    def create_task_plan(self, date: Any, event_type: str) -> TaskPlanResponse:
        request = TaskPlanInput(date=date, event_type=event_type)
        templates = get_task_templates_for_type(request.event_type)
        generated_on = datetime.utcnow().date()
        multiplier = EVENT_TYPE_LEAD_MULTIPLIER.get(
            request.event_type.strip().upper(),
            1.0,
        )

        task_categories: List[TaskPlanCategory] = []
        clamped_deadlines = False
        for category_name, task_titles in templates.items():
            base_lead_days = CATEGORY_LEAD_DAYS.get(category_name, 21)
            lead_days = max(1, int(base_lead_days * multiplier))
            step = max(3, lead_days // max(len(task_titles), 1))
            items: List[TaskPlanItem] = []

            for index, title in enumerate(task_titles):
                item_lead_days = max(0, lead_days - (index * step))
                due_date = request.date - timedelta(days=item_lead_days)
                if due_date < generated_on:
                    due_date = generated_on
                    clamped_deadlines = True
                items.append(
                    TaskPlanItem(
                        title=title,
                        category=category_name,
                        due_date=due_date,
                        lead_time_days=item_lead_days,
                    )
                )

            task_categories.append(TaskPlanCategory(name=category_name, items=items))

        assumptions = [
            "Task sequencing is generated from shared event templates and should be refined once real vendors and dates are locked.",
        ]
        if clamped_deadlines:
            assumptions.append(
                "Some deadlines were moved to today because the ideal planning lead time has already passed."
            )

        return TaskPlanResponse(
            event_type=request.event_type,
            event_date=request.date,
            generated_on=generated_on,
            task_categories=task_categories,
            assumptions=assumptions,
        )

    async def _search_places(
        self,
        *,
        tool_name: str,
        city: str,
        query: str,
        budget: Optional[BudgetRange],
        included_type: Optional[str],
        budget_levels: Optional[List[str]],
        preferred_types: Iterable[str],
        preferred_keywords: Iterable[str],
        include_pure_service_area_businesses: bool,
        assumptions: List[str],
    ) -> GooglePlacesSearchResponse:
        logger.info("Running %s with query '%s'", tool_name, query)
        places = await self.places_client.text_search(
            text_query=query,
            field_mask=SEARCH_FIELD_MASK,
            included_type=included_type,
            price_levels=budget_levels,
            include_pure_service_area_businesses=include_pure_service_area_businesses,
            strict_type_filtering=False,
        )
        if not places and included_type:
            places = await self.places_client.text_search(
                text_query=query,
                field_mask=SEARCH_FIELD_MASK,
                price_levels=budget_levels,
                include_pure_service_area_businesses=include_pure_service_area_businesses,
            )

        candidates = self._rank_candidates(
            places,
            preferred_types=set(preferred_types),
            preferred_keywords=list(preferred_keywords),
            expected_budget_levels=budget_levels,
        )
        return GooglePlacesSearchResponse(
            tool_name=tool_name,
            query=query,
            city=city,
            included_type=included_type,
            budget=budget,
            candidates=candidates,
            assumptions=assumptions,
        )

    def _rank_candidates(
        self,
        places: Sequence[Dict[str, Any]],
        *,
        preferred_types: set[str],
        preferred_keywords: Sequence[str],
        expected_budget_levels: Optional[Sequence[str]],
    ) -> List[GooglePlaceCandidate]:
        candidates: Dict[str, GooglePlaceCandidate] = {}
        for place in places:
            candidate = self._to_candidate(
                place,
                preferred_types=preferred_types,
                preferred_keywords=preferred_keywords,
                expected_budget_levels=expected_budget_levels,
            )
            existing = candidates.get(candidate.place_id)
            if existing is None or candidate.fit_score > existing.fit_score:
                candidates[candidate.place_id] = candidate
        return sorted(
            candidates.values(),
            key=lambda item: (-item.fit_score, -(item.user_rating_count or 0), item.name),
        )

    def _to_candidate(
        self,
        place: Dict[str, Any],
        *,
        preferred_types: set[str],
        preferred_keywords: Sequence[str],
        expected_budget_levels: Optional[Sequence[str]],
    ) -> GooglePlaceCandidate:
        price_level = place.get("priceLevel")
        fit_score, fit_reasons = self._score_candidate(
            place,
            preferred_types=preferred_types,
            preferred_keywords=preferred_keywords,
            expected_budget_levels=expected_budget_levels,
        )
        return GooglePlaceCandidate(
            place_id=place["id"],
            name=self._extract_display_name(place),
            formatted_address=place.get("formattedAddress"),
            short_formatted_address=place.get("shortFormattedAddress"),
            coordinates=self._extract_coordinates(place),
            primary_type=place.get("primaryType"),
            types=place.get("types") or [],
            rating=place.get("rating"),
            user_rating_count=place.get("userRatingCount"),
            price_level=price_level,
            price_level_rank=PRICE_LEVEL_RANKS.get(price_level),
            business_status=place.get("businessStatus"),
            open_now=self._extract_open_now(place),
            pure_service_area_business=place.get("pureServiceAreaBusiness"),
            google_maps_uri=self._extract_google_maps_uri(place),
            fit_score=fit_score,
            fit_reasons=fit_reasons,
        )

    def _to_place_details(self, place: Dict[str, Any]) -> GooglePlaceDetails:
        price_level = place.get("priceLevel")
        photos: List[GooglePlacePhoto] = []
        for photo in place.get("photos") or []:
            photos.append(
                GooglePlacePhoto(
                    name=photo["name"],
                    width_px=photo.get("widthPx"),
                    height_px=photo.get("heightPx"),
                    google_maps_uri=photo.get("googleMapsUri"),
                    author_attributions=[
                        attribution.get("displayName", "")
                        for attribution in photo.get("authorAttributions") or []
                        if attribution.get("displayName")
                    ],
                )
            )

        return GooglePlaceDetails(
            place_id=place["id"],
            name=self._extract_display_name(place),
            formatted_address=place.get("formattedAddress"),
            short_formatted_address=place.get("shortFormattedAddress"),
            coordinates=self._extract_coordinates(place),
            primary_type=place.get("primaryType"),
            types=place.get("types") or [],
            rating=place.get("rating"),
            user_rating_count=place.get("userRatingCount"),
            price_level=price_level,
            price_level_rank=PRICE_LEVEL_RANKS.get(price_level),
            business_status=place.get("businessStatus"),
            open_now=self._extract_open_now(place),
            pure_service_area_business=place.get("pureServiceAreaBusiness"),
            google_maps_uri=self._extract_google_maps_uri(place),
            website_uri=place.get("websiteUri"),
            national_phone_number=place.get("nationalPhoneNumber"),
            regular_opening_hours=self._extract_weekday_descriptions(place),
            photos=photos,
        )

    def _score_candidate(
        self,
        place: Dict[str, Any],
        *,
        preferred_types: set[str],
        preferred_keywords: Sequence[str],
        expected_budget_levels: Optional[Sequence[str]],
    ) -> tuple[float, List[str]]:
        score = 0.0
        reasons: List[str] = []
        place_types = set(place.get("types") or [])
        primary_type = place.get("primaryType")
        name = self._extract_display_name(place).lower()
        address = (place.get("formattedAddress") or "").lower()
        query_haystack = " ".join([name, address, primary_type or "", " ".join(place_types)]).lower()

        if primary_type in preferred_types or place_types.intersection(preferred_types):
            score += 25.0
            reasons.append(f"Primary type matches the search focus ({primary_type}).")

        rating = float(place.get("rating") or 0)
        if rating:
            score += min(30.0, rating * 6.0)
            rating_count = int(place.get("userRatingCount") or 0)
            if rating_count:
                score += min(15.0, math.log10(rating_count + 1) * 7.0)
                reasons.append(
                    f"Strong public rating ({rating:.1f} from {rating_count} Google reviews)."
                )

        price_level = place.get("priceLevel")
        if expected_budget_levels:
            if price_level in expected_budget_levels:
                score += 15.0
                reasons.append(
                    f"Price level fits the {PRICE_LEVEL_LABELS.get(price_level, 'requested')} budget hint."
                )
            elif price_level is None:
                score += 6.0
                reasons.append("Google did not return a price level, so budget fit is uncertain.")
        elif price_level is not None:
            score += 5.0

        matched_keywords = {
            keyword.strip().lower()
            for keyword in preferred_keywords
            if keyword and keyword.strip().lower() in query_haystack
        }
        if matched_keywords:
            score += min(15.0, len(matched_keywords) * 4.0)
            reasons.append(
                "Query terms matched listing content: "
                + ", ".join(sorted(matched_keywords))
                + "."
            )

        if self._extract_open_now(place) is True:
            score += 3.0
        if place.get("businessStatus") == "OPERATIONAL":
            score += 2.0

        if not reasons:
            reasons.append("Returned by Google Places for the requested search.")

        return round(score, 2), reasons[:3]

    def _normalize_budget_range(
        self,
        value: Any,
        *,
        currency_hint: str = "USD",
    ) -> Optional[BudgetRange]:
        if value is None:
            return None
        if isinstance(value, BudgetRange):
            return value
        if isinstance(value, (int, float)):
            return BudgetRange(max_amount=float(value), currency=currency_hint)
        if isinstance(value, str):
            raw_value = value.strip()
            label = raw_value.lower()
            if label in _LOW_BUDGET_LABELS | _MID_BUDGET_LABELS | _HIGH_BUDGET_LABELS:
                return BudgetRange(label=label, currency=currency_hint)

            match = re.match(
                r"^\s*(?P<low>\d+(?:\.\d+)?)\s*[-:]\s*(?P<high>\d+(?:\.\d+)?)\s*$",
                raw_value,
            )
            if match:
                return BudgetRange(
                    min_amount=float(match.group("low")),
                    max_amount=float(match.group("high")),
                    currency=currency_hint,
                )
            raise ValidationError(f"Unsupported budget format: {value}")
        if isinstance(value, dict):
            payload = dict(value)
            if "min" in payload and "min_amount" not in payload:
                payload["min_amount"] = payload.pop("min")
            if "max" in payload and "max_amount" not in payload:
                payload["max_amount"] = payload.pop("max")
            if "amount" in payload and "max_amount" not in payload:
                payload["max_amount"] = payload.pop("amount")
            payload.setdefault("currency", currency_hint)
            return BudgetRange.model_validate(payload)
        raise ValidationError(f"Unsupported budget input type: {type(value)!r}")

    def _price_levels_for_budget(
        self,
        budget: Optional[BudgetRange],
        *,
        guest_count: Optional[int] = None,
        search_kind: str = "vendor",
    ) -> Optional[List[str]]:
        if not budget:
            return None

        if budget.label:
            if budget.label in _LOW_BUDGET_LABELS:
                return ["PRICE_LEVEL_INEXPENSIVE", "PRICE_LEVEL_MODERATE"]
            if budget.label in _MID_BUDGET_LABELS:
                return ["PRICE_LEVEL_MODERATE", "PRICE_LEVEL_EXPENSIVE"]
            if budget.label in _HIGH_BUDGET_LABELS:
                return ["PRICE_LEVEL_EXPENSIVE", "PRICE_LEVEL_VERY_EXPENSIVE"]

        ceiling = budget.max_amount or budget.min_amount
        if ceiling is None:
            return None

        if guest_count:
            per_guest = ceiling / max(guest_count, 1)
        else:
            per_guest = ceiling

        if search_kind == "venue":
            if per_guest <= 50:
                return ["PRICE_LEVEL_INEXPENSIVE", "PRICE_LEVEL_MODERATE"]
            if per_guest <= 150:
                return ["PRICE_LEVEL_MODERATE", "PRICE_LEVEL_EXPENSIVE"]
            return ["PRICE_LEVEL_EXPENSIVE", "PRICE_LEVEL_VERY_EXPENSIVE"]

        if per_guest <= 500:
            return ["PRICE_LEVEL_INEXPENSIVE", "PRICE_LEVEL_MODERATE"]
        if per_guest <= 2000:
            return ["PRICE_LEVEL_MODERATE", "PRICE_LEVEL_EXPENSIVE"]
        return ["PRICE_LEVEL_EXPENSIVE", "PRICE_LEVEL_VERY_EXPENSIVE"]

    def _apply_priority_adjustments(
        self,
        ratios: Dict[str, float],
        priorities: Dict[str, float],
    ) -> Dict[str, float]:
        if not priorities:
            return ratios

        filtered_priorities = {
            category: weight
            for category, weight in priorities.items()
            if category in ratios and weight > 0
        }
        if not filtered_priorities:
            return ratios

        total_priority = sum(filtered_priorities.values())
        adjusted: Dict[str, float] = {}
        for category, ratio in ratios.items():
            priority_ratio = filtered_priorities.get(category, 0.0) / total_priority
            adjusted[category] = (0.7 * ratio) + (0.3 * priority_ratio)

        normalized_total = sum(adjusted.values())
        return {
            category: ratio / normalized_total
            for category, ratio in adjusted.items()
        }

    def _build_venue_query(self, request: VenueSearchInput) -> str:
        parts = [request.event_type]
        if request.indoor_outdoor != "either":
            parts.append(request.indoor_outdoor)
        if request.guest_count:
            parts.append(f"for {request.guest_count} guests")
        parts.append(f"venue in {request.city}")
        return " ".join(part for part in parts if part)

    def _resolve_venue_type(self, event_type: str) -> str:
        normalized = event_type.strip().upper()
        return VENUE_INCLUDED_TYPES.get(normalized, VENUE_INCLUDED_TYPES["DEFAULT"])

    def _extract_display_name(self, place: Dict[str, Any]) -> str:
        display_name = place.get("displayName") or {}
        if isinstance(display_name, dict):
            return display_name.get("text", "")
        return str(display_name)

    def _extract_coordinates(self, place: Dict[str, Any]) -> Optional[Coordinates]:
        location = place.get("location") or {}
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        if latitude is None or longitude is None:
            return None
        return Coordinates(latitude=latitude, longitude=longitude)

    def _extract_open_now(self, place: Dict[str, Any]) -> Optional[bool]:
        for key in ("currentOpeningHours", "regularOpeningHours"):
            hours = place.get(key)
            if isinstance(hours, dict) and "openNow" in hours:
                return hours.get("openNow")
        return None

    def _extract_weekday_descriptions(self, place: Dict[str, Any]) -> List[str]:
        for key in ("currentOpeningHours", "regularOpeningHours"):
            hours = place.get(key)
            if isinstance(hours, dict) and hours.get("weekdayDescriptions"):
                return list(hours["weekdayDescriptions"])
        return []

    def _extract_google_maps_uri(self, place: Dict[str, Any]) -> Optional[str]:
        google_maps_uri = place.get("googleMapsUri")
        if google_maps_uri:
            return google_maps_uri
        place_id = place.get("id")
        if place_id:
            return f"https://www.google.com/maps/place/?q=place_id:{place_id}"
        return None


planning_llm_tools = EventPlanningLLMTools()
TOOL_REGISTRY = planning_llm_tools.get_tool_registry()
TOOL_DEFINITIONS = planning_llm_tools.get_tool_definitions()


async def search_venues(
    city: str,
    event_type: str,
    indoor_outdoor: str = "either",
    guest_count: Optional[int] = None,
    budget: Any = None,
) -> GooglePlacesSearchResponse:
    return await planning_llm_tools.search_venues(
        city=city,
        event_type=event_type,
        indoor_outdoor=indoor_outdoor,
        guest_count=guest_count,
        budget=budget,
    )


async def get_place_details(place_id: str) -> GooglePlaceDetails:
    return await planning_llm_tools.get_place_details(place_id)


async def search_caterers(
    city: str,
    cuisine: Optional[str] = None,
    budget_range: Any = None,
) -> GooglePlacesSearchResponse:
    return await planning_llm_tools.search_caterers(
        city=city,
        cuisine=cuisine,
        budget_range=budget_range,
    )


async def search_decorators(
    city: str,
    vibe: Optional[str] = None,
    budget_range: Any = None,
) -> GooglePlacesSearchResponse:
    return await planning_llm_tools.search_decorators(
        city=city,
        vibe=vibe,
        budget_range=budget_range,
    )


async def search_entertainment(
    city: str,
    event_type: str,
    budget_range: Any = None,
) -> GooglePlacesSearchResponse:
    return await planning_llm_tools.search_entertainment(
        city=city,
        event_type=event_type,
        budget_range=budget_range,
    )


def generate_budget_breakdown(
    total_budget: float,
    event_type: str,
    guest_count: Optional[int] = None,
    currency: str = "USD",
    priorities: Optional[Dict[str, float]] = None,
) -> BudgetBreakdownResponse:
    return planning_llm_tools.generate_budget_breakdown(
        total_budget=total_budget,
        event_type=event_type,
        guest_count=guest_count,
        currency=currency,
        priorities=priorities,
    )


def create_task_plan(date: Any, event_type: str) -> TaskPlanResponse:
    return planning_llm_tools.create_task_plan(date=date, event_type=event_type)
