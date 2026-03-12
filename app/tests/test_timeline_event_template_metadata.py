from datetime import datetime
from types import SimpleNamespace

from app.services.timeline_service import TimelineService


class TestTimelineEventTemplateMetadata:
    def test_get_event_template_metadata_maps_event_and_tasks(self):
        service = TimelineService.__new__(TimelineService)
        event = SimpleNamespace(
            id=42,
            title="Launch Party",
            description="Product celebration",
            event_type="other",
            status="confirmed",
            start_datetime=datetime(2026, 8, 20, 18, 0, 0),
            end_datetime=datetime(2026, 8, 20, 22, 0, 0),
            cover_image_url="https://example.com/cover.jpg",
            total_budget=5000.0,
            attendee_count=28,
            task_categories=[
                {
                    "name": "Logistics",
                    "items": [
                        {"title": "Book venue", "description": "Reserve hall", "completed": True},
                        {"title": "Arrange chairs", "description": "Layout setup", "completed": False}
                    ]
                }
            ]
        )
        service._get_event_with_access = lambda event_id, user_id: event

        metadata = service.get_event_template_metadata(42, 3)

        assert metadata["event_id"] == 42
        assert metadata["title"] == "Launch Party"
        assert metadata["event_type"] == "other"
        assert metadata["status"] == "confirmed"
        assert metadata["task_categories"][0]["name"] == "Logistics"
        assert metadata["template_data"]["source"] == "event"
        assert len(metadata["template_data"]["items"]) == 2

    def test_get_event_template_metadata_handles_empty_categories(self):
        service = TimelineService.__new__(TimelineService)
        event = SimpleNamespace(
            id=7,
            title="Simple Event",
            description=None,
            event_type="trip",
            status="confirmed",
            start_datetime=None,
            end_datetime=None,
            cover_image_url=None,
            total_budget=None,
            attendee_count=0,
            task_categories=[]
        )
        service._get_event_with_access = lambda event_id, user_id: event

        metadata = service.get_event_template_metadata(7, 1)

        assert metadata["event_id"] == 7
        assert metadata["task_categories"] == []
        assert metadata["template_data"]["items"] == []
