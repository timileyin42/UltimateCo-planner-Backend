from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum, JSON, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.models.shared_models import BaseModel, TimestampMixin
import enum

class MoodboardType(str, enum.Enum):
    """Types of moodboards."""
    DECORATIONS = "decorations"
    FOOD = "food"
    THEMES = "themes"
    COLORS = "colors"
    VENUES = "venues"
    OUTFITS = "outfits"
    GENERAL = "general"

class PlaylistProvider(str, enum.Enum):
    """Music streaming provider."""
    SPOTIFY = "spotify"
    CUSTOM = "custom"

class PlaylistType(str, enum.Enum):
    """Types of playlists."""
    COLLABORATIVE = "collaborative"
    CURATED = "curated"
    GENERATED = "generated"

class GameType(str, enum.Enum):
    """Types of party games."""
    TRIVIA = "trivia"
    ICEBREAKER = "icebreaker"
    PARTY_GAME = "party_game"
    QUIZ = "quiz"
    SCAVENGER_HUNT = "scavenger_hunt"
    BINGO = "bingo"
    CUSTOM = "custom"

class GameDifficulty(str, enum.Enum):
    """Game difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class Moodboard(BaseModel, TimestampMixin):
    """Moodboards for event inspiration."""
    __tablename__ = "moodboards"
    
    # Basic info
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    moodboard_type: Mapped[MoodboardType] = mapped_column(SQLEnum(MoodboardType), default=MoodboardType.GENERAL)
    
    # Relationships
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Settings
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_contributions: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Metadata
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of tags
    color_palette: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of hex colors
    
    # Relationships
    event = relationship("Event", back_populates="moodboards")
    creator = relationship("User", foreign_keys=[creator_id], back_populates="created_moodboards")
    items = relationship("MoodboardItem", back_populates="moodboard", cascade="all, delete-orphan")
    likes = relationship("MoodboardLike", back_populates="moodboard", cascade="all, delete-orphan")
    comments = relationship("MoodboardComment", back_populates="moodboard", cascade="all, delete-orphan")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_moodboard_event_id', 'event_id'),
        Index('idx_moodboard_creator_id', 'creator_id'),
        Index('idx_moodboard_type', 'moodboard_type'),
        Index('idx_moodboard_is_public', 'is_public'),
        Index('idx_moodboard_allow_contributions', 'allow_contributions'),
        Index('idx_moodboard_created_at', 'created_at'),
        Index('idx_moodboard_updated_at', 'updated_at'),
        
        # Combined indexes for common queries
        Index('idx_moodboard_event_public', 'event_id', 'is_public'),
        Index('idx_moodboard_creator_type', 'creator_id', 'moodboard_type'),
        Index('idx_moodboard_type_public', 'moodboard_type', 'is_public'),
        Index('idx_moodboard_event_created', 'event_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Moodboard(id={self.id}, title='{self.title}', type='{self.moodboard_type}')>"
    
    @property
    def item_count(self) -> int:
        """Get number of items in moodboard."""
        return len(self.items) if self.items else 0
    
    @property
    def like_count(self) -> int:
        """Get number of likes."""
        return len(self.likes) if self.likes else 0

class MoodboardItem(BaseModel, TimestampMixin):
    """Items within a moodboard."""
    __tablename__ = "moodboard_items"
    
    # Basic info
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Content
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content_type: Mapped[str] = mapped_column(String(50), default="image")  # image, link, text, color
    
    # Position and styling
    position_x: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    position_y: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Metadata
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_estimate: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    vendor_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON object
    
    # Relationships
    moodboard_id: Mapped[int] = mapped_column(ForeignKey("moodboards.id"), nullable=False)
    added_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    moodboard = relationship("Moodboard", back_populates="items")
    added_by = relationship("User", back_populates="moodboard_items")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_moodboard_item_moodboard_id', 'moodboard_id'),
        Index('idx_moodboard_item_added_by_id', 'added_by_id'),
        Index('idx_moodboard_item_content_type', 'content_type'),
        Index('idx_moodboard_item_created_at', 'created_at'),
        Index('idx_moodboard_item_updated_at', 'updated_at'),
        
        # Combined indexes for common queries
        Index('idx_moodboard_item_board_type', 'moodboard_id', 'content_type'),
        Index('idx_moodboard_item_board_created', 'moodboard_id', 'created_at'),
        Index('idx_moodboard_item_user_created', 'added_by_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<MoodboardItem(id={self.id}, moodboard_id={self.moodboard_id}, type='{self.content_type}')>"

class MoodboardLike(BaseModel, TimestampMixin):
    """Likes for moodboards."""
    __tablename__ = "moodboard_likes"
    
    # Relationships
    moodboard_id: Mapped[int] = mapped_column(ForeignKey("moodboards.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    moodboard = relationship("Moodboard", back_populates="likes")
    user = relationship("User", back_populates="moodboard_likes")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_moodboard_like_moodboard_id', 'moodboard_id'),
        Index('idx_moodboard_like_user_id', 'user_id'),
        Index('idx_moodboard_like_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_moodboard_like_board_user', 'moodboard_id', 'user_id'),
        Index('idx_moodboard_like_user_created', 'user_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<MoodboardLike(id={self.id}, moodboard_id={self.moodboard_id}, user_id={self.user_id})>"

class MoodboardComment(BaseModel, TimestampMixin):
    """Comments on moodboards."""
    __tablename__ = "moodboard_comments"
    
    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Relationships
    moodboard_id: Mapped[int] = mapped_column(ForeignKey("moodboards.id"), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    moodboard = relationship("Moodboard", back_populates="comments")
    author = relationship("User", back_populates="moodboard_comments")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_moodboard_comment_moodboard_id', 'moodboard_id'),
        Index('idx_moodboard_comment_author_id', 'author_id'),
        Index('idx_moodboard_comment_created_at', 'created_at'),
        Index('idx_moodboard_comment_updated_at', 'updated_at'),
        
        # Combined indexes for common queries
        Index('idx_moodboard_comment_board_created', 'moodboard_id', 'created_at'),
        Index('idx_moodboard_comment_author_created', 'author_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<MoodboardComment(id={self.id}, moodboard_id={self.moodboard_id}, author_id={self.author_id})>"

class Playlist(BaseModel, TimestampMixin):
    """Event playlists for music."""
    __tablename__ = "playlists"
    
    # Basic info
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Provider info
    provider: Mapped[PlaylistProvider] = mapped_column(SQLEnum(PlaylistProvider), default=PlaylistProvider.CUSTOM)
    external_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Spotify ID
    external_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Settings
    is_collaborative: Mapped[bool] = mapped_column(Boolean, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_duplicates: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Metadata
    total_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    genre_tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    mood_tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    
    # Relationships
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    event = relationship("Event", back_populates="playlists")
    creator = relationship("User", foreign_keys=[creator_id], back_populates="created_playlists")
    tracks = relationship("PlaylistTrack", back_populates="playlist", cascade="all, delete-orphan")
    votes = relationship("PlaylistVote", back_populates="playlist", cascade="all, delete-orphan")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_playlist_event_id', 'event_id'),
        Index('idx_playlist_creator_id', 'creator_id'),
        Index('idx_playlist_provider', 'provider'),
        Index('idx_playlist_is_collaborative', 'is_collaborative'),
        Index('idx_playlist_is_public', 'is_public'),
        Index('idx_playlist_created_at', 'created_at'),
        Index('idx_playlist_updated_at', 'updated_at'),
        
        # Combined indexes for common queries
        Index('idx_playlist_event_public', 'event_id', 'is_public'),
        Index('idx_playlist_creator_provider', 'creator_id', 'provider'),
        Index('idx_playlist_provider_public', 'provider', 'is_public'),
        Index('idx_playlist_event_collaborative', 'event_id', 'is_collaborative'),
    )
    
    def __repr__(self):
        return f"<Playlist(id={self.id}, title='{self.title}', provider='{self.provider}')>"
    
    @property
    def track_count(self) -> int:
        """Get number of tracks in playlist."""
        return len(self.tracks) if self.tracks else 0

class PlaylistTrack(BaseModel, TimestampMixin):
    """Tracks within a playlist."""
    __tablename__ = "playlist_tracks"
    
    # Track info
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    artist: Mapped[str] = mapped_column(String(200), nullable=False)
    album: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # External references
    spotify_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Metadata
    genre: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    explicit: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Playlist position
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Relationships
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id"), nullable=False)
    added_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    playlist = relationship("Playlist", back_populates="tracks")
    added_by = relationship("User", back_populates="playlist_tracks")
    votes = relationship("PlaylistVote", back_populates="track", cascade="all, delete-orphan")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_playlist_track_playlist_id', 'playlist_id'),
        Index('idx_playlist_track_added_by_id', 'added_by_id'),
        Index('idx_playlist_track_position', 'position'),
        Index('idx_playlist_track_genre', 'genre'),
        Index('idx_playlist_track_year', 'year'),
        Index('idx_playlist_track_explicit', 'explicit'),
        Index('idx_playlist_track_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_playlist_track_playlist_position', 'playlist_id', 'position'),
        Index('idx_playlist_track_playlist_created', 'playlist_id', 'created_at'),
        Index('idx_playlist_track_user_created', 'added_by_id', 'created_at'),
        Index('idx_playlist_track_genre_year', 'genre', 'year'),
    )
    
    def __repr__(self):
        return f"<PlaylistTrack(id={self.id}, title='{self.title}', artist='{self.artist}')>"

class PlaylistVote(BaseModel, TimestampMixin):
    """Votes on playlist tracks."""
    __tablename__ = "playlist_votes"
    
    # Vote info
    vote_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'like', 'dislike', 'love'
    
    # Relationships
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id"), nullable=False)
    track_id: Mapped[Optional[int]] = mapped_column(ForeignKey("playlist_tracks.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    playlist = relationship("Playlist", back_populates="votes")
    track = relationship("PlaylistTrack", back_populates="votes")
    user = relationship("User", back_populates="playlist_votes")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_playlist_vote_playlist_id', 'playlist_id'),
        Index('idx_playlist_vote_track_id', 'track_id'),
        Index('idx_playlist_vote_user_id', 'user_id'),
        Index('idx_playlist_vote_type', 'vote_type'),
        Index('idx_playlist_vote_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_playlist_vote_playlist_user', 'playlist_id', 'user_id'),
        Index('idx_playlist_vote_track_user', 'track_id', 'user_id'),
        Index('idx_playlist_vote_track_type', 'track_id', 'vote_type'),
        Index('idx_playlist_vote_user_type', 'user_id', 'vote_type'),
    )
    
    def __repr__(self):
        return f"<PlaylistVote(id={self.id}, type='{self.vote_type}', user_id={self.user_id})>"

class Game(BaseModel, TimestampMixin):
    """Party games and icebreakers."""
    __tablename__ = "games"
    
    # Basic info
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    game_type: Mapped[GameType] = mapped_column(SQLEnum(GameType), nullable=False)
    difficulty: Mapped[GameDifficulty] = mapped_column(SQLEnum(GameDifficulty), default=GameDifficulty.MEDIUM)
    
    # Game settings
    min_players: Mapped[int] = mapped_column(Integer, default=2)
    max_players: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Content
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    materials_needed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    game_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON object for questions, etc.
    
    # Settings
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    age_appropriate: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Metadata
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    categories: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    
    # Relationships
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True)  # Can be global
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    event = relationship("Event", back_populates="games")
    creator = relationship("User", foreign_keys=[creator_id], back_populates="created_games")
    sessions = relationship("GameSession", back_populates="game", cascade="all, delete-orphan")
    ratings = relationship("GameRating", back_populates="game", cascade="all, delete-orphan")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_game_event_id', 'event_id'),
        Index('idx_game_creator_id', 'creator_id'),
        Index('idx_game_type', 'game_type'),
        Index('idx_game_difficulty', 'difficulty'),
        Index('idx_game_min_players', 'min_players'),
        Index('idx_game_max_players', 'max_players'),
        Index('idx_game_is_public', 'is_public'),
        Index('idx_game_age_appropriate', 'age_appropriate'),
        Index('idx_game_created_at', 'created_at'),
        Index('idx_game_updated_at', 'updated_at'),
        
        # Combined indexes for common queries
        Index('idx_game_type_difficulty', 'game_type', 'difficulty'),
        Index('idx_game_public_type', 'is_public', 'game_type'),
        Index('idx_game_creator_type', 'creator_id', 'game_type'),
        Index('idx_game_event_type', 'event_id', 'game_type'),
        Index('idx_game_players_difficulty', 'min_players', 'max_players', 'difficulty'),
    )
    
    def __repr__(self):
        return f"<Game(id={self.id}, title='{self.title}', type='{self.game_type}')>"
    
    @property
    def average_rating(self) -> float:
        """Get average rating for the game."""
        if not self.ratings:
            return 0.0
        return sum(rating.rating for rating in self.ratings) / len(self.ratings)

class GameSession(BaseModel, TimestampMixin):
    """Active game sessions during events."""
    __tablename__ = "game_sessions"
    
    # Session info
    status: Mapped[str] = mapped_column(String(20), default="waiting")  # waiting, active, completed, cancelled
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Game state
    current_round: Mapped[int] = mapped_column(Integer, default=1)
    total_rounds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    session_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON object for game state
    
    # Settings
    max_participants: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Relationships
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    host_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    game = relationship("Game", back_populates="sessions")
    event = relationship("Event", back_populates="game_sessions")
    host = relationship("User", foreign_keys=[host_id], back_populates="hosted_game_sessions")
    participants = relationship("GameParticipant", back_populates="session", cascade="all, delete-orphan")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_game_session_game_id', 'game_id'),
        Index('idx_game_session_event_id', 'event_id'),
        Index('idx_game_session_host_id', 'host_id'),
        Index('idx_game_session_status', 'status'),
        Index('idx_game_session_start_time', 'start_time'),
        Index('idx_game_session_end_time', 'end_time'),
        Index('idx_game_session_current_round', 'current_round'),
        Index('idx_game_session_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_game_session_game_status', 'game_id', 'status'),
        Index('idx_game_session_event_status', 'event_id', 'status'),
        Index('idx_game_session_host_status', 'host_id', 'status'),
        Index('idx_game_session_game_created', 'game_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<GameSession(id={self.id}, game_id={self.game_id}, status='{self.status}')>"
    
    @property
    def participant_count(self) -> int:
        """Get number of participants."""
        return len(self.participants) if self.participants else 0

class GameParticipant(BaseModel, TimestampMixin):
    """Participants in game sessions."""
    __tablename__ = "game_participants"
    
    # Participation info
    score: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Final ranking
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    session_id: Mapped[int] = mapped_column(ForeignKey("game_sessions.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    session = relationship("GameSession", back_populates="participants")
    user = relationship("User", back_populates="game_participations")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_game_participant_session_id', 'session_id'),
        Index('idx_game_participant_user_id', 'user_id'),
        Index('idx_game_participant_score', 'score'),
        Index('idx_game_participant_position', 'position'),
        Index('idx_game_participant_is_active', 'is_active'),
        
        # Combined indexes for common queries
        Index('idx_game_participant_session_user', 'session_id', 'user_id'),
        Index('idx_game_participant_session_score', 'session_id', 'score'),
        Index('idx_game_participant_session_active', 'session_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<GameParticipant(id={self.id}, session_id={self.session_id}, user_id={self.user_id}, score={self.score})>"

class GameRating(BaseModel, TimestampMixin):
    """Ratings for games."""
    __tablename__ = "game_ratings"
    
    # Rating info
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5 stars
    review: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    game = relationship("Game", back_populates="ratings")
    user = relationship("User", back_populates="game_ratings")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_game_rating_game_id', 'game_id'),
        Index('idx_game_rating_user_id', 'user_id'),
        Index('idx_game_rating_rating', 'rating'),
        Index('idx_game_rating_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_game_rating_game_user', 'game_id', 'user_id'),
        Index('idx_game_rating_game_rating', 'game_id', 'rating'),
        Index('idx_game_rating_user_rating', 'user_id', 'rating'),
        Index('idx_game_rating_game_created', 'game_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<GameRating(id={self.id}, game_id={self.game_id}, rating={self.rating})>"