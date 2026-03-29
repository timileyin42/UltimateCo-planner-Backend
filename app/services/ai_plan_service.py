import json
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.models.ai_chat_models import AIChatSession
from app.models.event_models import Event
from app.schemas.chat import ChatPlanData
from app.schemas.event import EventCreate
from app.services.event_service import EventService


class AIPlanService:
    """Normalize persisted AI plan data and convert it into event records."""

    def __init__(self, db: Session):
        self.db = db
        self.event_service = EventService(db)

    def get_plan(self, session: AIChatSession) -> ChatPlanData:
        raw_event_data = self._loads(session.event_data)
        raw_plan_data = self._loads(session.plan_data)
        merged = self._merge_dicts(raw_event_data, raw_plan_data)
        return ChatPlanData.model_validate(merged)

    def get_plan_payload(self, session: AIChatSession) -> Dict[str, Any]:
        return self.get_plan(session).model_dump(mode="json", exclude_none=True)

    def build_legacy_event_data(self, plan: ChatPlanData) -> Dict[str, Any]:
        legacy: Dict[str, Any] = {}

        if plan.title:
            legacy["title"] = plan.title
        if plan.description:
            legacy["description"] = plan.description
        if plan.event_type:
            legacy["event_type"] = plan.event_type
        if plan.start_datetime:
            legacy["start_date"] = plan.start_datetime.isoformat()
        if plan.end_datetime:
            legacy["end_date"] = plan.end_datetime.isoformat()
        if plan.location_input:
            legacy["location"] = plan.location_input
        elif plan.venue_address:
            legacy["location"] = plan.venue_address
        elif plan.venue_name:
            legacy["location"] = plan.venue_name
        if plan.max_attendees is not None:
            legacy["guest_count"] = plan.max_attendees
        if plan.total_budget is not None:
            legacy["budget"] = plan.total_budget
        if plan.currency:
            legacy["currency"] = plan.currency

        return legacy

    async def create_event_from_session(self, session: AIChatSession, creator_id: int) -> Event:
        event_create = self.build_event_create(session)
        event = await self.event_service.create_event(event_create, creator_id)
        event.ai_plan_data = json.dumps(self.get_plan_payload(session))
        self.db.add(event)
        self.db.flush()
        self.db.refresh(event)
        return event

    def build_event_create(self, session: AIChatSession) -> EventCreate:
        plan = self.get_plan(session)
        start_datetime = plan.start_datetime
        if start_datetime is None:
            raise ValidationError(
                "Plan is missing start_datetime. Save a structured plan before creating the event."
            )

        location_input = plan.location_input or plan.venue_address or plan.venue_name

        return EventCreate(
            title=plan.title or self._default_title(plan),
            description=plan.description,
            event_type=plan.event_type or "other",
            start_datetime=start_datetime,
            end_datetime=plan.end_datetime,
            timezone=plan.timezone,
            venue_name=plan.venue_name,
            venue_address=plan.venue_address,
            venue_city=plan.venue_city,
            venue_country=plan.venue_country,
            latitude=plan.latitude,
            longitude=plan.longitude,
            is_public=bool(plan.is_public),
            max_attendees=plan.max_attendees,
            total_budget=plan.total_budget,
            currency=plan.currency or "USD",
            location_input=location_input,
            auto_optimize_location=bool(location_input and (plan.latitude is None or plan.longitude is None)),
            task_categories=plan.task_categories,
        )

    def _default_title(self, plan: ChatPlanData) -> str:
        event_type = (plan.event_type or "planned").replace("_", " ").strip()
        return f"{event_type.title()} Event"

    def _loads(self, value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    def _merge_dicts(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(base)
        for key, value in override.items():
            if value is None:
                continue
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._merge_dicts(merged[key], value)
            else:
                merged[key] = value
        return merged
