from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.creative_models import (
    MoodboardType, PlaylistProvider, GameType, GameDifficulty
)

# Base schemas
class UserBasic(BaseModel):
    """Basic user info for creative feature responses."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    full_name: str
    username: Optional[str] = None
    avatar_url: Optional[str] = None

# Moodboard schemas
class MoodboardBase(BaseModel):
    """Base moodboard schema."""
    title: str = Field(..., min_length=1, max_length=200, description="Moodboard title")
    description: Optional[str] = Field(None, max_length=1000, description="Moodboard description")
    moodboard_type: MoodboardType = Field(default=MoodboardType.GENERAL, description="Type of moodboard")
    is_public: bool = Field(default=True, description="Whether moodboard is public")
    allow_contributions: bool = Field(default=True, description="Allow others to add items")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    color_palette: Optional[List[str]] = Field(None, description="Color palette (hex codes)")

class MoodboardCreate(MoodboardBase):
    """Schema for creating a moodboard."""
    pass

class MoodboardUpdate(BaseModel):
    """Schema for updating a moodboard."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    moodboard_type: Optional[MoodboardType] = None
    is_public: Optional[bool] = None
    allow_contributions: Optional[bool] = None
    tags: Optional[List[str]] = None
    color_palette: Optional[List[str]] = None

class MoodboardItemBase(BaseModel):
    """Base moodboard item schema."""
    title: Optional[str] = Field(None, max_length=200, description="Item title")
    description: Optional[str] = Field(None, max_length=1000, description="Item description")
    image_url: Optional[str] = Field(None, description="Image URL")
    source_url: Optional[str] = Field(None, description="Source URL")
    content_type: str = Field(default="image", description="Content type")
    position_x: Optional[int] = Field(None, description="X position on board")
    position_y: Optional[int] = Field(None, description="Y position on board")
    width: Optional[int] = Field(None, description="Item width")
    height: Optional[int] = Field(None, description="Item height")
    tags: Optional[List[str]] = Field(None, description="Item tags")
    notes: Optional[str] = Field(None, description="Personal notes")
    price_estimate: Optional[str] = Field(None, description="Estimated price")
    vendor_info: Optional[Dict[str, Any]] = Field(None, description="Vendor information")

class MoodboardItemCreate(MoodboardItemBase):
    """Schema for creating a moodboard item."""
    pass

class MoodboardItemUpdate(BaseModel):
    """Schema for updating a moodboard item."""
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    price_estimate: Optional[str] = None
    vendor_info: Optional[Dict[str, Any]] = None

class MoodboardItemResponse(MoodboardItemBase):
    """Schema for moodboard item response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    moodboard_id: int
    added_by: UserBasic
    created_at: datetime
    updated_at: datetime

class MoodboardResponse(MoodboardBase):
    """Schema for moodboard response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    event_id: int
    creator: UserBasic
    item_count: int
    like_count: int
    created_at: datetime
    updated_at: datetime
    items: List[MoodboardItemResponse] = []

class MoodboardCommentCreate(BaseModel):
    """Schema for creating a moodboard comment."""
    content: str = Field(..., min_length=1, max_length=1000, description="Comment content")

class MoodboardCommentResponse(BaseModel):
    """Schema for moodboard comment response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    content: str
    author: UserBasic
    created_at: datetime

# Playlist schemas
class PlaylistBase(BaseModel):
    """Base playlist schema."""
    title: str = Field(..., min_length=1, max_length=200, description="Playlist title")
    description: Optional[str] = Field(None, max_length=1000, description="Playlist description")
    provider: PlaylistProvider = Field(default=PlaylistProvider.CUSTOM, description="Music provider")
    external_id: Optional[str] = Field(None, description="External playlist ID")
    external_url: Optional[str] = Field(None, description="External playlist URL")
    is_collaborative: bool = Field(default=True, description="Allow others to add tracks")
    is_public: bool = Field(default=True, description="Whether playlist is public")
    allow_duplicates: bool = Field(default=False, description="Allow duplicate tracks")
    genre_tags: Optional[List[str]] = Field(None, description="Genre tags")
    mood_tags: Optional[List[str]] = Field(None, description="Mood tags")

class PlaylistCreate(PlaylistBase):
    """Schema for creating a playlist."""
    pass

class PlaylistUpdate(BaseModel):
    """Schema for updating a playlist."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    is_collaborative: Optional[bool] = None
    is_public: Optional[bool] = None
    allow_duplicates: Optional[bool] = None
    genre_tags: Optional[List[str]] = None
    mood_tags: Optional[List[str]] = None

class PlaylistTrackBase(BaseModel):
    """Base playlist track schema."""
    title: str = Field(..., min_length=1, max_length=200, description="Track title")
    artist: str = Field(..., min_length=1, max_length=200, description="Artist name")
    album: Optional[str] = Field(None, max_length=200, description="Album name")
    duration_seconds: Optional[int] = Field(None, ge=0, description="Track duration in seconds")
    spotify_id: Optional[str] = Field(None, description="Spotify track ID")
    apple_music_id: Optional[str] = Field(None, description="Apple Music track ID")
    youtube_id: Optional[str] = Field(None, description="YouTube track ID")
    genre: Optional[str] = Field(None, description="Track genre")
    year: Optional[int] = Field(None, ge=1900, le=2100, description="Release year")
    explicit: bool = Field(default=False, description="Explicit content")

class PlaylistTrackCreate(PlaylistTrackBase):
    """Schema for adding a track to playlist."""
    position: Optional[int] = Field(None, description="Position in playlist")

class PlaylistTrackResponse(PlaylistTrackBase):
    """Schema for playlist track response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    playlist_id: int
    position: int
    added_by: UserBasic
    created_at: datetime

class PlaylistVoteCreate(BaseModel):
    """Schema for voting on playlist tracks."""
    vote_type: str = Field(..., description="Vote type: like, dislike, love")
    track_id: Optional[int] = Field(None, description="Specific track ID (optional)")

class PlaylistResponse(PlaylistBase):
    """Schema for playlist response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    event_id: int
    creator: UserBasic
    track_count: int
    total_duration_seconds: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    tracks: List[PlaylistTrackResponse] = []

# Game schemas
class GameBase(BaseModel):
    """Base game schema."""
    title: str = Field(..., min_length=1, max_length=200, description="Game title")
    description: str = Field(..., min_length=1, max_length=2000, description="Game description")
    game_type: GameType = Field(..., description="Type of game")
    difficulty: GameDifficulty = Field(default=GameDifficulty.MEDIUM, description="Game difficulty")
    min_players: int = Field(default=2, ge=1, description="Minimum players")
    max_players: Optional[int] = Field(None, ge=1, description="Maximum players")
    estimated_duration_minutes: Optional[int] = Field(None, ge=1, description="Estimated duration")
    instructions: str = Field(..., min_length=1, description="Game instructions")
    materials_needed: Optional[List[str]] = Field(None, description="Required materials")
    game_data: Optional[Dict[str, Any]] = Field(None, description="Game-specific data")
    is_public: bool = Field(default=True, description="Whether game is public")
    age_appropriate: bool = Field(default=True, description="Age appropriate content")
    tags: Optional[List[str]] = Field(None, description="Game tags")
    categories: Optional[List[str]] = Field(None, description="Game categories")

class GameCreate(GameBase):
    """Schema for creating a game."""
    pass

class GameUpdate(BaseModel):
    """Schema for updating a game."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1, max_length=2000)
    difficulty: Optional[GameDifficulty] = None
    min_players: Optional[int] = Field(None, ge=1)
    max_players: Optional[int] = Field(None, ge=1)
    estimated_duration_minutes: Optional[int] = Field(None, ge=1)
    instructions: Optional[str] = Field(None, min_length=1)
    materials_needed: Optional[List[str]] = None
    game_data: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None
    age_appropriate: Optional[bool] = None
    tags: Optional[List[str]] = None
    categories: Optional[List[str]] = None

class GameResponse(GameBase):
    """Schema for game response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    event_id: Optional[int] = None
    creator: UserBasic
    average_rating: float
    created_at: datetime
    updated_at: datetime

class GameSessionBase(BaseModel):
    """Base game session schema."""
    max_participants: Optional[int] = Field(None, ge=1, description="Maximum participants")
    total_rounds: Optional[int] = Field(None, ge=1, description="Total rounds")

class GameSessionCreate(GameSessionBase):
    """Schema for creating a game session."""
    game_id: int = Field(..., description="Game ID")

class GameSessionUpdate(BaseModel):
    """Schema for updating a game session."""
    status: Optional[str] = Field(None, description="Session status")
    current_round: Optional[int] = Field(None, ge=1)
    session_data: Optional[Dict[str, Any]] = Field(None, description="Game state data")

class GameParticipantResponse(BaseModel):
    """Schema for game participant response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user: UserBasic
    score: int
    position: Optional[int] = None
    is_active: bool

class GameSessionResponse(GameSessionBase):
    """Schema for game session response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    game_id: int
    event_id: int
    host: UserBasic
    status: str
    current_round: int
    participant_count: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: datetime
    participants: List[GameParticipantResponse] = []

class GameRatingCreate(BaseModel):
    """Schema for creating a game rating."""
    rating: int = Field(..., ge=1, le=5, description="Rating from 1-5 stars")
    review: Optional[str] = Field(None, max_length=1000, description="Optional review")

class GameRatingResponse(BaseModel):
    """Schema for game rating response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    rating: int
    review: Optional[str] = None
    user: UserBasic
    created_at: datetime

# Search and filter schemas
class MoodboardSearchParams(BaseModel):
    """Schema for moodboard search parameters."""
    query: Optional[str] = Field(None, description="Search query")
    moodboard_type: Optional[MoodboardType] = Field(None, description="Filter by type")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    creator_id: Optional[int] = Field(None, description="Filter by creator")
    is_public: Optional[bool] = Field(None, description="Filter by visibility")
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")

class PlaylistSearchParams(BaseModel):
    """Schema for playlist search parameters."""
    query: Optional[str] = Field(None, description="Search query")
    provider: Optional[PlaylistProvider] = Field(None, description="Filter by provider")
    genre_tags: Optional[List[str]] = Field(None, description="Filter by genre")
    mood_tags: Optional[List[str]] = Field(None, description="Filter by mood")
    creator_id: Optional[int] = Field(None, description="Filter by creator")
    is_collaborative: Optional[bool] = Field(None, description="Filter by collaboration")
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")

class GameSearchParams(BaseModel):
    """Schema for game search parameters."""
    query: Optional[str] = Field(None, description="Search query")
    game_type: Optional[GameType] = Field(None, description="Filter by type")
    difficulty: Optional[GameDifficulty] = Field(None, description="Filter by difficulty")
    min_players: Optional[int] = Field(None, description="Minimum players")
    max_players: Optional[int] = Field(None, description="Maximum players")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    categories: Optional[List[str]] = Field(None, description="Filter by categories")
    age_appropriate: Optional[bool] = Field(None, description="Age appropriate only")
    creator_id: Optional[int] = Field(None, description="Filter by creator")
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")

# List response schemas
class MoodboardListResponse(BaseModel):
    """Schema for paginated moodboard list."""
    moodboards: List[MoodboardResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

class PlaylistListResponse(BaseModel):
    """Schema for paginated playlist list."""
    playlists: List[PlaylistResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

class GameListResponse(BaseModel):
    """Schema for paginated game list."""
    games: List[GameResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

# Statistics schemas
class CreativeStatistics(BaseModel):
    """Schema for creative features statistics."""
    total_moodboards: int
    total_playlists: int
    total_games: int
    active_game_sessions: int
    most_popular_moodboard_type: Optional[str] = None
    most_popular_game_type: Optional[str] = None
    average_playlist_length: Optional[float] = None
    total_playlist_tracks: int

# Integration schemas
class SpotifyIntegration(BaseModel):
    """Schema for Spotify integration."""
    access_token: str = Field(..., description="Spotify access token")
    refresh_token: Optional[str] = Field(None, description="Spotify refresh token")
    playlist_id: Optional[str] = Field(None, description="Spotify playlist ID")

class AppleMusicIntegration(BaseModel):
    """Schema for Apple Music integration."""
    developer_token: str = Field(..., description="Apple Music developer token")
    user_token: str = Field(..., description="Apple Music user token")
    playlist_id: Optional[str] = Field(None, description="Apple Music playlist ID")

# Bulk operations
class BulkMoodboardItemCreate(BaseModel):
    """Schema for bulk creating moodboard items."""
    items: List[MoodboardItemCreate] = Field(..., min_items=1, max_items=50)

class BulkPlaylistTrackCreate(BaseModel):
    """Schema for bulk adding playlist tracks."""
    tracks: List[PlaylistTrackCreate] = Field(..., min_items=1, max_items=100)

# Export schemas
class MoodboardExportRequest(BaseModel):
    """Schema for moodboard export request."""
    format: str = Field(default="pdf", description="Export format: pdf, png, json")
    include_items: bool = Field(default=True, description="Include all items")
    include_comments: bool = Field(default=False, description="Include comments")
    layout: str = Field(default="grid", description="Layout style: grid, collage, list")

class PlaylistExportRequest(BaseModel):
    """Schema for playlist export request."""
    format: str = Field(default="m3u", description="Export format: m3u, json, csv")
    include_metadata: bool = Field(default=True, description="Include track metadata")
    provider_links: bool = Field(default=True, description="Include streaming links")