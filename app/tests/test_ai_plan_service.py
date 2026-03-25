import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

from app.schemas.chat import (
    ChatMessageRole,
    ChatSessionResponse,
    ChatSessionStatus,
)
from app.services.ai_plan_service import AIPlanService


def test_build_event_create_from_structured_plan():
    service = AIPlanService(Mock())
    session = SimpleNamespace(
        event_data=json.dumps(
            {
                "title": "Birthday Dinner",
                "event_type": "birthday",
                "start_date": "2026-08-12T18:00:00",
                "guest_count": 25,
                "budget": 150000,
                "currency": "NGN",
            }
        ),
        plan_data=json.dumps(
            {
                "venue_name": "Skyline Rooftop",
                "venue_address": "12 Admiralty Way, Lekki",
                "venue_city": "Lagos",
                "task_categories": [
                    {
                        "name": "Venue",
                        "items": [
                            {"title": "Confirm deposit", "completed": False},
                        ],
                    }
                ],
            }
        ),
    )

    event_create = service.build_event_create(session)

    assert event_create.title == "Birthday Dinner"
    assert event_create.event_type == "birthday"
    assert event_create.start_datetime == datetime(2026, 8, 12, 18, 0, 0)
    assert event_create.max_attendees == 25
    assert event_create.total_budget == 150000
    assert event_create.currency == "NGN"
    assert event_create.venue_city == "Lagos"
    assert event_create.task_categories[0].name == "Venue"


def test_chat_session_response_parses_json_fields():
    response = ChatSessionResponse(
        id="session-123",
        user_id=7,
        status=ChatSessionStatus.ACTIVE,
        messages=[
            {
                "role": ChatMessageRole.ASSISTANT,
                "content": "Here is your draft plan.",
                "timestamp": datetime(2026, 3, 24, 9, 0, 0),
            }
        ],
        event_data='{"title": "Draft Event", "budget": 2000}',
        plan_data='{"title": "Draft Event", "total_budget": 2000, "currency": "ngn"}',
        llm_metadata='{"provider": "openai", "model": "gpt-5.4-nano"}',
        created_at=datetime(2026, 3, 24, 9, 0, 0),
        updated_at=datetime(2026, 3, 24, 9, 5, 0),
    )

    assert response.event_data["title"] == "Draft Event"
    assert response.plan_data.total_budget == 2000
    assert response.plan_data.currency == "NGN"
    assert response.llm_metadata["model"] == "gpt-5.4-nano"
