from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc
from datetime import datetime, timedelta
from app.models.creative_models import (
    Moodboard, MoodboardItem, MoodboardLike, MoodboardComment,
    Playlist, PlaylistTrack, PlaylistVote,
    Game, GameSession, GameParticipation, GameRating,
    MoodboardType, PlaylistType, GameType
)
from app.models.user_models import User
from app.models.event_models import Event
from app.schemas.pagination import PaginationParams, SortParams

class CreativeRepository:
    """Repository for creative features data access operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Moodboard operations
    def get_moodboard_by_id(
        self, 
        moodboard_id: int, 
        include_relations: bool = False
    ) -> Optional[Moodboard]:
        """Get moodboard by ID with optional relation loading"""
        query = self.db.query(Moodboard).filter(Moodboard.id == moodboard_id)
        
        if include_relations:
            query = query.options(
                joinedload(Moodboard.creator),
                joinedload(Moodboard.event),
                joinedload(Moodboard.items),
                joinedload(Moodboard.likes),
                joinedload(Moodboard.comments)
            )
        
        return query.first()
    
    def get_event_moodboards(
        self,
        event_id: int,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Moodboard], int]:
        """Get moodboards for an event"""
        query = self.db.query(Moodboard).options(
            joinedload(Moodboard.creator)
        ).filter(Moodboard.event_id == event_id)
        
        if filters:
            if filters.get('type'):
                query = query.filter(Moodboard.type == filters['type'])
            
            if filters.get('is_public') is not None:
                query = query.filter(Moodboard.is_public == filters['is_public'])
            
            if filters.get('creator_id'):
                query = query.filter(Moodboard.creator_id == filters['creator_id'])
        
        total = query.count()
        
        moodboards = query.order_by(
            desc(Moodboard.is_featured),
            desc(Moodboard.created_at)
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return moodboards, total
    
    def search_moodboards(
        self,
        search_params: Dict[str, Any],
        pagination: PaginationParams
    ) -> Tuple[List[Moodboard], int]:
        """Search moodboards with filters"""
        query = self.db.query(Moodboard).options(
            joinedload(Moodboard.creator),
            joinedload(Moodboard.event)
        ).filter(Moodboard.is_public == True)
        
        if search_params.get('query'):
            search_term = f"%{search_params['query']}%"
            query = query.filter(
                or_(
                    Moodboard.title.ilike(search_term),
                    Moodboard.description.ilike(search_term)
                )
            )
        
        if search_params.get('type'):
            query = query.filter(Moodboard.type == search_params['type'])
        
        if search_params.get('event_type'):
            query = query.join(Event).filter(Event.event_type == search_params['event_type'])
        
        total = query.count()
        
        moodboards = query.order_by(
            desc(Moodboard.is_featured),
            desc(Moodboard.total_likes),
            desc(Moodboard.created_at)
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return moodboards, total
    
    def create_moodboard(self, moodboard_data: Dict[str, Any]) -> Moodboard:
        """Create a new moodboard"""
        moodboard = Moodboard(**moodboard_data)
        self.db.add(moodboard)
        self.db.commit()
        self.db.refresh(moodboard)
        return moodboard
    
    def update_moodboard(self, moodboard_id: int, update_data: Dict[str, Any]) -> Optional[Moodboard]:
        """Update moodboard by ID"""
        moodboard = self.get_moodboard_by_id(moodboard_id)
        if not moodboard:
            return None
        
        for field, value in update_data.items():
            if hasattr(moodboard, field):
                setattr(moodboard, field, value)
        
        self.db.commit()
        self.db.refresh(moodboard)
        return moodboard
    
    def delete_moodboard(self, moodboard_id: int) -> bool:
        """Delete moodboard by ID"""
        moodboard = self.get_moodboard_by_id(moodboard_id)
        if not moodboard:
            return False
        
        self.db.delete(moodboard)
        self.db.commit()
        return True
    
    # Moodboard Item operations
    def create_moodboard_item(self, item_data: Dict[str, Any]) -> MoodboardItem:
        """Create a new moodboard item"""
        item = MoodboardItem(**item_data)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        
        # Update moodboard stats
        self.update_moodboard_stats(item.moodboard_id)
        
        return item
    
    def get_moodboard_items(self, moodboard_id: int) -> List[MoodboardItem]:
        """Get all items for a moodboard"""
        return self.db.query(MoodboardItem).filter(
            MoodboardItem.moodboard_id == moodboard_id
        ).order_by(MoodboardItem.order_index, MoodboardItem.created_at).all()
    
    def delete_moodboard_item(self, item_id: int) -> bool:
        """Delete moodboard item by ID"""
        item = self.db.query(MoodboardItem).filter(MoodboardItem.id == item_id).first()
        if not item:
            return False
        
        moodboard_id = item.moodboard_id
        self.db.delete(item)
        self.db.commit()
        
        # Update moodboard stats
        self.update_moodboard_stats(moodboard_id)
        
        return True
    
    # Moodboard Like operations
    def create_moodboard_like(self, like_data: Dict[str, Any]) -> MoodboardLike:
        """Create a new moodboard like"""
        like = MoodboardLike(**like_data)
        self.db.add(like)
        self.db.commit()
        self.db.refresh(like)
        
        # Update moodboard stats
        self.update_moodboard_stats(like.moodboard_id)
        
        return like
    
    def get_moodboard_like(self, moodboard_id: int, user_id: int) -> Optional[MoodboardLike]:
        """Get user's like for a moodboard"""
        return self.db.query(MoodboardLike).filter(
            MoodboardLike.moodboard_id == moodboard_id,
            MoodboardLike.user_id == user_id
        ).first()
    
    def delete_moodboard_like(self, moodboard_id: int, user_id: int) -> bool:
        """Delete moodboard like"""
        like = self.get_moodboard_like(moodboard_id, user_id)
        if not like:
            return False
        
        self.db.delete(like)
        self.db.commit()
        
        # Update moodboard stats
        self.update_moodboard_stats(moodboard_id)
        
        return True
    
    # Moodboard Comment operations
    def create_moodboard_comment(self, comment_data: Dict[str, Any]) -> MoodboardComment:
        """Create a new moodboard comment"""
        comment = MoodboardComment(**comment_data)
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        
        # Update moodboard stats
        self.update_moodboard_stats(comment.moodboard_id)
        
        return comment
    
    def get_moodboard_comments(
        self,
        moodboard_id: int,
        pagination: PaginationParams
    ) -> Tuple[List[MoodboardComment], int]:
        """Get comments for a moodboard"""
        query = self.db.query(MoodboardComment).options(
            joinedload(MoodboardComment.user)
        ).filter(MoodboardComment.moodboard_id == moodboard_id)
        
        total = query.count()
        
        comments = query.order_by(
            desc(MoodboardComment.created_at)
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return comments, total
    
    # Playlist operations
    def get_playlist_by_id(
        self, 
        playlist_id: int, 
        include_relations: bool = False
    ) -> Optional[Playlist]:
        """Get playlist by ID with optional relation loading"""
        query = self.db.query(Playlist).filter(Playlist.id == playlist_id)
        
        if include_relations:
            query = query.options(
                joinedload(Playlist.creator),
                joinedload(Playlist.event),
                joinedload(Playlist.tracks)
            )
        
        return query.first()
    
    def get_event_playlists(
        self,
        event_id: int,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Playlist], int]:
        """Get playlists for an event"""
        query = self.db.query(Playlist).options(
            joinedload(Playlist.creator)
        ).filter(Playlist.event_id == event_id)
        
        if filters:
            if filters.get('type'):
                query = query.filter(Playlist.type == filters['type'])
            
            if filters.get('is_public') is not None:
                query = query.filter(Playlist.is_public == filters['is_public'])
        
        total = query.count()
        
        playlists = query.order_by(
            desc(Playlist.is_featured),
            desc(Playlist.created_at)
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return playlists, total
    
    def create_playlist(self, playlist_data: Dict[str, Any]) -> Playlist:
        """Create a new playlist"""
        playlist = Playlist(**playlist_data)
        self.db.add(playlist)
        self.db.commit()
        self.db.refresh(playlist)
        return playlist
    
    def update_playlist(self, playlist_id: int, update_data: Dict[str, Any]) -> Optional[Playlist]:
        """Update playlist by ID"""
        playlist = self.get_playlist_by_id(playlist_id)
        if not playlist:
            return None
        
        for field, value in update_data.items():
            if hasattr(playlist, field):
                setattr(playlist, field, value)
        
        self.db.commit()
        self.db.refresh(playlist)
        return playlist
    
    # Playlist Track operations
    def create_playlist_track(self, track_data: Dict[str, Any]) -> PlaylistTrack:
        """Create a new playlist track"""
        track = PlaylistTrack(**track_data)
        self.db.add(track)
        self.db.commit()
        self.db.refresh(track)
        
        # Update playlist stats
        self.update_playlist_stats(track.playlist_id)
        
        return track
    
    def get_playlist_tracks(self, playlist_id: int) -> List[PlaylistTrack]:
        """Get all tracks for a playlist"""
        return self.db.query(PlaylistTrack).options(
            joinedload(PlaylistTrack.added_by)
        ).filter(
            PlaylistTrack.playlist_id == playlist_id
        ).order_by(PlaylistTrack.order_index, PlaylistTrack.created_at).all()
    
    def get_track_by_id(self, track_id: int) -> Optional[PlaylistTrack]:
        """Get playlist track by ID"""
        return self.db.query(PlaylistTrack).filter(PlaylistTrack.id == track_id).first()
    
    # Playlist Vote operations
    def create_playlist_vote(self, vote_data: Dict[str, Any]) -> PlaylistVote:
        """Create a new playlist vote"""
        vote = PlaylistVote(**vote_data)
        self.db.add(vote)
        self.db.commit()
        self.db.refresh(vote)
        
        # Update track vote count
        self.update_track_votes(vote.track_id)
        
        return vote
    
    def get_playlist_vote(self, track_id: int, user_id: int) -> Optional[PlaylistVote]:
        """Get user's vote for a track"""
        return self.db.query(PlaylistVote).filter(
            PlaylistVote.track_id == track_id,
            PlaylistVote.user_id == user_id
        ).first()
    
    def update_playlist_vote(self, vote_id: int, is_upvote: bool) -> Optional[PlaylistVote]:
        """Update playlist vote"""
        vote = self.db.query(PlaylistVote).filter(PlaylistVote.id == vote_id).first()
        if not vote:
            return None
        
        vote.is_upvote = is_upvote
        self.db.commit()
        self.db.refresh(vote)
        
        # Update track vote count
        self.update_track_votes(vote.track_id)
        
        return vote
    
    # Game operations
    def get_game_by_id(
        self, 
        game_id: int, 
        include_relations: bool = False
    ) -> Optional[Game]:
        """Get game by ID with optional relation loading"""
        query = self.db.query(Game).filter(Game.id == game_id)
        
        if include_relations:
            query = query.options(
                joinedload(Game.creator),
                joinedload(Game.event),
                joinedload(Game.sessions),
                joinedload(Game.ratings)
            )
        
        return query.first()
    
    def get_event_games(
        self,
        event_id: int,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Game], int]:
        """Get games for an event"""
        query = self.db.query(Game).options(
            joinedload(Game.creator)
        ).filter(Game.event_id == event_id)
        
        if filters:
            if filters.get('type'):
                query = query.filter(Game.type == filters['type'])
            
            if filters.get('is_active') is not None:
                query = query.filter(Game.is_active == filters['is_active'])
        
        total = query.count()
        
        games = query.order_by(
            desc(Game.is_featured),
            desc(Game.created_at)
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return games, total
    
    def create_game(self, game_data: Dict[str, Any]) -> Game:
        """Create a new game"""
        game = Game(**game_data)
        self.db.add(game)
        self.db.commit()
        self.db.refresh(game)
        return game
    
    def update_game(self, game_id: int, update_data: Dict[str, Any]) -> Optional[Game]:
        """Update game by ID"""
        game = self.get_game_by_id(game_id)
        if not game:
            return None
        
        for field, value in update_data.items():
            if hasattr(game, field):
                setattr(game, field, value)
        
        self.db.commit()
        self.db.refresh(game)
        return game
    
    # Game Session operations
    def create_game_session(self, session_data: Dict[str, Any]) -> GameSession:
        """Create a new game session"""
        session = GameSession(**session_data)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session
    
    def get_game_session_by_id(self, session_id: int) -> Optional[GameSession]:
        """Get game session by ID"""
        return self.db.query(GameSession).options(
            joinedload(GameSession.game),
            joinedload(GameSession.host),
            joinedload(GameSession.participants)
        ).filter(GameSession.id == session_id).first()
    
    def get_active_game_sessions(self, game_id: int) -> List[GameSession]:
        """Get active sessions for a game"""
        return self.db.query(GameSession).filter(
            GameSession.game_id == game_id,
            GameSession.status.in_(['waiting', 'in_progress'])
        ).all()
    
    # Game Participation operations
    def create_game_participation(self, participation_data: Dict[str, Any]) -> GameParticipation:
        """Create a new game participation"""
        participation = GameParticipation(**participation_data)
        self.db.add(participation)
        self.db.commit()
        self.db.refresh(participation)
        return participation
    
    def get_game_participation(self, session_id: int, user_id: int) -> Optional[GameParticipation]:
        """Get user's participation in a game session"""
        return self.db.query(GameParticipation).filter(
            GameParticipation.session_id == session_id,
            GameParticipation.user_id == user_id
        ).first()
    
    # Game Rating operations
    def create_game_rating(self, rating_data: Dict[str, Any]) -> GameRating:
        """Create a new game rating"""
        rating = GameRating(**rating_data)
        self.db.add(rating)
        self.db.commit()
        self.db.refresh(rating)
        
        # Update game stats
        self.update_game_stats(rating.game_id)
        
        return rating
    
    def get_user_game_rating(self, game_id: int, user_id: int) -> Optional[GameRating]:
        """Get user's rating for a game"""
        return self.db.query(GameRating).filter(
            GameRating.game_id == game_id,
            GameRating.user_id == user_id
        ).first()
    
    # Statistics operations
    def get_moodboard_statistics(self, moodboard_id: int) -> Dict[str, Any]:
        """Get statistics for a moodboard"""
        moodboard = self.get_moodboard_by_id(moodboard_id, include_relations=True)
        if not moodboard:
            return {}
        
        return {
            "total_items": len(moodboard.items),
            "total_likes": len(moodboard.likes),
            "total_comments": len(moodboard.comments),
            "engagement_score": len(moodboard.likes) + len(moodboard.comments)
        }
    
    def get_playlist_statistics(self, playlist_id: int) -> Dict[str, Any]:
        """Get statistics for a playlist"""
        playlist = self.get_playlist_by_id(playlist_id, include_relations=True)
        if not playlist:
            return {}
        
        total_duration = sum(track.duration_ms for track in playlist.tracks if track.duration_ms)
        total_votes = sum(track.upvotes + track.downvotes for track in playlist.tracks)
        
        return {
            "total_tracks": len(playlist.tracks),
            "total_duration_ms": total_duration,
            "total_votes": total_votes,
            "average_track_rating": playlist.average_rating
        }
    
    def get_game_statistics(self, game_id: int) -> Dict[str, Any]:
        """Get statistics for a game"""
        game = self.get_game_by_id(game_id, include_relations=True)
        if not game:
            return {}
        
        total_sessions = len(game.sessions)
        completed_sessions = len([s for s in game.sessions if s.status == 'completed'])
        total_participants = sum(len(s.participants) for s in game.sessions)
        
        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "total_participants": total_participants,
            "average_rating": game.average_rating,
            "total_ratings": len(game.ratings)
        }
    
    # Helper methods for updating statistics
    def update_moodboard_stats(self, moodboard_id: int):
        """Update moodboard statistics"""
        moodboard = self.get_moodboard_by_id(moodboard_id)
        if not moodboard:
            return
        
        # Count items, likes, and comments
        moodboard.total_items = self.db.query(func.count(MoodboardItem.id)).filter(
            MoodboardItem.moodboard_id == moodboard_id
        ).scalar() or 0
        
        moodboard.total_likes = self.db.query(func.count(MoodboardLike.id)).filter(
            MoodboardLike.moodboard_id == moodboard_id
        ).scalar() or 0
        
        moodboard.total_comments = self.db.query(func.count(MoodboardComment.id)).filter(
            MoodboardComment.moodboard_id == moodboard_id
        ).scalar() or 0
        
        self.db.commit()
    
    def update_playlist_stats(self, playlist_id: int):
        """Update playlist statistics"""
        playlist = self.get_playlist_by_id(playlist_id)
        if not playlist:
            return
        
        # Count tracks and calculate total duration
        tracks = self.get_playlist_tracks(playlist_id)
        playlist.total_tracks = len(tracks)
        playlist.total_duration_ms = sum(track.duration_ms for track in tracks if track.duration_ms)
        
        self.db.commit()
    
    def update_track_votes(self, track_id: int):
        """Update track vote counts"""
        track = self.get_track_by_id(track_id)
        if not track:
            return
        
        # Count upvotes and downvotes
        track.upvotes = self.db.query(func.count(PlaylistVote.id)).filter(
            PlaylistVote.track_id == track_id,
            PlaylistVote.is_upvote == True
        ).scalar() or 0
        
        track.downvotes = self.db.query(func.count(PlaylistVote.id)).filter(
            PlaylistVote.track_id == track_id,
            PlaylistVote.is_upvote == False
        ).scalar() or 0
        
        self.db.commit()
    
    def update_game_stats(self, game_id: int):
        """Update game statistics"""
        game = self.get_game_by_id(game_id)
        if not game:
            return
        
        # Calculate average rating
        ratings = self.db.query(GameRating).filter(
            GameRating.game_id == game_id
        ).all()
        
        if ratings:
            total_rating = sum(rating.rating for rating in ratings)
            game.average_rating = total_rating / len(ratings)
            game.total_ratings = len(ratings)
        else:
            game.average_rating = 0.0
            game.total_ratings = 0
        
        self.db.commit()