from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.deps import get_db, get_current_active_user
from app.core.errors import http_400_bad_request, http_404_not_found, http_403_forbidden
from app.services.creative_service import CreativeService
from app.schemas.creative import (
    # Moodboard schemas
    MoodboardCreate, MoodboardUpdate, MoodboardResponse, MoodboardListResponse,
    MoodboardItemCreate, MoodboardItemUpdate, MoodboardItemResponse,
    MoodboardCommentCreate, MoodboardCommentResponse, MoodboardSearchParams,
    
    # Playlist schemas
    PlaylistCreate, PlaylistUpdate, PlaylistResponse, PlaylistListResponse,
    PlaylistTrackCreate, PlaylistTrackResponse, PlaylistVoteCreate,
    PlaylistSearchParams,
    
    # Game schemas
    GameCreate, GameUpdate, GameResponse, GameListResponse,
    GameSessionCreate, GameSessionUpdate, GameSessionResponse,
    GameRatingCreate, GameRatingResponse, GameSearchParams,
    
    # Statistics
    CreativeStatistics
)
from app.models.user_models import User
from pydantic import BaseModel

creative_router = APIRouter()

# Moodboard endpoints
@creative_router.post("/events/{event_id}/moodboards", response_model=MoodboardResponse)
async def create_moodboard(
    event_id: int,
    moodboard_data: MoodboardCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new moodboard for an event"""
    try:
        creative_service = CreativeService(db)
        moodboard = creative_service.create_moodboard(event_id, current_user.id, moodboard_data)
        
        return MoodboardResponse.model_validate(moodboard)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower() or "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to create moodboard")

@creative_router.get("/events/{event_id}/moodboards", response_model=MoodboardListResponse)
async def get_event_moodboards(
    event_id: int,
    search_params: MoodboardSearchParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get moodboards for an event"""
    try:
        creative_service = CreativeService(db)
        moodboards, total = creative_service.get_event_moodboards(event_id, current_user.id, search_params)
        
        moodboard_responses = [MoodboardResponse.model_validate(mb) for mb in moodboards]
        
        return MoodboardListResponse(
            moodboards=moodboard_responses,
            total=total,
            page=search_params.page,
            per_page=search_params.per_page,
            has_next=(search_params.page * search_params.per_page) < total,
            has_prev=search_params.page > 1
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get moodboards")

@creative_router.get("/moodboards/{moodboard_id}", response_model=MoodboardResponse)
async def get_moodboard(
    moodboard_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific moodboard by ID"""
    try:
        creative_service = CreativeService(db)
        moodboard = creative_service.get_moodboard(moodboard_id, current_user.id)
        
        if not moodboard:
            raise http_404_not_found("Moodboard not found")
        
        return MoodboardResponse.model_validate(moodboard)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get moodboard")

@creative_router.put("/moodboards/{moodboard_id}", response_model=MoodboardResponse)
async def update_moodboard(
    moodboard_id: int,
    update_data: MoodboardUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a moodboard"""
    try:
        creative_service = CreativeService(db)
        moodboard = creative_service.update_moodboard(moodboard_id, current_user.id, update_data)
        
        return MoodboardResponse.model_validate(moodboard)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to update moodboard")

@creative_router.delete("/moodboards/{moodboard_id}")
async def delete_moodboard(
    moodboard_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a moodboard"""
    try:
        creative_service = CreativeService(db)
        success = creative_service.delete_moodboard(moodboard_id, current_user.id)
        
        return {"message": "Moodboard deleted successfully", "success": success}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to delete moodboard")

# Moodboard item endpoints
@creative_router.post("/moodboards/{moodboard_id}/items", response_model=MoodboardItemResponse)
async def add_moodboard_item(
    moodboard_id: int,
    item_data: MoodboardItemCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add an item to a moodboard"""
    try:
        creative_service = CreativeService(db)
        item = creative_service.add_moodboard_item(moodboard_id, current_user.id, item_data)
        
        return MoodboardItemResponse.model_validate(item)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower() or "contributions" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to add moodboard item")

@creative_router.put("/moodboard-items/{item_id}", response_model=MoodboardItemResponse)
async def update_moodboard_item(
    item_id: int,
    update_data: MoodboardItemUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a moodboard item"""
    try:
        creative_service = CreativeService(db)
        item = creative_service.update_moodboard_item(item_id, current_user.id, update_data)
        
        return MoodboardItemResponse.model_validate(item)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to update moodboard item")

@creative_router.delete("/moodboard-items/{item_id}")
async def delete_moodboard_item(
    item_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a moodboard item"""
    try:
        creative_service = CreativeService(db)
        success = creative_service.delete_moodboard_item(item_id, current_user.id)
        
        return {"message": "Moodboard item deleted successfully", "success": success}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to delete moodboard item")

# Moodboard interactions
@creative_router.post("/moodboards/{moodboard_id}/like")
async def toggle_moodboard_like(
    moodboard_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Toggle like on a moodboard"""
    try:
        creative_service = CreativeService(db)
        is_liked = creative_service.toggle_moodboard_like(moodboard_id, current_user.id)
        
        return {
            "message": "Liked" if is_liked else "Unliked",
            "is_liked": is_liked
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request("Failed to toggle like")

@creative_router.post("/moodboards/{moodboard_id}/comments", response_model=MoodboardCommentResponse)
async def add_moodboard_comment(
    moodboard_id: int,
    comment_data: MoodboardCommentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add a comment to a moodboard"""
    try:
        creative_service = CreativeService(db)
        comment = creative_service.add_moodboard_comment(
            moodboard_id, current_user.id, comment_data.content
        )
        
        return MoodboardCommentResponse.model_validate(comment)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to add comment")

# Playlist endpoints
@creative_router.post("/events/{event_id}/playlists", response_model=PlaylistResponse)
async def create_playlist(
    event_id: int,
    playlist_data: PlaylistCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new playlist for an event"""
    try:
        creative_service = CreativeService(db)
        playlist = creative_service.create_playlist(event_id, current_user.id, playlist_data)
        
        return PlaylistResponse.model_validate(playlist)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to create playlist")

@creative_router.get("/events/{event_id}/playlists", response_model=PlaylistListResponse)
async def get_event_playlists(
    event_id: int,
    search_params: PlaylistSearchParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get playlists for an event"""
    try:
        creative_service = CreativeService(db)
        playlists, total = creative_service.get_event_playlists(event_id, current_user.id, search_params)
        
        playlist_responses = [PlaylistResponse.model_validate(pl) for pl in playlists]
        
        return PlaylistListResponse(
            playlists=playlist_responses,
            total=total,
            page=search_params.page,
            per_page=search_params.per_page,
            has_next=(search_params.page * search_params.per_page) < total,
            has_prev=search_params.page > 1
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get playlists")

@creative_router.get("/playlists/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(
    playlist_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific playlist by ID"""
    try:
        creative_service = CreativeService(db)
        playlist = creative_service.get_playlist(playlist_id, current_user.id)
        
        if not playlist:
            raise http_404_not_found("Playlist not found")
        
        return PlaylistResponse.model_validate(playlist)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get playlist")

@creative_router.post("/playlists/{playlist_id}/tracks", response_model=PlaylistTrackResponse)
async def add_playlist_track(
    playlist_id: int,
    track_data: PlaylistTrackCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add a track to a playlist"""
    try:
        creative_service = CreativeService(db)
        track = creative_service.add_playlist_track(playlist_id, current_user.id, track_data)
        
        return PlaylistTrackResponse.model_validate(track)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "collaborative" in str(e).lower() or "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        elif "already exists" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request("Failed to add track")

@creative_router.delete("/playlist-tracks/{track_id}")
async def remove_playlist_track(
    track_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Remove a track from a playlist"""
    try:
        creative_service = CreativeService(db)
        success = creative_service.remove_playlist_track(track_id, current_user.id)
        
        return {"message": "Track removed successfully", "success": success}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to remove track")

# Game endpoints
@creative_router.post("/events/{event_id}/games", response_model=GameResponse)
async def create_game(
    event_id: int,
    game_data: GameCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new game for an event"""
    try:
        creative_service = CreativeService(db)
        game = creative_service.create_game(event_id, current_user.id, game_data)
        
        return GameResponse.model_validate(game)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to create game")

@creative_router.post("/games", response_model=GameResponse)
async def create_global_game(
    game_data: GameCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a global game (not event-specific)"""
    try:
        creative_service = CreativeService(db)
        game = creative_service.create_game(None, current_user.id, game_data)
        
        return GameResponse.model_validate(game)
        
    except Exception as e:
        raise http_400_bad_request("Failed to create game")

@creative_router.get("/events/{event_id}/games", response_model=GameListResponse)
async def get_event_games(
    event_id: int,
    search_params: GameSearchParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get games for an event (including global games)"""
    try:
        creative_service = CreativeService(db)
        games, total = creative_service.get_event_games(event_id, current_user.id, search_params)
        
        game_responses = [GameResponse.model_validate(game) for game in games]
        
        return GameListResponse(
            games=game_responses,
            total=total,
            page=search_params.page,
            per_page=search_params.per_page,
            has_next=(search_params.page * search_params.per_page) < total,
            has_prev=search_params.page > 1
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get games")

@creative_router.get("/games/{game_id}", response_model=GameResponse)
async def get_game(
    game_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific game by ID"""
    try:
        creative_service = CreativeService(db)
        game = creative_service.get_game(game_id, current_user.id)
        
        if not game:
            raise http_404_not_found("Game not found")
        
        return GameResponse.model_validate(game)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get game")

# Game session endpoints
@creative_router.post("/events/{event_id}/game-sessions", response_model=GameSessionResponse)
async def start_game_session(
    event_id: int,
    session_data: GameSessionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Start a new game session"""
    try:
        creative_service = CreativeService(db)
        session = creative_service.start_game_session(event_id, current_user.id, session_data)
        
        return GameSessionResponse.model_validate(session)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to start game session")

@creative_router.post("/game-sessions/{session_id}/join")
async def join_game_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Join a game session"""
    try:
        creative_service = CreativeService(db)
        participant = creative_service.join_game_session(session_id, current_user.id)
        
        return {
            "message": "Joined game session successfully",
            "participant_id": participant.id
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        elif "full" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request("Failed to join game session")

@creative_router.post("/games/{game_id}/rate", response_model=GameRatingResponse)
async def rate_game(
    game_id: int,
    rating_data: GameRatingCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Rate a game"""
    try:
        creative_service = CreativeService(db)
        rating = creative_service.rate_game(
            game_id, current_user.id, rating_data.rating, rating_data.review
        )
        
        return GameRatingResponse.model_validate(rating)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request("Failed to rate game")

# Statistics endpoint
@creative_router.get("/events/{event_id}/creative-stats", response_model=CreativeStatistics)
async def get_creative_statistics(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get creative features statistics for an event"""
    try:
        creative_service = CreativeService(db)
        stats = creative_service.get_creative_statistics(event_id, current_user.id)
        
        return CreativeStatistics(**stats)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get statistics")

# File upload endpoint for moodboard images
@creative_router.post("/moodboards/{moodboard_id}/upload-image")
async def upload_moodboard_image(
    moodboard_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload an image for a moodboard item"""
    try:
        from app.services.gcp_storage_service import gcp_storage_service
        
        # Read file content
        file_content = await file.read()
        
        # Validate file
        validation = gcp_storage_service.validate_file(
            filename=file.filename,
            file_size=len(file_content),
            content_type=file.content_type,
            allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp'],
            max_size_mb=10
        )
        
        if not validation["is_valid"]:
            raise http_400_bad_request(f"File validation failed: {', '.join(validation['errors'])}")
        
        # Upload to GCP Storage
        upload_result = await gcp_storage_service.upload_file(
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type,
            folder=f"moodboards/{moodboard_id}",
            user_id=current_user.id
        )
        
        return {
            "message": "Image uploaded successfully",
            "file_url": upload_result["file_url"],
            "file_name": upload_result["filename"],
            "unique_filename": upload_result["unique_filename"],
            "file_size": upload_result["file_size"],
            "content_type": upload_result["content_type"],
            "uploaded_at": upload_result["uploaded_at"]
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        elif "validation failed" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request("Failed to upload image")

# Spotify integration endpoints (placeholder)
@creative_router.post("/playlists/{playlist_id}/sync-spotify")
async def sync_spotify_playlist(
    playlist_id: int,
    spotify_playlist_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Sync playlist with Spotify (requires Spotify integration)"""
    try:
        # This would integrate with Spotify Web API
        # For now, return a placeholder response
        return {
            "message": "Spotify sync initiated",
            "playlist_id": playlist_id,
            "spotify_playlist_id": spotify_playlist_id,
            "status": "pending"
        }
        
    except Exception as e:
        raise http_400_bad_request("Failed to sync with Spotify")

@creative_router.get("/playlists/{playlist_id}/spotify-tracks")
async def search_spotify_tracks(
    playlist_id: int,
    query: str = Query(..., description="Search query for tracks"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Search Spotify tracks to add to playlist"""
    try:
        # This would search Spotify Web API
        # For now, return mock data
        mock_tracks = [
            {
                "id": "spotify_track_1",
                "title": "Sample Song 1",
                "artist": "Sample Artist 1",
                "album": "Sample Album 1",
                "duration_seconds": 180,
                "preview_url": "https://example.com/preview1.mp3"
            },
            {
                "id": "spotify_track_2",
                "title": "Sample Song 2",
                "artist": "Sample Artist 2",
                "album": "Sample Album 2",
                "duration_seconds": 210,
                "preview_url": "https://example.com/preview2.mp3"
            }
        ]
        
        return {
            "query": query,
            "tracks": mock_tracks,
            "total": len(mock_tracks)
        }
        
    except Exception as e:
        raise http_400_bad_request("Failed to search Spotify tracks")