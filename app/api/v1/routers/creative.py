from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import json
from app.core.deps import get_db, get_current_active_user
from app.core.errors import http_400_bad_request, http_404_not_found, http_403_forbidden
from app.services.creative_service import CreativeService
from app.services.spotify_service import SpotifyService
from app.core.logger import get_logger

logger = get_logger(__name__)
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
    
    # Question/Answer schemas
    GameQuestionsResponse, SubmitAnswerRequest, AnswerResult,
    GenerateQuestionsRequest,
    
    # Game Template schemas
    GameTemplateResponse, GameTemplateListResponse, CreateGameFromTemplateRequest,
    
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
        result = creative_service.like_moodboard(moodboard_id, current_user.id)
        action = result.get("action", "liked")

        return {
            "message": action.capitalize(),
            "action": action
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
            moodboard_id, current_user.id, comment_data.model_dump()
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

# Game Template endpoints (must come BEFORE /games/{game_id} to avoid route conflicts)
@creative_router.get("/games/templates", response_model=GameTemplateListResponse)
async def get_game_templates(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all available game templates."""
    try:
        creative_service = CreativeService(db)
        templates = creative_service.get_all_game_templates()
        return GameTemplateListResponse(**templates)
    except Exception as e:
        logger.error(f"Failed to get templates: {str(e)}")
        raise http_400_bad_request(f"Failed to retrieve templates: {str(e)}")

@creative_router.get("/games/templates/{game_type}/{template_name}", response_model=GameTemplateResponse)
async def get_template_details(
    game_type: str,
    template_name: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get details for a specific game template."""
    try:
        creative_service = CreativeService(db)
        template = creative_service.get_template_details(game_type, template_name)
        return GameTemplateResponse(**template)
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request(f"Failed to get template: {str(e)}")

@creative_router.post("/games/from-template", response_model=GameResponse)
async def create_game_from_template(
    template_data: CreateGameFromTemplateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new game from a pre-defined template."""
    try:
        creative_service = CreativeService(db)
        game = creative_service.create_game_from_template(
            user_id=current_user.id,
            game_type=template_data.game_type,
            template_name=template_data.template_name,
            event_id=template_data.event_id,
            custom_title=template_data.title,
            custom_description=template_data.description,
            custom_instructions=template_data.instructions,
            is_public=template_data.is_public,
            customizations=template_data.customizations
        )
        
        return GameResponse.model_validate(game)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            logger.error(f"Failed to create game from template: {str(e)}")
            raise http_400_bad_request(f"Failed to create game from template: {str(e)}")

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

@creative_router.get("/games/{game_id}/questions", response_model=GameQuestionsResponse)
async def get_game_questions(
    game_id: int,
    round: Optional[int] = Query(None, description="Filter by round number"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get questions for a game (optionally filtered by round)."""
    try:
        creative_service = CreativeService(db)
        questions = creative_service.get_game_questions(game_id, current_user.id, round)
        
        # Get game to extract round info
        game = creative_service.creative_repo.get_game_by_id(game_id)
        game_data = json.loads(game.game_data) if isinstance(game.game_data, str) else (game.game_data or {})
        
        return GameQuestionsResponse(
            questions=questions,
            round=round,
            total_rounds=game_data.get('rounds')
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request(str(e))

@creative_router.post("/game-sessions/{session_id}/submit-answer", response_model=AnswerResult)
async def submit_answer(
    session_id: int,
    answer_data: SubmitAnswerRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Submit an answer during active gameplay."""
    try:
        creative_service = CreativeService(db)
        result = creative_service.submit_answer(
            session_id,
            current_user.id,
            answer_data.question_id,
            answer_data.answer
        )
        
        return AnswerResult(**result)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "not active" in str(e).lower() or "not participating" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request("Failed to submit answer")

@creative_router.post("/games/generate-questions")
async def generate_ai_questions(
    request_data: GenerateQuestionsRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate trivia questions using Open Trivia Database (free API)."""
    try:
        creative_service = CreativeService(db)
        questions = await creative_service.generate_game_questions(
            topic=request_data.topic,
            difficulty=request_data.difficulty.value,
            game_type=request_data.game_type.value,
            count=request_data.count
        )
        
        return {"questions": questions, "count": len(questions)}
        
    except Exception as e:
        logger.error(f"Failed to generate questions: {str(e)}")
        raise http_400_bad_request(f"Failed to generate questions: {str(e)}")

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

# Spotify integration endpoints
class SpotifyPlaylistSync(BaseModel):
    spotify_playlist_id: str
    user_access_token: Optional[str] = None

@creative_router.post("/playlists/{playlist_id}/sync-spotify")
async def sync_spotify_playlist(
    playlist_id: int,
    sync_data: SpotifyPlaylistSync,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Import tracks from a Spotify playlist into our playlist"""
    try:
        spotify_service = SpotifyService(db)
        creative_service = CreativeService(db)
        
        # Get the Spotify playlist
        spotify_playlist = await spotify_service.get_playlist(
            sync_data.spotify_playlist_id,
            sync_data.user_access_token
        )
        
        # Get our internal playlist
        playlist = creative_service.get_playlist(playlist_id, current_user.id)
        
        # Import tracks from Spotify playlist
        imported_count = 0
        for item in spotify_playlist.get("tracks", {}).get("items", []):
            track = item.get("track")
            if not track:
                continue
            
            # Parse Spotify track data
            track_data = spotify_service.parse_spotify_track(track)
            
            # Add to our playlist
            try:
                creative_service.add_playlist_track(
                    playlist_id,
                    current_user.id,
                    track_data
                )
                imported_count += 1
            except Exception as e:
                logger.warning(f"Failed to import track {track_data.get('title')}: {str(e)}")
                continue
        
        # Update playlist to reference Spotify
        creative_service.update_playlist(
            playlist_id,
            current_user.id,
            {
                "provider": "spotify",
                "external_id": sync_data.spotify_playlist_id,
                "external_url": spotify_playlist.get("external_urls", {}).get("spotify")
            }
        )
        
        return {
            "message": "Spotify sync completed",
            "playlist_id": playlist_id,
            "spotify_playlist_id": sync_data.spotify_playlist_id,
            "imported_tracks": imported_count,
            "total_tracks": len(spotify_playlist.get("tracks", {}).get("items", [])),
            "status": "completed"
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Spotify authentication required"
            )
        raise http_400_bad_request(f"Failed to sync with Spotify: {str(e)}")

@creative_router.get("/spotify/search")
async def search_spotify_tracks(
    query: str = Query(..., description="Search query for tracks"),
    limit: int = Query(20, ge=1, le=50, description="Number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Search Spotify tracks to add to playlists"""
    try:
        spotify_service = SpotifyService(db)
        
        # Search Spotify
        results = await spotify_service.search_tracks(query, limit, offset)
        
        # Parse track data
        tracks = []
        for item in results.get("tracks", {}).get("items", []):
            parsed_track = spotify_service.parse_spotify_track(item)
            tracks.append(parsed_track)
        
        return {
            "query": query,
            "tracks": tracks,
            "total": results.get("tracks", {}).get("total", 0),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        if "not configured" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Spotify integration is not configured on the server"
            )
        raise http_400_bad_request(f"Failed to search Spotify tracks: {str(e)}")

@creative_router.get("/spotify/track/{track_id}")
async def get_spotify_track(
    track_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a Spotify track"""
    try:
        spotify_service = SpotifyService(db)
        
        # Get track from Spotify
        track = await spotify_service.get_track(track_id)
        
        # Parse track data
        parsed_track = spotify_service.parse_spotify_track(track)
        
        return parsed_track
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Track not found on Spotify")
        raise http_400_bad_request(f"Failed to get Spotify track: {str(e)}")

class SpotifyTrackAdd(BaseModel):
    spotify_track_id: str

@creative_router.post("/playlists/{playlist_id}/add-spotify-track")
async def add_spotify_track_to_playlist(
    playlist_id: int,
    track_data: SpotifyTrackAdd,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add a Spotify track to a playlist by Spotify track ID"""
    try:
        spotify_service = SpotifyService(db)
        creative_service = CreativeService(db)
        
        # Get track details from Spotify
        spotify_track = await spotify_service.get_track(track_data.spotify_track_id)
        
        # Parse into our format
        parsed_track = spotify_service.parse_spotify_track(spotify_track)
        
        # Add to our playlist
        track = creative_service.add_playlist_track(
            playlist_id,
            current_user.id,
            parsed_track
        )
        
        return PlaylistTrackResponse.model_validate(track)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        raise http_400_bad_request(f"Failed to add Spotify track: {str(e)}")