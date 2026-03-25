import json
from datetime import date

import httpx
import pytest

from app.llm_tools.google_places import GooglePlacesClient
from app.llm_tools.planning_tools import EventPlanningLLMTools


class StubPlacesClient:
    def __init__(self, *, places=None, details=None):
        self.places = places or []
        self.details = details or {}
        self.search_calls = []
        self.details_calls = []

    async def text_search(self, **kwargs):
        self.search_calls.append(kwargs)
        return list(self.places)

    async def get_place_details(self, place_id, **kwargs):
        self.details_calls.append({"place_id": place_id, **kwargs})
        return self.details[place_id]


@pytest.mark.asyncio
async def test_google_places_text_search_builds_expected_request():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["headers"] = dict(request.headers)
        captured["payload"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "places": [
                    {
                        "id": "place-1",
                        "displayName": {"text": "Skyline Event Centre"},
                    }
                ]
            },
        )

    client = GooglePlacesClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    results = await client.text_search(
        text_query="wedding venue in Lagos",
        field_mask="places.id,places.displayName",
        included_type="wedding_venue",
        price_levels=["PRICE_LEVEL_MODERATE"],
        open_now=True,
        include_pure_service_area_businesses=False,
    )

    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/places:searchText"
    assert captured["headers"]["x-goog-api-key"] == "test-key"
    assert captured["headers"]["x-goog-fieldmask"] == "places.id,places.displayName"
    assert captured["payload"]["textQuery"] == "wedding venue in Lagos"
    assert captured["payload"]["includedType"] == "wedding_venue"
    assert captured["payload"]["priceLevels"] == ["PRICE_LEVEL_MODERATE"]
    assert captured["payload"]["openNow"] is True
    assert results[0]["id"] == "place-1"


@pytest.mark.asyncio
async def test_google_places_get_place_details_builds_expected_request():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["headers"] = dict(request.headers)
        captured["query"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "id": "place-123",
                "displayName": {"text": "Skyline Event Centre"},
            },
        )

    client = GooglePlacesClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    result = await client.get_place_details(
        "place-123",
        field_mask="id,displayName",
    )

    assert captured["method"] == "GET"
    assert captured["path"] == "/v1/places/place-123"
    assert captured["headers"]["x-goog-fieldmask"] == "id,displayName"
    assert captured["query"]["languageCode"] == "en"
    assert result["id"] == "place-123"


@pytest.mark.asyncio
async def test_search_venues_scores_google_places_results():
    stub_client = StubPlacesClient(
        places=[
            {
                "id": "venue-1",
                "displayName": {"text": "Skyline Event Centre"},
                "formattedAddress": "10 Admiralty Way, Lagos",
                "shortFormattedAddress": "Admiralty Way, Lagos",
                "location": {"latitude": 6.431, "longitude": 3.455},
                "primaryType": "event_venue",
                "types": ["event_venue", "point_of_interest"],
                "rating": 4.8,
                "userRatingCount": 210,
                "priceLevel": "PRICE_LEVEL_MODERATE",
                "businessStatus": "OPERATIONAL",
                "regularOpeningHours": {"openNow": True},
                "googleMapsUri": "https://maps.google.com/?cid=venue-1",
            },
            {
                "id": "venue-2",
                "displayName": {"text": "Budget Banquet Hall"},
                "formattedAddress": "12 Broad St, Lagos",
                "location": {"latitude": 6.45, "longitude": 3.39},
                "primaryType": "banquet_hall",
                "types": ["banquet_hall"],
                "rating": 4.1,
                "userRatingCount": 40,
                "priceLevel": "PRICE_LEVEL_INEXPENSIVE",
                "businessStatus": "OPERATIONAL",
            },
        ]
    )
    tools = EventPlanningLLMTools(places_client=stub_client)

    result = await tools.search_venues(
        city="Lagos",
        event_type="birthday",
        indoor_outdoor="indoor",
        guest_count=40,
        budget={"max": 4000, "currency": "USD"},
    )

    assert result.tool_name == "search_venues"
    assert result.included_type == "event_venue"
    assert result.candidates[0].place_id == "venue-1"
    assert result.candidates[0].price_level_rank == 2
    assert result.candidates[0].fit_score > result.candidates[1].fit_score
    assert "Guest count and indoor/outdoor preferences are used as search hints" in result.assumptions[1]
    assert stub_client.search_calls[0]["included_type"] == "event_venue"


@pytest.mark.asyncio
async def test_get_place_details_normalizes_photos_and_hours():
    stub_client = StubPlacesClient(
        details={
            "place-123": {
                "id": "place-123",
                "displayName": {"text": "Skyline Event Centre"},
                "formattedAddress": "10 Admiralty Way, Lagos",
                "location": {"latitude": 6.431, "longitude": 3.455},
                "primaryType": "event_venue",
                "types": ["event_venue"],
                "rating": 4.8,
                "userRatingCount": 210,
                "priceLevel": "PRICE_LEVEL_EXPENSIVE",
                "businessStatus": "OPERATIONAL",
                "websiteUri": "https://skyline.example.com",
                "nationalPhoneNumber": "+234 800 000 0000",
                "currentOpeningHours": {
                    "openNow": True,
                    "weekdayDescriptions": ["Monday: 9:00 AM - 5:00 PM"],
                },
                "photos": [
                    {
                        "name": "places/place-123/photos/photo-1",
                        "widthPx": 1200,
                        "heightPx": 800,
                        "googleMapsUri": "https://maps.google.com/photo-1",
                        "authorAttributions": [{"displayName": "Planetal"}],
                    }
                ],
            }
        }
    )
    tools = EventPlanningLLMTools(places_client=stub_client)

    result = await tools.get_place_details("place-123")

    assert result.place_id == "place-123"
    assert result.price_level_rank == 3
    assert result.open_now is True
    assert result.photos[0].name == "places/place-123/photos/photo-1"
    assert result.regular_opening_hours == ["Monday: 9:00 AM - 5:00 PM"]


def test_budget_breakdown_applies_priority_weighting():
    tools = EventPlanningLLMTools(places_client=StubPlacesClient())

    result = tools.generate_budget_breakdown(
        total_budget=10000,
        event_type="wedding",
        guest_count=100,
        currency="USD",
        priorities={"decor": 3, "venue": 1},
    )

    total_allocated = round(sum(item.amount for item in result.allocations), 2)
    decor_allocation = next(item for item in result.allocations if item.category == "decor")

    assert total_allocated == 10000.00
    assert decor_allocation.percentage > 18.0
    assert "Priority categories were given extra weight" in result.assumptions[-1]


def test_create_task_plan_uses_shared_templates():
    tools = EventPlanningLLMTools(places_client=StubPlacesClient())

    result = tools.create_task_plan(date=date(2026, 12, 12), event_type="birthday")

    category_names = [category.name for category in result.task_categories]
    due_dates = [
        item.due_date
        for category in result.task_categories
        for item in category.items
    ]

    assert {"Food", "Guests", "Logistics", "Extras"}.issubset(set(category_names))
    assert all(due_date <= date(2026, 12, 12) for due_date in due_dates)
    assert all(due_date >= result.generated_on for due_date in due_dates)
    assert "Task sequencing is generated from shared event templates" in result.assumptions[0]


def test_tool_definitions_expose_expected_names():
    tools = EventPlanningLLMTools(places_client=StubPlacesClient())

    tool_names = {definition["name"] for definition in tools.get_tool_definitions()}

    assert tool_names == {
        "search_venues",
        "get_place_details",
        "search_caterers",
        "search_decorators",
        "search_entertainment",
        "generate_budget_breakdown",
        "create_task_plan",
    }
