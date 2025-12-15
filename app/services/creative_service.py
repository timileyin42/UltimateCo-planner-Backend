from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
import json
import httpx
import html
from app.core.config import settings
from app.repositories.creative_repo import CreativeRepository
from app.repositories.event_repo import EventRepository
from app.services.game_templates import get_template, list_templates, get_all_templates
from app.models.creative_models import (
    MoodboardType,
    Moodboard,
    MoodboardItem,
    PlaylistProvider,
    Playlist,
    PlaylistTrack,
    GameType,
    GameDifficulty,
    Game,
    GameSession
)
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
        payload = moodboard_data if isinstance(moodboard_data, dict) else moodboard_data.model_dump()

        raw_type = payload.get('moodboard_type', payload.get('type', MoodboardType.GENERAL))
        moodboard_type = raw_type if isinstance(raw_type, MoodboardType) else MoodboardType(raw_type)

        tags = payload.get('tags')
        color_palette = payload.get('color_palette')

        processed_data = {
            'title': payload['title'],
            'description': payload.get('description'),
            'moodboard_type': moodboard_type,
            'is_public': payload.get('is_public', True),
            'allow_contributions': payload.get('allow_contributions', True),
            'tags': json.dumps(tags) if tags else None,
            'color_palette': json.dumps(color_palette) if color_palette else None,
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
    
    def update_moodboard(
        self,
        moodboard_id: int,
        user_id: int,
        update_data: Dict[str, Any]
    ):
        """Update an existing moodboard."""
        moodboard = self.creative_repo.get_moodboard_by_id(moodboard_id)

        if not moodboard:
            raise NotFoundError("Moodboard not found")

        if not self._can_edit_moodboard(moodboard, user_id):
            raise AuthorizationError("You don't have permission to edit this moodboard")

        payload = (
            update_data.model_dump(exclude_unset=True)
            if hasattr(update_data, "model_dump")
            else dict(update_data or {})
        )

        if not payload:
            raise ValidationError("No fields provided for update")

        if 'type' in payload and 'moodboard_type' not in payload:
            payload['moodboard_type'] = payload.pop('type')

        if 'moodboard_type' in payload and payload['moodboard_type'] is not None:
            raw_type = payload['moodboard_type']
            payload['moodboard_type'] = (
                raw_type if isinstance(raw_type, MoodboardType) else MoodboardType(raw_type)
            )
        elif 'moodboard_type' in payload and payload['moodboard_type'] is None:
            payload.pop('moodboard_type')

        if 'tags' in payload:
            tags = payload['tags']
            payload['tags'] = json.dumps(tags) if tags else None

        if 'color_palette' in payload:
            palette = payload['color_palette']
            payload['color_palette'] = json.dumps(palette) if palette else None

        updated = self.creative_repo.update_moodboard(moodboard_id, payload)

        if not updated:
            raise NotFoundError("Moodboard not found")

        return self.creative_repo.get_moodboard_by_id(moodboard_id, include_relations=True)

    def delete_moodboard(self, moodboard_id: int, user_id: int) -> bool:
        """Delete a moodboard."""
        moodboard = self.creative_repo.get_moodboard_by_id(moodboard_id)

        if not moodboard:
            raise NotFoundError("Moodboard not found")

        if not self._can_edit_moodboard(moodboard, user_id):
            raise AuthorizationError("You don't have permission to delete this moodboard")

        return self.creative_repo.delete_moodboard(moodboard_id)

    def get_event_moodboards(
        self, 
        event_id: int, 
        user_id: int, 
        search_params: Dict[str, Any]
    ) -> Tuple[List, int]:
        """Get moodboards for an event."""
        # Verify event access
        self._get_event_with_access(event_id, user_id)
        
        params_dict = (
            search_params.model_dump(exclude_none=True)
            if hasattr(search_params, "model_dump")
            else dict(search_params or {})
        )

        page = params_dict.get('page', 1)
        per_page = params_dict.get('per_page', 20)
        pagination = PaginationParams(page=page, per_page=per_page)
        
        # Extract filters
        filters = {
            'moodboard_type': params_dict.get('moodboard_type') or params_dict.get('type'),
            'is_public': params_dict.get('is_public'),
            'creator_id': params_dict.get('creator_id')
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
        
        payload = (
            item_data.model_dump(exclude_unset=True)
            if hasattr(item_data, "model_dump")
            else dict(item_data or {})
        )

        if not payload.get("title") and not payload.get("image_url"):
            raise ValidationError("Moodboard item requires a title or image")

        tags = payload.get('tags')
        vendor = payload.get('vendor_info')

        processed_data = {
            'moodboard_id': moodboard_id,
            'title': payload.get('title'),
            'image_url': payload.get('image_url'),
            'description': payload.get('description'),
            'source_url': payload.get('source_url'),
            'content_type': payload.get('content_type', 'image'),
            'position_x': payload.get('position_x'),
            'position_y': payload.get('position_y'),
            'width': payload.get('width'),
            'height': payload.get('height'),
            'tags': json.dumps(tags) if tags else None,
            'notes': payload.get('notes'),
            'price_estimate': payload.get('price_estimate'),
            'vendor_info': json.dumps(vendor) if vendor else None,
            'added_by_id': user_id
        }

        return self.creative_repo.create_moodboard_item(processed_data)

    def update_moodboard_item(
        self,
        item_id: int,
        user_id: int,
        update_data: Dict[str, Any]
    ):
        """Update a moodboard item."""
        item = self.creative_repo.get_moodboard_item_by_id(item_id, include_relations=True)

        if not item:
            raise NotFoundError("Moodboard item not found")

        if not self._can_edit_moodboard(item.moodboard, user_id):
            raise AuthorizationError("You don't have permission to edit this moodboard item")

        payload = (
            update_data.model_dump(exclude_unset=True)
            if hasattr(update_data, "model_dump")
            else dict(update_data or {})
        )

        if not payload:
            raise ValidationError("No fields provided for update")

        if 'tags' in payload:
            tags = payload['tags']
            payload['tags'] = json.dumps(tags) if tags else None

        if 'vendor_info' in payload:
            vendor = payload['vendor_info']
            payload['vendor_info'] = json.dumps(vendor) if vendor else None

        updated = self.creative_repo.update_moodboard_item(item_id, payload)

        if not updated:
            raise NotFoundError("Moodboard item not found")

        return self.creative_repo.get_moodboard_item_by_id(item_id, include_relations=True)

    def delete_moodboard_item(self, item_id: int, user_id: int) -> bool:
        """Delete a moodboard item."""
        item = self.creative_repo.get_moodboard_item_by_id(item_id, include_relations=True)

        if not item:
            raise NotFoundError("Moodboard item not found")

        if not self._can_edit_moodboard(item.moodboard, user_id):
            raise AuthorizationError("You don't have permission to delete this moodboard item")

        return self.creative_repo.delete_moodboard_item(item_id)
    
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
        
        if not self._can_access_moodboard(moodboard, user_id):
            raise AuthorizationError("You don't have access to this moodboard")

        payload = (
            comment_data.model_dump(exclude_unset=True)
            if hasattr(comment_data, "model_dump")
            else dict(comment_data or {})
        )

        content = payload.get('content')
        if not content:
            raise ValidationError("Comment content is required")

        # Prepare comment data
        processed_data = {
            'moodboard_id': moodboard_id,
            'author_id': user_id,
            'content': content
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
        
        payload = (
            playlist_data.model_dump(exclude_unset=True)
            if hasattr(playlist_data, "model_dump")
            else dict(playlist_data or {})
        )

        provider_raw = payload.get('provider', PlaylistProvider.CUSTOM)
        provider = provider_raw if isinstance(provider_raw, PlaylistProvider) else PlaylistProvider(provider_raw)

        genre_tags = payload.get('genre_tags')
        mood_tags = payload.get('mood_tags')

        processed_data = {
            'title': payload['title'],
            'description': payload.get('description'),
            'provider': provider,
            'external_id': payload.get('external_id'),
            'external_url': payload.get('external_url'),
            'is_collaborative': payload.get('is_collaborative', True),
            'is_public': payload.get('is_public', True),
            'allow_duplicates': payload.get('allow_duplicates', False),
            'genre_tags': json.dumps(genre_tags) if genre_tags else None,
            'mood_tags': json.dumps(mood_tags) if mood_tags else None,
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
        
        payload = (
            track_data.model_dump(exclude_unset=True)
            if hasattr(track_data, "model_dump")
            else dict(track_data or {})
        )

        if not payload.get('title') or not payload.get('artist'):
            raise ValidationError("Playlist tracks require a title and artist")

        # Determine track duration in seconds
        duration_seconds = payload.get('duration_seconds')
        if not duration_seconds and payload.get('duration_ms'):
            duration_seconds = int(payload['duration_ms']) // 1000

        existing_tracks = self.creative_repo.get_playlist_tracks(playlist_id)
        position = payload.get('position')
        if position is None:
            position = len(existing_tracks) + 1

        processed_data = {
            'playlist_id': playlist_id,
            'title': payload['title'],
            'artist': payload['artist'],
            'album': payload.get('album'),
            'duration_seconds': duration_seconds,
            'spotify_id': payload.get('spotify_id'),
            'genre': payload.get('genre'),
            'year': payload.get('year'),
            'explicit': payload.get('explicit', False),
            'position': position,
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
        event_id: Optional[int], 
        user_id: int, 
        game_data: Dict[str, Any]
    ):
        """Create a new game for an event (or global if event_id is None)."""
        # Verify event access only if event_id is provided
        if event_id is not None:
            event = self._get_event_with_access(event_id, user_id)
        
        payload = (
            game_data.model_dump(exclude_unset=True)
            if hasattr(game_data, "model_dump")
            else dict(game_data or {})
        )

        game_type_raw = payload.get('game_type', GameType.ICEBREAKER)
        game_type = game_type_raw if isinstance(game_type_raw, GameType) else GameType(game_type_raw)

        difficulty_raw = payload.get('difficulty', GameDifficulty.EASY)
        difficulty = difficulty_raw if isinstance(difficulty_raw, GameDifficulty) else GameDifficulty(difficulty_raw)

        instructions = payload.get('instructions')
        if not instructions:
            raise ValidationError("Game instructions are required")

        materials = payload.get('materials_needed')
        tags = payload.get('tags')
        categories = payload.get('categories')
        game_specific_data = payload.get('game_data')

        processed_data = {
            'title': payload['title'],
            'description': payload.get('description', ''),
            'game_type': game_type,
            'difficulty': difficulty,
            'min_players': payload.get('min_players', 2),
            'max_players': payload.get('max_players'),
            'estimated_duration_minutes': (
                payload.get('estimated_duration_minutes')
                or payload.get('duration_minutes')
            ),
            'instructions': instructions,
            'materials_needed': json.dumps(materials) if materials else None,
            'game_data': json.dumps(game_specific_data) if game_specific_data else None,
            'is_public': payload.get('is_public', True),
            'age_appropriate': payload.get('age_appropriate', True),
            'tags': json.dumps(tags) if tags else None,
            'categories': json.dumps(categories) if categories else None,
            'event_id': event_id,
            'creator_id': user_id
        }
        
        game = self.creative_repo.create_game(processed_data)

        return self._hydrate_game(self.creative_repo.get_game_by_id(game.id, include_relations=True))
    
    def start_game_session(
        self,
        event_id: int,
        user_id: int,
        session_payload: Dict[str, Any]
    ):
        """Start a new game session for the provided event."""
        # Ensure the requester can operate on the event
        self._get_event_with_access(event_id, user_id)

        payload = (
            session_payload.model_dump(exclude_unset=True)
            if hasattr(session_payload, "model_dump")
            else dict(session_payload or {})
        )

        game_id = payload.get('game_id')
        if not game_id:
            raise ValidationError("Game ID is required to start a session")

        game = self.creative_repo.get_game_by_id(game_id)
        if not game:
            raise NotFoundError("Game not found")

        # Prevent linking the game to the wrong event unless the game is global
        if game.event_id and game.event_id != event_id:
            raise ValidationError("Game is not associated with this event")

        # Determine participant cap prioritizing explicit request, else fall back to game settings
        requested_max = payload.get('max_participants')
        max_participants = requested_max if requested_max is not None else game.max_players

        if max_participants is not None and game.min_players and max_participants < game.min_players:
            raise ValidationError("Max participants cannot be less than the game's minimum players")

        total_rounds = payload.get('total_rounds')

        session_data = {
            'game_id': game_id,
            'event_id': event_id if game.event_id is not None else payload.get('event_id', event_id),
            'host_id': user_id,
            'status': 'waiting',
            'max_participants': max_participants,
            'total_rounds': total_rounds
        }

        return self.creative_repo.create_game_session(session_data)

    def _hydrate_game(self, game: Optional[Game]):
        """Convert JSON/text fields on the game model into Python structures for responses."""
        if not game:
            return game

        json_fields = [
            ("materials_needed", list),
            ("tags", list),
            ("categories", list),
            ("game_data", dict)
        ]

        for field_name, expected_type in json_fields:
            value = getattr(game, field_name, None)
            if value is None or isinstance(value, expected_type):
                continue

            if isinstance(value, (dict, list)):
                continue

            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                parsed = None

            setattr(game, field_name, parsed)

        return game
    
    def join_game_session(
        self, 
        session_id: int, 
        user_id: int
    ):
        """Join a game session."""
        session = self.creative_repo.get_game_session_by_id(session_id)
        
        if not session:
            raise NotFoundError("Game session not found")
        
        self._get_event_with_access(session.event_id, user_id)

        if session.status != 'waiting':
            raise ValidationError("Cannot join a game that has already started")
        
        # Check if already participating
        existing_participation = self.creative_repo.get_game_participation(session_id, user_id)
        
        if existing_participation:
            raise ValidationError("You are already participating in this game")
        
        # Check participant limit
        max_participants = session.max_participants or session.game.max_players
        if max_participants is not None and len(session.participants) >= max_participants:
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
    
    async def generate_game_questions(
        self,
        topic: str,
        difficulty: str,
        game_type: str,
        count: int = 10
    ) -> List[Dict[str, Any]]:
        """Generate trivia questions using Open Trivia Database API."""
        try:
            # Map difficulty to OpenTDB format
            difficulty_map = {
                'easy': 'easy',
                'medium': 'medium',
                'hard': 'hard'
            }
            opentdb_difficulty = difficulty_map.get(difficulty.lower(), 'medium')
            
            # Build API URL
            url = f"https://opentdb.com/api.php?amount={count}&difficulty={opentdb_difficulty}&type=multiple"
            
            # Make API request
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
                response.raise_for_status()
                data = response.json()
            
            # Check response code
            if data.get('response_code') != 0:
                raise ValueError(f"OpenTDB API error: {data.get('response_code')}")
            
            # Transform OpenTDB format to our format
            questions = []
            for idx, item in enumerate(data.get('results', []), start=1):
                # Decode HTML entities
                question_text = html.unescape(item['question'])
                correct = html.unescape(item['correct_answer'])
                incorrect = [html.unescape(ans) for ans in item['incorrect_answers']]
                
                # Combine and shuffle options
                import random
                options = incorrect + [correct]
                random.shuffle(options)
                correct_index = options.index(correct)
                
                questions.append({
                    "id": idx,
                    "text": question_text,
                    "options": options,
                    "correct_answer": correct_index,
                    "points": 100,
                    "explanation": f"The correct answer is: {correct}",
                    "category": html.unescape(item.get('category', 'General Knowledge'))
                })
            
            return questions
            
        except Exception as e:
            # Fallback to sample questions if API fails
            return self._get_fallback_questions(game_type, count)
    
    def _get_fallback_questions(self, game_type: str, count: int) -> List[Dict[str, Any]]:
        """Return sample questions if AI generation fails."""
        fallback = [
            {
                "id": 1,
                "text": "What is the capital of France?",
                "options": ["London", "Paris", "Berlin", "Madrid"],
                "correct_answer": 1,
                "points": 100,
                "explanation": "Paris is the capital and largest city of France."
            },
            {
                "id": 2,
                "text": "Which planet is known as the Red Planet?",
                "options": ["Venus", "Mars", "Jupiter", "Saturn"],
                "correct_answer": 1,
                "points": 100,
                "explanation": "Mars appears red due to iron oxide on its surface."
            },
            {
                "id": 3,
                "text": "What year did World War II end?",
                "options": ["1943", "1944", "1945", "1946"],
                "correct_answer": 2,
                "points": 100,
                "explanation": "World War II ended in 1945 with Japan's surrender."
            }
        ]
        return fallback[:count]
    
    def get_game_questions(
        self,
        game_id: int,
        user_id: int,
        round_number: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get questions for a game, optionally filtered by round."""
        game = self.creative_repo.get_game_by_id(game_id)
        if not game:
            raise NotFoundError("Game not found")
        
        # Parse game_data
        game_data = json.loads(game.game_data) if isinstance(game.game_data, str) else (game.game_data or {})
        questions = game_data.get('questions', [])
        
        if not questions:
            raise ValidationError("This game has no questions configured")
        
        # Filter by round if specified
        if round_number is not None:
            total_rounds = game_data.get('rounds', 1)
            if total_rounds > 0:
                questions_per_round = len(questions) // total_rounds
                start_idx = (round_number - 1) * questions_per_round
                end_idx = start_idx + questions_per_round
                questions = questions[start_idx:end_idx]
        
        return questions
    
    def submit_answer(
        self,
        session_id: int,
        user_id: int,
        question_id: int,
        answer: int
    ) -> Dict[str, Any]:
        """Submit an answer and calculate score."""
        session = self.creative_repo.get_game_session_by_id(session_id)
        
        if not session:
            raise NotFoundError("Game session not found")
        
        if session.status != 'active':
            raise ValidationError("Game session is not active")
        
        # Check user is participating
        participant = self.creative_repo.get_game_participation(session_id, user_id)
        if not participant:
            raise ValidationError("You are not participating in this game")
        
        # Get game questions
        game_data = json.loads(session.game.game_data) if isinstance(session.game.game_data, str) else (session.game.game_data or {})
        questions = game_data.get('questions', [])
        
        # Find the question
        question = next((q for q in questions if q.get('id') == question_id), None)
        if not question:
            raise NotFoundError("Question not found")
        
        # Check answer
        is_correct = question.get('correct_answer') == answer
        points = question.get('points', 100) if is_correct else 0
        
        # Update participant score
        participant.score += points
        self.db.commit()
        self.db.refresh(participant)
        
        return {
            'is_correct': is_correct,
            'points': points,
            'new_score': participant.score,
            'correct_answer': question.get('correct_answer'),
            'explanation': question.get('explanation', '')
        }
    
    def get_creative_statistics(self, event_id: int, user_id: int) -> Dict[str, Any]:
        """Aggregate creative feature statistics for an event."""
        self._get_event_with_access(event_id, user_id)

        moodboard_count = self.db.query(func.count(Moodboard.id)).filter(Moodboard.event_id == event_id).scalar() or 0
        playlist_count = self.db.query(func.count(Playlist.id)).filter(Playlist.event_id == event_id).scalar() or 0
        game_count = self.db.query(func.count(Game.id)).filter(Game.event_id == event_id).scalar() or 0

        total_tracks = (
            self.db.query(func.count(PlaylistTrack.id))
            .join(Playlist, PlaylistTrack.playlist_id == Playlist.id)
            .filter(Playlist.event_id == event_id)
            .scalar()
            or 0
        )

        active_sessions = (
            self.db.query(func.count(GameSession.id))
            .filter(
                GameSession.event_id == event_id,
                GameSession.status.in_(["waiting", "active"])
            )
            .scalar()
            or 0
        )

        moodboard_type_row = (
            self.db.query(Moodboard.moodboard_type, func.count(Moodboard.id))
            .filter(Moodboard.event_id == event_id)
            .group_by(Moodboard.moodboard_type)
            .order_by(func.count(Moodboard.id).desc())
            .first()
        )
        most_popular_moodboard_type = (
            moodboard_type_row[0].value.lower()
            if moodboard_type_row and isinstance(moodboard_type_row[0], MoodboardType)
            else (moodboard_type_row[0] if moodboard_type_row else None)
        )

        game_type_row = (
            self.db.query(Game.game_type, func.count(Game.id))
            .filter(Game.event_id == event_id)
            .group_by(Game.game_type)
            .order_by(func.count(Game.id).desc())
            .first()
        )
        most_popular_game_type = (
            game_type_row[0].value.lower()
            if game_type_row and isinstance(game_type_row[0], GameType)
            else (game_type_row[0] if game_type_row else None)
        )

        average_playlist_length = (
            (total_tracks / playlist_count) if playlist_count > 0 else None
        )

        return {
            'total_moodboards': int(moodboard_count),
            'total_playlists': int(playlist_count),
            'total_games': int(game_count),
            'active_game_sessions': int(active_sessions),
            'most_popular_moodboard_type': most_popular_moodboard_type,
            'most_popular_game_type': most_popular_game_type,
            'average_playlist_length': average_playlist_length,
            'total_playlist_tracks': int(total_tracks)
        }

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
        if moodboard.creator_id == user_id:
            return True

        if not moodboard.allow_contributions:
            return False

        try:
            self._get_event_with_access(moodboard.event_id, user_id)
            return True
        except (NotFoundError, AuthorizationError):
            return False
    
    def _can_edit_playlist(self, playlist, user_id: int) -> bool:
        """Check if user can edit a playlist."""
        # Creator can always edit
        if playlist.creator_id == user_id:
            return True
        
        # For collaborative playlists, event participants can edit
        if getattr(playlist, 'is_collaborative', False):
            try:
                self._get_event_with_access(playlist.event_id, user_id)
                return True
            except (NotFoundError, AuthorizationError):
                return False
        
        return False
    
    # Game Template operations
    def get_all_game_templates(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all available game templates grouped by type."""
        all_templates = get_all_templates()
        
        result = {}
        total = 0
        
        for game_type, templates_dict in all_templates.items():
            result[game_type] = []
            for template_name, template_data in templates_dict.items():
                result[game_type].append({
                    "game_type": game_type,
                    "template_name": template_name,
                    "title": template_data.get("title"),
                    "description": template_data.get("description"),
                    "instructions": template_data.get("instructions"),
                    "min_players": template_data.get("min_players"),
                    "max_players": template_data.get("max_players"),
                    "estimated_duration_minutes": template_data.get("estimated_duration_minutes"),
                    "materials_needed": template_data.get("materials_needed", []),
                    "game_data": template_data.get("game_data")
                })
                total += 1
        
        return {"templates": result, "total": total}
    
    def get_templates_by_type(self, game_type: str) -> List[str]:
        """Get list of template names for a specific game type."""
        return list_templates(game_type)
    
    def get_template_details(self, game_type: str, template_name: str) -> Dict[str, Any]:
        """Get details for a specific template."""
        template = get_template(game_type, template_name)
        
        if not template:
            raise NotFoundError(f"Template '{template_name}' not found for game type '{game_type}'")
        
        return {
            "game_type": game_type,
            "template_name": template_name,
            "title": template.get("title"),
            "description": template.get("description"),
            "instructions": template.get("instructions"),
            "min_players": template.get("min_players"),
            "max_players": template.get("max_players"),
            "estimated_duration_minutes": template.get("estimated_duration_minutes"),
            "materials_needed": template.get("materials_needed", []),
            "game_data": template.get("game_data")
        }
    
    def create_game_from_template(
        self, 
        user_id: int,
        game_type: str,
        template_name: str,
        event_id: Optional[int] = None,
        custom_title: Optional[str] = None,
        custom_description: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        is_public: bool = False,
        customizations: Optional[Dict[str, Any]] = None
    ) -> Game:
        """Create a new game from a template."""
        # Get the template
        template = get_template(game_type, template_name)
        
        if not template:
            raise NotFoundError(f"Template '{template_name}' not found for game type '{game_type}'")
        
        # Verify event access if event_id provided
        if event_id:
            self._get_event_with_access(event_id, user_id)
        
        # Prepare game data
        game_data = template.get("game_data", {}).copy()
        
        # Apply customizations if provided
        if customizations:
            game_data.update(customizations)
        
        # Add template identifier to game_data
        game_data["template"] = template_name
        
        # Map game_type string to GameType enum
        # Note: team_building maps to PARTY_GAME since there's no separate enum value
        game_type_enum_map = {
            "icebreaker": GameType.ICEBREAKER,
            "party_game": GameType.PARTY_GAME,
            "team_building": GameType.PARTY_GAME,  # Team building uses PARTY_GAME type
            "trivia": GameType.TRIVIA,
            "custom": GameType.CUSTOM
        }
        
        game_type_enum = game_type_enum_map.get(game_type.lower(), GameType.CUSTOM)
        
        # Create game
        game = Game(
            title=custom_title or template.get("title"),
            description=custom_description or template.get("description"),
            instructions=custom_instructions or template.get("instructions"),
            game_type=game_type_enum,
            difficulty=GameDifficulty.MEDIUM,  # Default, user can change later
            min_players=template.get("min_players"),
            max_players=template.get("max_players"),
            estimated_duration_minutes=template.get("estimated_duration_minutes"),
            materials_needed=json.dumps(template.get("materials_needed", [])),
            game_data=json.dumps(game_data),
            is_public=is_public,
            event_id=event_id,
            creator_id=user_id
        )
        
        self.db.add(game)
        self.db.commit()
        self.db.refresh(game)
        
        return self._hydrate_game(game)