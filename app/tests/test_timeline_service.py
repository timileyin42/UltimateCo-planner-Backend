import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.services.timeline_service import TimelineService
from app.models.timeline_models import (
    EventTimeline, TimelineItem, TimelineDependency, TimelineTemplate,
    TimelineNotification, TimelineUpdate, TimelineItemType, TimelineStatus
)
from app.models.user_models import User
from app.models.event_models import Event
from app.core.errors import NotFoundError, ValidationError, AuthorizationError

class TestTimelineService:
    """Test cases for TimelineService."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def timeline_service(self, mock_db):
        """Create TimelineService instance with mocked database."""
        return TimelineService(mock_db)
    
    @pytest.fixture
    def mock_user(self):
        """Mock user for testing."""
        user = Mock(spec=User)
        user.id = 1
        user.full_name = "Test User"
        user.email = "test@example.com"
        return user
    
    @pytest.fixture
    def mock_event(self):
        """Mock event for testing."""
        event = Mock(spec=Event)
        event.id = 1
        event.title = "Test Event"
        event.creator_id = 1
        event.start_datetime = datetime.utcnow() + timedelta(days=7)
        event.end_datetime = datetime.utcnow() + timedelta(days=7, hours=4)
        event.collaborators = []
        return event
    
    @pytest.fixture
    def mock_timeline(self):
        """Mock timeline for testing."""
        timeline = Mock(spec=EventTimeline)
        timeline.id = 1
        timeline.title = "Test Timeline"
        timeline.event_id = 1
        timeline.creator_id = 1
        timeline.is_active = True
        timeline.items = []
        return timeline
    
    @pytest.fixture
    def mock_timeline_item(self):
        """Mock timeline item for testing."""
        item = Mock(spec=TimelineItem)
        item.id = 1
        item.title = "Test Item"
        item.timeline_id = 1
        item.item_type = TimelineItemType.ACTIVITY
        item.status = TimelineStatus.PENDING
        item.start_time = datetime.utcnow() + timedelta(hours=1)
        item.end_time = datetime.utcnow() + timedelta(hours=2)
        item.duration_minutes = 60
        return item
    
    # Timeline CRUD tests
    def test_create_timeline_success(self, timeline_service, mock_db, mock_event):
        """Test successful timeline creation."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_event
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        timeline_data = {
            "title": "Test Timeline",
            "description": "Test timeline description",
            "template_id": None
        }
        
        # Execute
        result = timeline_service.create_timeline(1, 1, timeline_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    def test_create_timeline_event_not_found(self, timeline_service, mock_db):
        """Test timeline creation with non-existent event."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        timeline_data = {
            "title": "Test Timeline",
            "description": "Test timeline description"
        }
        
        # Execute & Assert
        with pytest.raises(NotFoundError, match="Event not found"):
            timeline_service.create_timeline(999, 1, timeline_data)
    
    def test_get_timeline_success(self, timeline_service, mock_db, mock_timeline):
        """Test successful timeline retrieval."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_timeline
        
        # Execute
        result = timeline_service.get_timeline(1, 1)
        
        # Assert
        assert result == mock_timeline
    
    def test_get_timeline_not_found(self, timeline_service, mock_db):
        """Test timeline retrieval with non-existent timeline."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = None
        
        # Execute & Assert
        with pytest.raises(NotFoundError, match="Timeline not found"):
            timeline_service.get_timeline(999, 1)
    
    def test_update_timeline_success(self, timeline_service, mock_db, mock_timeline):
        """Test successful timeline update."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_timeline
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        update_data = {
            "title": "Updated Timeline",
            "description": "Updated description"
        }
        
        # Execute
        result = timeline_service.update_timeline(1, 1, update_data)
        
        # Assert
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result == mock_timeline
    
    def test_update_timeline_permission_denied(self, timeline_service, mock_db, mock_timeline):
        """Test timeline update with permission denied."""
        # Setup
        mock_timeline.creator_id = 2  # Different user
        mock_db.query.return_value.filter.return_value.first.return_value = mock_timeline
        
        update_data = {"title": "Updated Timeline"}
        
        # Execute & Assert
        with pytest.raises(AuthorizationError, match="You don't have permission to edit this timeline"):
            timeline_service.update_timeline(1, 1, update_data)
    
    def test_delete_timeline_success(self, timeline_service, mock_db, mock_timeline):
        """Test successful timeline deletion."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_timeline
        mock_db.commit = Mock()
        
        # Execute
        result = timeline_service.delete_timeline(1, 1)
        
        # Assert
        assert result is True
        assert mock_timeline.is_active is False
        mock_db.commit.assert_called_once()
    
    # Timeline Item tests
    def test_add_timeline_item_success(self, timeline_service, mock_db, mock_timeline):
        """Test successful timeline item addition."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_timeline
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        item_data = {
            "title": "Test Item",
            "description": "Test item description",
            "item_type": "activity",
            "start_time": datetime.utcnow() + timedelta(hours=1),
            "duration_minutes": 60
        }
        
        # Execute
        result = timeline_service.add_timeline_item(1, 1, item_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    def test_update_timeline_item_success(self, timeline_service, mock_db, mock_timeline_item):
        """Test successful timeline item update."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_timeline_item
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        update_data = {
            "title": "Updated Item",
            "duration_minutes": 90
        }
        
        # Execute
        result = timeline_service.update_timeline_item(1, 1, update_data)
        
        # Assert
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result == mock_timeline_item
    
    def test_update_item_status_success(self, timeline_service, mock_db, mock_timeline_item):
        """Test successful timeline item status update."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_timeline_item
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        status_data = {
            "status": "in_progress",
            "actual_start_time": datetime.utcnow()
        }
        
        # Execute
        result = timeline_service.update_item_status(1, 1, status_data)
        
        # Assert
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result == mock_timeline_item
    
    def test_delete_timeline_item_success(self, timeline_service, mock_db, mock_timeline_item):
        """Test successful timeline item deletion."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_timeline_item
        mock_db.delete = Mock()
        mock_db.commit = Mock()
        
        # Execute
        result = timeline_service.delete_timeline_item(1, 1)
        
        # Assert
        assert result is True
        mock_db.delete.assert_called_once_with(mock_timeline_item)
        mock_db.commit.assert_called_once()
    
    def test_reorder_timeline_items_success(self, timeline_service, mock_db, mock_timeline):
        """Test successful timeline items reordering."""
        # Setup
        mock_items = [Mock(spec=TimelineItem) for _ in range(3)]
        for i, item in enumerate(mock_items):
            item.id = i + 1
            item.order_index = i
        
        mock_timeline.items = mock_items
        mock_db.query.return_value.filter.return_value.first.return_value = mock_timeline
        mock_db.commit = Mock()
        
        item_orders = [
            {"item_id": 1, "order_index": 2},
            {"item_id": 2, "order_index": 0},
            {"item_id": 3, "order_index": 1}
        ]
        
        # Execute
        result = timeline_service.reorder_timeline_items(1, 1, item_orders)
        
        # Assert
        assert result is True
        mock_db.commit.assert_called_once()
    
    # AI Timeline Generation tests
    @patch('app.services.timeline_service.ai_service')
    def test_generate_ai_timeline_success(self, mock_ai_service, timeline_service, mock_db, mock_event):
        """Test successful AI timeline generation."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_event
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Mock AI service response
        mock_ai_response = [
            {
                "title": "Setup",
                "item_type": "setup",
                "start_time_offset_minutes": 0,
                "duration_minutes": 30
            },
            {
                "title": "Main Event",
                "item_type": "activity",
                "start_time_offset_minutes": 30,
                "duration_minutes": 120
            }
        ]
        mock_ai_service.generate_event_timeline.return_value = mock_ai_response
        
        ai_request = {
            "event_type": "birthday",
            "duration_hours": 3,
            "guest_count": 20,
            "preferences": ["casual", "outdoor"]
        }
        
        # Execute
        result = timeline_service.generate_ai_timeline(1, 1, ai_request)
        
        # Assert
        mock_ai_service.generate_event_timeline.assert_called_once()
        mock_db.add.assert_called()  # Called multiple times for timeline and items
        mock_db.commit.assert_called()
        assert result is not None
    
    # Template tests
    def test_create_template_success(self, timeline_service, mock_db):
        """Test successful template creation."""
        # Setup
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        template_data = {
            "name": "Birthday Party Template",
            "description": "Standard birthday party timeline",
            "event_type": "birthday",
            "duration_hours": 4,
            "template_data": {
                "items": [
                    {"title": "Setup", "duration_minutes": 30},
                    {"title": "Party", "duration_minutes": 180}
                ]
            }
        }
        
        # Execute
        result = timeline_service.create_template(1, template_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    def test_apply_template_success(self, timeline_service, mock_db, mock_event):
        """Test successful template application."""
        # Setup
        mock_template = Mock(spec=TimelineTemplate)
        mock_template.id = 1
        mock_template.name = "Test Template"
        mock_template.template_data = {
            "items": [
                {
                    "title": "Setup",
                    "item_type": "setup",
                    "duration_minutes": 30,
                    "start_time_offset_minutes": 0
                },
                {
                    "title": "Main Event",
                    "item_type": "activity",
                    "duration_minutes": 120,
                    "start_time_offset_minutes": 30
                }
            ]
        }
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_event, mock_template]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Execute
        result = timeline_service.apply_template(1, 1, 1)
        
        # Assert
        mock_db.add.assert_called()  # Called for timeline and items
        mock_db.commit.assert_called()
        assert result is not None
    
    def test_apply_template_not_found(self, timeline_service, mock_db, mock_event):
        """Test template application with non-existent template."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_event, None]
        
        # Execute & Assert
        with pytest.raises(NotFoundError, match="Template not found"):
            timeline_service.apply_template(1, 1, 999)
    
    # Statistics tests
    def test_get_timeline_statistics_success(self, timeline_service, mock_db, mock_timeline):
        """Test successful timeline statistics retrieval."""
        # Setup
        mock_items = []
        for i in range(10):
            item = Mock(spec=TimelineItem)
            if i < 3:
                item.status = TimelineStatus.COMPLETED
            elif i < 5:
                item.status = TimelineStatus.IN_PROGRESS
            elif i < 8:
                item.status = TimelineStatus.PENDING
            else:
                item.status = TimelineStatus.DELAYED
                item.end_time = datetime.utcnow() - timedelta(hours=1)  # Overdue
            mock_items.append(item)
        
        mock_timeline.items = mock_items
        mock_db.query.return_value.filter.return_value.first.return_value = mock_timeline
        
        # Execute
        stats = timeline_service.get_timeline_statistics(1, 1)
        
        # Assert
        assert stats["total_items"] == 10
        assert stats["completed_items"] == 3
        assert stats["in_progress_items"] == 2
        assert stats["pending_items"] == 3
        assert stats["overdue_items"] == 2
        assert stats["completion_percentage"] == 30.0
    
    # Helper method tests
    def test_get_event_with_access_success(self, timeline_service, mock_db, mock_event):
        """Test successful event access check."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_event
        
        # Execute
        result = timeline_service._get_event_with_access(1, 1)
        
        # Assert
        assert result == mock_event
    
    def test_get_event_with_access_not_found(self, timeline_service, mock_db):
        """Test event access check with non-existent event."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = None
        
        # Execute & Assert
        with pytest.raises(NotFoundError, match="Event not found"):
            timeline_service._get_event_with_access(999, 1)
    
    def test_can_edit_timeline_creator(self, timeline_service, mock_timeline, mock_event):
        """Test timeline edit permission for creator."""
        # Setup
        mock_timeline.creator_id = 1
        mock_event.creator_id = 2
        
        # Execute
        result = timeline_service._can_edit_timeline(mock_timeline, mock_event, 1)
        
        # Assert
        assert result is True
    
    def test_can_edit_timeline_event_creator(self, timeline_service, mock_timeline, mock_event):
        """Test timeline edit permission for event creator."""
        # Setup
        mock_timeline.creator_id = 2
        mock_event.creator_id = 1
        
        # Execute
        result = timeline_service._can_edit_timeline(mock_timeline, mock_event, 1)
        
        # Assert
        assert result is True
    
    def test_can_edit_timeline_denied(self, timeline_service, mock_timeline, mock_event):
        """Test timeline edit permission denied."""
        # Setup
        mock_timeline.creator_id = 2
        mock_event.creator_id = 3
        
        # Execute
        result = timeline_service._can_edit_timeline(mock_timeline, mock_event, 1)
        
        # Assert
        assert result is False
    
    def test_calculate_item_end_time(self, timeline_service):
        """Test timeline item end time calculation."""
        # Setup
        start_time = datetime(2024, 1, 1, 10, 0, 0)
        duration_minutes = 90
        
        # Execute
        end_time = timeline_service._calculate_item_end_time(start_time, duration_minutes)
        
        # Assert
        expected_end_time = datetime(2024, 1, 1, 11, 30, 0)
        assert end_time == expected_end_time
    
    def test_validate_timeline_items_no_conflicts(self, timeline_service):
        """Test timeline items validation with no conflicts."""
        # Setup
        items = [
            {
                "start_time": datetime(2024, 1, 1, 10, 0, 0),
                "end_time": datetime(2024, 1, 1, 11, 0, 0)
            },
            {
                "start_time": datetime(2024, 1, 1, 11, 30, 0),
                "end_time": datetime(2024, 1, 1, 12, 30, 0)
            }
        ]
        
        # Execute
        conflicts = timeline_service._validate_timeline_items(items)
        
        # Assert
        assert len(conflicts) == 0
    
    def test_validate_timeline_items_with_conflicts(self, timeline_service):
        """Test timeline items validation with conflicts."""
        # Setup
        items = [
            {
                "start_time": datetime(2024, 1, 1, 10, 0, 0),
                "end_time": datetime(2024, 1, 1, 11, 30, 0)
            },
            {
                "start_time": datetime(2024, 1, 1, 11, 0, 0),
                "end_time": datetime(2024, 1, 1, 12, 0, 0)
            }
        ]
        
        # Execute
        conflicts = timeline_service._validate_timeline_items(items)
        
        # Assert
        assert len(conflicts) > 0
    
    # Integration-style tests
    def test_timeline_workflow_integration(self, timeline_service, mock_db, mock_event):
        """Test complete timeline workflow integration."""
        # Setup mocks for the entire workflow
        mock_timeline = Mock(spec=EventTimeline)
        mock_timeline.id = 1
        mock_timeline.creator_id = 1
        mock_timeline.items = []
        
        mock_item = Mock(spec=TimelineItem)
        mock_item.id = 1
        
        # Mock database interactions
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_event,  # For create_timeline
            mock_timeline,  # For add_timeline_item
            mock_item,  # For update_item_status
        ]
        
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_timeline
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Execute workflow
        # 1. Create timeline
        timeline_data = {"title": "Test Timeline", "description": "Test description"}
        timeline = timeline_service.create_timeline(1, 1, timeline_data)
        
        # 2. Add timeline item
        item_data = {
            "title": "Test Item",
            "item_type": "activity",
            "start_time": datetime.utcnow() + timedelta(hours=1),
            "duration_minutes": 60
        }
        item = timeline_service.add_timeline_item(1, 1, item_data)
        
        # 3. Update item status
        status_data = {"status": "in_progress"}
        updated_item = timeline_service.update_item_status(1, 1, status_data)
        
        # Assert all operations succeeded
        assert mock_db.add.call_count >= 2  # timeline and item
        assert mock_db.commit.call_count >= 3  # create, add item, update status
        assert timeline is not None
        assert item is not None
        assert updated_item is not None
    
    def test_timeline_with_dependencies(self, timeline_service, mock_db, mock_timeline):
        """Test timeline with item dependencies."""
        # Setup
        mock_item1 = Mock(spec=TimelineItem)
        mock_item1.id = 1
        mock_item1.title = "Setup"
        
        mock_item2 = Mock(spec=TimelineItem)
        mock_item2.id = 2
        mock_item2.title = "Main Event"
        
        mock_timeline.items = [mock_item1, mock_item2]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_timeline
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        dependency_data = {
            "dependent_item_id": 2,
            "prerequisite_item_id": 1,
            "dependency_type": "finish_to_start"
        }
        
        # Execute
        result = timeline_service.add_item_dependency(1, 1, dependency_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        assert result is not None