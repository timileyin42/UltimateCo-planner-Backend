import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime
from app.services.creative_service import CreativeService
from app.models.creative_models import (
    Moodboard, MoodboardItem, MoodboardLike, MoodboardComment,
    Playlist, PlaylistTrack, PlaylistVote,
    Game, GameSession, GameParticipation, GameRating,
    MoodboardType, PlaylistType, GameType
)
from app.models.user_models import User
from app.models.event_models import Event
from app.core.errors import NotFoundError, ValidationError, AuthorizationError

class TestCreativeService:
    """Test cases for CreativeService."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def creative_service(self, mock_db):
        """Create CreativeService instance with mocked database."""
        return CreativeService(mock_db)
    
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
        event.collaborators = []
        return event
    
    @pytest.fixture
    def mock_moodboard(self):
        """Mock moodboard for testing."""
        moodboard = Mock(spec=Moodboard)
        moodboard.id = 1
        moodboard.title = "Test Moodboard"
        moodboard.event_id = 1
        moodboard.creator_id = 1
        moodboard.type = MoodboardType.VISION_BOARD
        moodboard.is_public = True
        moodboard.items = []
        moodboard.likes = []
        moodboard.comments = []
        return moodboard
    
    # Moodboard tests
    def test_create_moodboard_success(self, creative_service, mock_db, mock_event):
        """Test successful moodboard creation."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_event
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        moodboard_data = {
            "title": "Test Moodboard",
            "description": "Test description",
            "type": "vision_board",
            "is_public": True
        }
        
        # Execute
        result = creative_service.create_moodboard(1, 1, moodboard_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    def test_create_moodboard_event_not_found(self, creative_service, mock_db):
        """Test moodboard creation with non-existent event."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        moodboard_data = {
            "title": "Test Moodboard",
            "type": "vision_board"
        }
        
        # Execute & Assert
        with pytest.raises(NotFoundError, match="Event not found"):
            creative_service.create_moodboard(999, 1, moodboard_data)
    
    def test_get_moodboard_success(self, creative_service, mock_db, mock_moodboard):
        """Test successful moodboard retrieval."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_moodboard
        
        # Execute
        result = creative_service.get_moodboard(1, 1)
        
        # Assert
        assert result == mock_moodboard
    
    def test_get_moodboard_not_found(self, creative_service, mock_db):
        """Test moodboard retrieval with non-existent moodboard."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = None
        
        # Execute & Assert
        with pytest.raises(NotFoundError, match="Moodboard not found"):
            creative_service.get_moodboard(999, 1)
    
    def test_add_moodboard_item_success(self, creative_service, mock_db, mock_moodboard):
        """Test successful moodboard item addition."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_moodboard
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        item_data = {
            "title": "Test Item",
            "image_url": "https://example.com/image.jpg",
            "description": "Test item description"
        }
        
        # Execute
        result = creative_service.add_moodboard_item(1, 1, item_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    def test_like_moodboard_success(self, creative_service, mock_db, mock_moodboard):
        """Test successful moodboard like."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_moodboard, None]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Execute
        result = creative_service.like_moodboard(1, 1)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        assert result is not None
    
    def test_like_moodboard_already_liked(self, creative_service, mock_db, mock_moodboard):
        """Test liking an already liked moodboard."""
        # Setup
        mock_like = Mock(spec=MoodboardLike)
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_moodboard, mock_like]
        
        # Execute & Assert
        with pytest.raises(ValidationError, match="You have already liked this moodboard"):
            creative_service.like_moodboard(1, 1)
    
    def test_add_moodboard_comment_success(self, creative_service, mock_db, mock_moodboard):
        """Test successful moodboard comment addition."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_moodboard
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        comment_data = {
            "content": "Great moodboard!"
        }
        
        # Execute
        result = creative_service.add_moodboard_comment(1, 1, comment_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    # Playlist tests
    def test_create_playlist_success(self, creative_service, mock_db, mock_event):
        """Test successful playlist creation."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_event
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        playlist_data = {
            "title": "Test Playlist",
            "description": "Test playlist description",
            "type": "collaborative",
            "is_public": True
        }
        
        # Execute
        result = creative_service.create_playlist(1, 1, playlist_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    def test_add_playlist_track_success(self, creative_service, mock_db):
        """Test successful playlist track addition."""
        # Setup
        mock_playlist = Mock(spec=Playlist)
        mock_playlist.id = 1
        mock_playlist.creator_id = 1
        mock_playlist.tracks = []
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_playlist
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        track_data = {
            "title": "Test Song",
            "artist": "Test Artist",
            "spotify_id": "spotify:track:123",
            "duration_ms": 180000
        }
        
        # Execute
        result = creative_service.add_playlist_track(1, 1, track_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    def test_vote_playlist_track_success(self, creative_service, mock_db):
        """Test successful playlist track voting."""
        # Setup
        mock_track = Mock(spec=PlaylistTrack)
        mock_track.id = 1
        mock_track.playlist_id = 1
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_track, None]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Execute
        result = creative_service.vote_playlist_track(1, 1, True)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        assert result is not None
    
    # Game tests
    def test_create_game_success(self, creative_service, mock_db, mock_event):
        """Test successful game creation."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_event
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        game_data = {
            "title": "Test Game",
            "description": "Test game description",
            "type": "icebreaker",
            "max_participants": 10,
            "duration_minutes": 30
        }
        
        # Execute
        result = creative_service.create_game(1, 1, game_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    def test_start_game_session_success(self, creative_service, mock_db):
        """Test successful game session start."""
        # Setup
        mock_game = Mock(spec=Game)
        mock_game.id = 1
        mock_game.event_id = 1
        mock_game.max_participants = 10
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Execute
        result = creative_service.start_game_session(1, 1)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    def test_join_game_session_success(self, creative_service, mock_db):
        """Test successful game session join."""
        # Setup
        mock_session = Mock(spec=GameSession)
        mock_session.id = 1
        mock_session.game_id = 1
        mock_session.status = "waiting"
        mock_session.participants = []
        
        mock_game = Mock(spec=Game)
        mock_game.max_participants = 10
        
        mock_session.game = mock_game
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_session, None]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Execute
        result = creative_service.join_game_session(1, 1)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        assert result is not None
    
    def test_rate_game_success(self, creative_service, mock_db):
        """Test successful game rating."""
        # Setup
        mock_game = Mock(spec=Game)
        mock_game.id = 1
        mock_game.event_id = 1
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_game, None]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        rating_data = {
            "rating": 5,
            "comment": "Great game!"
        }
        
        # Execute
        result = creative_service.rate_game(1, 1, rating_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    # Search and statistics tests
    def test_search_moodboards_success(self, creative_service, mock_db):
        """Test successful moodboard search."""
        # Setup
        mock_moodboards = [Mock(spec=Moodboard) for _ in range(3)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 3
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_moodboards
        
        mock_db.query.return_value.options.return_value = mock_query
        
        search_params = {
            "query": "test",
            "type": "vision_board",
            "page": 1,
            "per_page": 10
        }
        
        # Execute
        moodboards, total = creative_service.search_moodboards(search_params)
        
        # Assert
        assert len(moodboards) == 3
        assert total == 3
    
    def test_get_moodboard_statistics_success(self, creative_service, mock_db, mock_moodboard):
        """Test successful moodboard statistics retrieval."""
        # Setup
        mock_moodboard.items = [Mock() for _ in range(5)]
        mock_moodboard.likes = [Mock() for _ in range(10)]
        mock_moodboard.comments = [Mock() for _ in range(3)]
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_moodboard
        
        # Execute
        stats = creative_service.get_moodboard_statistics(1, 1)
        
        # Assert
        assert stats["total_items"] == 5
        assert stats["total_likes"] == 10
        assert stats["total_comments"] == 3
    
    # Helper method tests
    def test_get_event_with_access_success(self, creative_service, mock_db, mock_event):
        """Test successful event access check."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_event
        
        # Execute
        result = creative_service._get_event_with_access(1, 1)
        
        # Assert
        assert result == mock_event
    
    def test_get_event_with_access_not_found(self, creative_service, mock_db):
        """Test event access check with non-existent event."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = None
        
        # Execute & Assert
        with pytest.raises(NotFoundError, match="Event not found"):
            creative_service._get_event_with_access(999, 1)
    
    def test_get_event_with_access_denied(self, creative_service, mock_db, mock_event):
        """Test event access check with access denied."""
        # Setup
        mock_event.creator_id = 2  # Different user
        mock_event.collaborators = []
        
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_event
        
        # Mock invitation query to return None (no invitation)
        mock_invitation_query = Mock()
        mock_invitation_query.filter.return_value.first.return_value = None
        mock_db.query.side_effect = [Mock().options.return_value, mock_invitation_query]
        
        # Execute & Assert
        with pytest.raises(AuthorizationError, match="You don't have access to this event"):
            creative_service._get_event_with_access(1, 1)
    
    def test_can_edit_moodboard_creator(self, creative_service, mock_moodboard):
        """Test moodboard edit permission for creator."""
        # Setup
        mock_moodboard.creator_id = 1
        
        # Execute
        result = creative_service._can_edit_moodboard(mock_moodboard, 1)
        
        # Assert
        assert result is True
    
    def test_can_edit_moodboard_non_creator(self, creative_service, mock_moodboard):
        """Test moodboard edit permission for non-creator."""
        # Setup
        mock_moodboard.creator_id = 2
        
        # Execute
        result = creative_service._can_edit_moodboard(mock_moodboard, 1)
        
        # Assert
        assert result is False
    
    def test_update_moodboard_stats_success(self, creative_service, mock_db, mock_moodboard):
        """Test successful moodboard statistics update."""
        # Setup
        mock_moodboard.items = [Mock() for _ in range(5)]
        mock_moodboard.likes = [Mock() for _ in range(10)]
        mock_moodboard.comments = [Mock() for _ in range(3)]
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_moodboard
        mock_db.commit = Mock()
        
        # Execute
        creative_service._update_moodboard_stats(1)
        
        # Assert
        assert mock_moodboard.total_items == 5
        assert mock_moodboard.total_likes == 10
        assert mock_moodboard.total_comments == 3
        mock_db.commit.assert_called_once()

    # Integration-style tests
    def test_moodboard_workflow_integration(self, creative_service, mock_db, mock_event):
        """Test complete moodboard workflow integration."""
        # Setup mocks for the entire workflow
        mock_moodboard = Mock(spec=Moodboard)
        mock_moodboard.id = 1
        mock_moodboard.creator_id = 1
        
        # Mock database interactions
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_event,  # For create_moodboard
            mock_moodboard,  # For add_moodboard_item
            mock_moodboard,  # For like_moodboard
            None,  # No existing like
            mock_moodboard,  # For add_moodboard_comment
        ]
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Execute workflow
        # 1. Create moodboard
        moodboard_data = {"title": "Test Moodboard", "type": "vision_board"}
        moodboard = creative_service.create_moodboard(1, 1, moodboard_data)
        
        # 2. Add item
        item_data = {"title": "Test Item", "image_url": "https://example.com/image.jpg"}
        item = creative_service.add_moodboard_item(1, 1, item_data)
        
        # 3. Like moodboard
        like = creative_service.like_moodboard(1, 1)
        
        # 4. Add comment
        comment_data = {"content": "Great moodboard!"}
        comment = creative_service.add_moodboard_comment(1, 1, comment_data)
        
        # Assert all operations succeeded
        assert mock_db.add.call_count == 4  # moodboard, item, like, comment
        assert mock_db.commit.call_count == 4
        assert moodboard is not None
        assert item is not None
        assert like is not None
        assert comment is not None