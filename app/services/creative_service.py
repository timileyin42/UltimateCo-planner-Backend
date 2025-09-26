from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime
from app.repositories.creative_repo import CreativeRepository
from app.repositories.event_repo import EventRepository
from app.models.creative_models import MoodboardType, PlaylistType, GameType
from app.models.event_models import EventInvitation
from app.core.errors import NotFoundError, ValidationError, AuthorizationError
from app.schemas.pagination import PaginationParams

class CreativeService:
    """Service for managing creative features like moodboards, playlists, and games."""
    
    def __init__(self, db: Session):
        self.db = db
        self.creative_repo = CreativeRepository(db)
        self.event_repo = EventRepository(db)
    
    # Moodboard operations
    def create_moodboard(
        self, 
        event_id: int, 
        user_id: int, 
        moodboard_data: Dict[str, Any]
    ):
        """Create a new moodboard for an event."""
        # Verify event access
        event = self._get_event_with_access(event_id, user_id)
        
        # Prepare moodboard data
        processed_data = {
            'title': moodboard_data['title'],
            'description': moodboard_data.get('description'),
            'type': MoodboardType(moodboard_data.get('type', 'vision_board')),
            'is_public': moodboard_data.get('is_public', False),
            'event_id': event_id,
            'creator_id': user_id
        }
        
        return self.creative_repo.create_moodboard(processed_data)
    
    def get_moodboard(self, moodboard_id: int, user_id: int):
        """Get a moodboard by ID."""
        moodboard = self.creative_repo.get_moodboard_by_id(moodboard_id, include_relations=True)
        
        if not moodboard:
            raise NotFoundError("Moodboard not found")
        
        # Check access permissions
        if not moodboard.is_public and not self._can_access_moodboard(moodboard, user_id):
            raise AuthorizationError("You don't have access to this moodboard")
        
        return moodboard
    
    def get_event_moodboards(
        self, 
        event_id: int, 
        user_id: int, 
        search_params: Dict[str, Any]
    ) -> Tuple[List, int]:
        """Get moodboards for an event."""
        # Verify event access
        self._get_event_with_access(event_id, user_id)
        
        # Create pagination params
        page = search_params.get('page', 1)
        per_page = search_params.get('per_page', 20)
        pagination = PaginationParams(page=page, per_page=per_page)
        
        # Extract filters
        filters = {
            'type': search_params.get('type'),
            'is_public': search_params.get('is_public'),
            'creator_id': search_params.get('creator_id')
        }
        
        return self.creative_repo.get_event_moodboards(event_id, pagination, filters)
    
    def add_moodboard_item(
        self, 
        moodboard_id: int, 
        user_id: int, 
        item_data: Dict[str, Any]
    ):
        """Add an item to a moodboard."""
        moodboard = self.creative_repo.get_moodboard_by_id(moodboard_id)
        
        if not moodboard:
            raise NotFoundError("Moodboard not found")
        
        # Check edit permissions
        if not self._can_edit_moodboard(moodboard, user_id):
            raise AuthorizationError("You don't have permission to edit this moodboard")
        
        # Prepare item data
        processed_data = {
            'moodboard_id': moodboard_id,
            'title': item_data['title'],
            'image_url': item_data['image_url'],
            'description': item_data.get('description'),
            'source_url': item_data.get('source_url'),
            'tags': item_data.get('tags', []),
            'order_index': item_data.get('order_index', 0),
            'added_by_id': user_id
        }
        
        return self.creative_repo.create_moodboard_item(processed_data)
    
    def like_moodboard(self, moodboard_id: int, user_id: int):
        """Like or unlike a moodboard."""
        moodboard = self.creative_repo.get_moodboard_by_id(moodboard_id)
        
        if not moodboard:
            raise NotFoundError("Moodboard not found")
        
        # Check if already liked
        existing_like = self.creative_repo.get_moodboard_like(moodboard_id, user_id)
        
        if existing_like:
            # Unlike
            self.creative_repo.delete_moodboard_like(moodboard_id, user_id)
            return {'action': 'unliked'}
        else:
            # Like
            like_data = {
                'moodboard_id': moodboard_id,
                'user_id': user_id
            }
            self.creative_repo.create_moodboard_like(like_data)
            return {'action': 'liked'}
    
    def add_moodboard_comment(
        self, 
        moodboard_id: int, 
        user_id: int, 
        comment_data: Dict[str, Any]
    ):
        """Add a comment to a moodboard."""
        moodboard = self.creative_repo.get_moodboard_by_id(moodboard_id)
        
        if not moodboard:
            raise NotFoundError("Moodboard not found")
        
        # Prepare comment data
        processed_data = {
            'moodboard_id': moodboard_id,
            'user_id': user_id,
            'content': comment_data['content']
        }
        
        return self.creative_repo.create_moodboard_comment(processed_data)
    
    # Playlist operations
    def create_playlist(
        self, 
        event_id: int, 
        user_id: int, 
        playlist_data: Dict[str, Any]
    ):
        """Create a new playlist for an event."""
        # Verify event access
        event = self._get_event_with_access(event_id, user_id)
        
        # Prepare playlist data
        processed_data = {
            'title': playlist_data['title'],
            'description': playlist_data.get('description'),
            'type': PlaylistType(playlist_data.get('type', 'collaborative')),
            'is_public': playlist_data.get('is_public', False),
            'event_id': event_id,
            'creator_id': user_id
        }
        
        return self.creative_repo.create_playlist(processed_data)
    
    def add_playlist_track(
        self, 
        playlist_id: int, 
        user_id: int, 
        track_data: Dict[str, Any]
    ):
        """Add a track to a playlist."""
        playlist = self.creative_repo.get_playlist_by_id(playlist_id)
        
        if not playlist:
            raise NotFoundError("Playlist not found")
        
        # Check permissions
        if not self._can_edit_playlist(playlist, user_id):
            raise AuthorizationError("You don't have permission to add tracks to this playlist")
        
        # Prepare track data
        processed_data = {
            'playlist_id': playlist_id,
            'title': track_data['title'],
            'artist': track_data['artist'],
            'album': track_data.get('album'),
            'duration_ms': track_data.get('duration_ms'),
            'spotify_id': track_data.get('spotify_id'),
            'youtube_id': track_data.get('youtube_id'),
            'preview_url': track_data.get('preview_url'),
            'added_by_id': user_id
        }
        
        return self.creative_repo.create_playlist_track(processed_data)
    
    def vote_playlist_track(
        self, 
        track_id: int, 
        user_id: int, 
        is_upvote: bool
    ):
        """Vote on a playlist track."""
        track = self.creative_repo.get_track_by_id(track_id)
        
        if not track:
            raise NotFoundError("Track not found")
        
        # Check if already voted
        existing_vote = self.creative_repo.get_playlist_vote(track_id, user_id)
        
        if existing_vote:
            # Update existing vote
            return self.creative_repo.update_playlist_vote(existing_vote.id, is_upvote)
        else:
            # Create new vote
            vote_data = {
                'track_id': track_id,
                'user_id': user_id,
                'is_upvote': is_upvote
            }
            return self.creative_repo.create_playlist_vote(vote_data)
    
    # Game operations
    def create_game(
        self, 
        event_id: int, 
        user_id: int, 
        game_data: Dict[str, Any]
    ):
        """Create a new game for an event."""
        # Verify event access
        event = self._get_event_with_access(event_id, user_id)
        
        # Prepare game data
        processed_data = {
            'title': game_data['title'],
            'description': game_data.get('description'),
            'type': GameType(game_data.get('type', 'icebreaker')),
            'rules': game_data.get('rules'),
            'max_participants': game_data.get('max_participants'),
            'duration_minutes': game_data.get('duration_minutes'),
            'materials_needed': game_data.get('materials_needed', []),
            'difficulty_level': game_data.get('difficulty_level', 'easy'),
            'event_id': event_id,
            'creator_id': user_id
        }
        
        return self.creative_repo.create_game(processed_data)
    
    def start_game_session(
        self, 
        game_id: int, 
        user_id: int
    ):
        """Start a new game session."""
        game = self.creative_repo.get_game_by_id(game_id)
        
        if not game:
            raise NotFoundError("Game not found")
        
        # Check if user has access to the event
        self._get_event_with_access(game.event_id, user_id)
        
        # Prepare session data
        session_data = {
            'game_id': game_id,
            'host_id': user_id,
            'status': 'waiting',
            'max_participants': game.max_participants
        }
        
        return self.creative_repo.create_game_session(session_data)
    
    def join_game_session(
        self, 
        session_id: int, 
        user_id: int
    ):
        """Join a game session."""
        session = self.creative_repo.get_game_session_by_id(session_id)
        
        if not session:
            raise NotFoundError("Game session not found")
        
        if session.status != 'waiting':
            raise ValidationError("Cannot join a game that has already started")
        
        # Check if already participating
        existing_participation = self.creative_repo.get_game_participation(session_id, user_id)
        
        if existing_participation:
            raise ValidationError("You are already participating in this game")
        
        # Check participant limit
        if len(session.participants) >= session.game.max_participants:
            raise ValidationError("Game session is full")
        
        # Create participation
        participation_data = {
            'session_id': session_id,
            'user_id': user_id,
            'joined_at': datetime.utcnow()
        }
        
        return self.creative_repo.create_game_participation(participation_data)
    
    def rate_game(
        self, 
        game_id: int, 
        user_id: int, 
        rating_data: Dict[str, Any]
    ):
        """Rate a game."""
        game = self.creative_repo.get_game_by_id(game_id)
        
        if not game:
            raise NotFoundError("Game not found")
        
        # Check if already rated
        existing_rating = self.creative_repo.get_user_game_rating(game_id, user_id)
        
        if existing_rating:
            raise ValidationError("You have already rated this game")
        
        # Prepare rating data
        processed_data = {
            'game_id': game_id,
            'user_id': user_id,
            'rating': rating_data['rating'],
            'comment': rating_data.get('comment')
        }
        
        return self.creative_repo.create_game_rating(processed_data)
    
    # Search and statistics
    def search_moodboards(self, search_params: Dict[str, Any]) -> Tuple[List, int]:
        """Search public moodboards."""
        # Create pagination params
        page = search_params.get('page', 1)
        per_page = search_params.get('per_page', 20)
        pagination = PaginationParams(page=page, per_page=per_page)
        
        return self.creative_repo.search_moodboards(search_params, pagination)
    
    def get_moodboard_statistics(self, moodboard_id: int, user_id: int) -> Dict[str, Any]:
        """Get statistics for a moodboard."""
        moodboard = self.creative_repo.get_moodboard_by_id(moodboard_id)
        
        if not moodboard:
            raise NotFoundError("Moodboard not found")
        
        # Check access permissions
        if not self._can_access_moodboard(moodboard, user_id):
            raise AuthorizationError("You don't have access to this moodboard")
        
        return self.creative_repo.get_moodboard_statistics(moodboard_id)
    
    # Helper methods
    def _get_event_with_access(self, event_id: int, user_id: int):
        """Get event and verify user has access."""
        event = self.event_repo.get_by_id(event_id, include_relations=True)
        
        if not event:
            raise NotFoundError("Event not found")
        
        # Check access (creator, collaborator, or invited)
        if event.creator_id != user_id:
            # Check if user is collaborator or invited
            invitation = self.db.query(EventInvitation).filter(
                EventInvitation.event_id == event_id,
                EventInvitation.user_id == user_id
            ).first()
            
            if not invitation:
                raise AuthorizationError("You don't have access to this event")
        
        return event
    
    def _can_access_moodboard(self, moodboard, user_id: int) -> bool:
        """Check if user can access a moodboard."""
        if moodboard.is_public:
            return True
        
        # Check if user is creator
        if moodboard.creator_id == user_id:
            return True
        
        # Check if user has access to the event
        try:
            self._get_event_with_access(moodboard.event_id, user_id)
            return True
        except (NotFoundError, AuthorizationError):
            return False
    
    def _can_edit_moodboard(self, moodboard, user_id: int) -> bool:
        """Check if user can edit a moodboard."""
        # Only creator can edit
        return moodboard.creator_id == user_id
    
    def _can_edit_playlist(self, playlist, user_id: int) -> bool:
        """Check if user can edit a playlist."""
        # Creator can always edit
        if playlist.creator_id == user_id:
            return True
        
        # For collaborative playlists, event participants can edit
        if playlist.type == PlaylistType.COLLABORATIVE:
            try:
                self._get_event_with_access(playlist.event_id, user_id)
                return True
            except (NotFoundError, AuthorizationError):
                return False
        
        return False