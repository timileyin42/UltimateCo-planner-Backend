"""Thin async client for Google Places API (New)."""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

import httpx

from app.core.config import get_settings
from app.core.errors import ValidationError
from app.core.logger import get_logger

logger = get_logger(__name__)


class GooglePlacesClient:
    """Async client for the Google Places API (New)."""

    BASE_URL = "https://places.googleapis.com/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        timeout: float = 10.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = (
            api_key
            or settings.GOOGLE_PLACES_API_KEY
            or settings.GOOGLE_MAPS_API_KEY
        )
        self.language_code = settings.GOOGLE_PLACES_LANGUAGE_CODE
        self.region_code = settings.GOOGLE_PLACES_REGION_CODE
        self.default_page_size = settings.GOOGLE_PLACES_DEFAULT_PAGE_SIZE
        self.default_min_rating = settings.GOOGLE_PLACES_DEFAULT_MIN_RATING
        self.timeout = timeout
        self.transport = transport

    def is_available(self) -> bool:
        """Return True when a Places API key is configured."""

        return bool(self.api_key)

    async def text_search(
        self,
        *,
        text_query: str,
        field_mask: str,
        included_type: Optional[str] = None,
        price_levels: Optional[Sequence[str]] = None,
        min_rating: Optional[float] = None,
        open_now: Optional[bool] = None,
        rank_preference: str = "RELEVANCE",
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
        language_code: Optional[str] = None,
        region_code: Optional[str] = None,
        include_pure_service_area_businesses: Optional[bool] = None,
        strict_type_filtering: bool = False,
    ) -> Dict[str, Any]:
        """Run a Places text search."""

        payload: Dict[str, Any] = {
            "textQuery": text_query,
            "pageSize": page_size or self.default_page_size,
            "languageCode": language_code or self.language_code,
            "rankPreference": rank_preference,
        }
        if page_token:
            payload["pageToken"] = page_token
        if included_type:
            payload["includedType"] = included_type
            payload["strictTypeFiltering"] = strict_type_filtering
        if price_levels:
            payload["priceLevels"] = list(price_levels)
        if min_rating is not None:
            payload["minRating"] = min_rating
        elif self.default_min_rating is not None:
            payload["minRating"] = self.default_min_rating
        if open_now is not None:
            payload["openNow"] = open_now
        if include_pure_service_area_businesses is not None:
            payload["includePureServiceAreaBusinesses"] = (
                include_pure_service_area_businesses
            )

        effective_region_code = region_code or self.region_code
        if effective_region_code:
            payload["regionCode"] = effective_region_code

        data = await self._request(
            "POST",
            "/places:searchText",
            field_mask=field_mask,
            json=payload,
        )
        return {
            "places": data.get("places", []),
            "next_page_token": data.get("nextPageToken"),
            "search_uri": data.get("searchUri"),
        }

    async def get_place_details(
        self,
        place_id: str,
        *,
        field_mask: str,
        language_code: Optional[str] = None,
        region_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch details for a single place ID."""

        params: Dict[str, Any] = {}
        if language_code or self.language_code:
            params["languageCode"] = language_code or self.language_code
        if region_code or self.region_code:
            params["regionCode"] = region_code or self.region_code

        return await self._request(
            "GET",
            f"/places/{place_id}",
            field_mask=field_mask,
            params=params,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        field_mask: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ValidationError("Google Places API key not configured")

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": field_mask,
        }

        try:
            async with httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.request(
                    method,
                    path,
                    headers=headers,
                    json=json,
                    params=params,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Google Places request failed with status %s: %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise ValidationError(
                f"Google Places API error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Google Places request transport error: %s", exc)
            raise ValidationError(f"Google Places request failed: {exc}") from exc
