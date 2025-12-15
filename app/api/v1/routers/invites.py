from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user_models import User
from app.services.invite_service import InviteService
from app.schemas.invite import (
    InviteCodeCreate, InviteCodeResponse,
    InviteLinkCreate, InviteLinkResponse,
    QRCodeRequest, QRCodeResponse,
    InviteStatsResponse, ProcessInviteRequest, ProcessInviteResponse
)

router = APIRouter(prefix="/invites", tags=["invites"])


def get_invite_service(db: Session = Depends(get_db)) -> InviteService:
    """Dependency to get invite service"""
    return InviteService(db)


@router.post("/codes", response_model=InviteCodeResponse)
async def create_invite_code(
    invite_data: InviteCodeCreate,
    current_user: User = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service)
):
    """Create a new invite code with QR code"""
    try:
        return await invite_service.create_invite_code(current_user.id, invite_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/links", response_model=InviteLinkResponse)
async def create_invite_link(
    invite_data: InviteLinkCreate,
    current_user: User = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service)
):
    """Create a new invite link with QR code"""
    try:
        return await invite_service.create_invite_link(current_user.id, invite_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/qr-code", response_model=QRCodeResponse)
async def generate_qr_code(
    qr_request: QRCodeRequest,
    current_user: User = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service)
):
    """Generate a custom QR code"""
    try:
        return await invite_service.generate_custom_qr_code(qr_request, user_id=current_user.id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/qr-code/profile", response_model=QRCodeResponse)
async def generate_profile_qr_code(
    current_user: User = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service)
):
    """Generate QR code for user profile sharing"""
    try:
        return await invite_service.generate_user_profile_qr(current_user.id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/qr-code/app", response_model=QRCodeResponse)
async def generate_app_qr_code(
    invite_service: InviteService = Depends(get_invite_service)
):
    """Generate QR code for general app invitation (public endpoint)"""
    try:
        return await invite_service.generate_app_invite_qr()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/process", response_model=ProcessInviteResponse)
async def process_invite(
    process_request: ProcessInviteRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service)
):
    """Process an invite code or link"""
    try:
        user_id = current_user.id if current_user else None
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        if process_request.invite_code:
            return invite_service.process_invite_code(
                process_request.invite_code, user_id
            )
        elif process_request.invite_link_id:
            return invite_service.process_invite_link(
                process_request.invite_link_id, user_id, ip_address, user_agent
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either invite_code or invite_link_id must be provided"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/codes", response_model=List[InviteCodeResponse])
async def get_my_invite_codes(
    active_only: bool = False,
    current_user: User = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service)
):
    """Get current user's invite codes"""
    return invite_service.get_user_invite_codes(current_user.id, active_only)


@router.get("/links", response_model=List[InviteLinkResponse])
async def get_my_invite_links(
    active_only: bool = False,
    current_user: User = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service)
):
    """Get current user's invite links"""
    return invite_service.get_user_invite_links(current_user.id, active_only)


@router.get("/stats", response_model=InviteStatsResponse)
async def get_invite_stats(
    current_user: User = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service)
):
    """Get invite statistics for current user"""
    return invite_service.get_invite_stats(current_user.id)


@router.delete("/codes/{invite_id}")
async def deactivate_invite_code(
    invite_id: int,
    current_user: User = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service)
):
    """Deactivate an invite code"""
    success = invite_service.deactivate_invite_code(invite_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite code not found or not owned by user"
        )
    return {"message": "Invite code deactivated successfully"}


@router.delete("/codes/{invite_id}/with-qr")
async def delete_invite_code_with_qr(
    invite_id: int,
    current_user: User = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service)
):
    """Delete an invite code and its QR code from database and GCP bucket"""
    try:
        success = await invite_service.delete_invite_code_with_qr(invite_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite code not found or not owned by user"
            )
        return {"message": "Invite code and QR code deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/links/{invite_id}")
async def deactivate_invite_link(
    invite_id: int,
    current_user: User = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service)
):
    """Deactivate an invite link"""
    success = invite_service.deactivate_invite_link(invite_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite link not found or not owned by user"
        )
    return {"message": "Invite link deactivated successfully"}


@router.delete("/links/{invite_id}/with-qr")
async def delete_invite_link_with_qr(
    invite_id: int,
    current_user: User = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service)
):
    """Delete an invite link and its QR code from database and GCP bucket"""
    try:
        success = await invite_service.delete_invite_link_with_qr(invite_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite link not found or not owned by user"
            )
        return {"message": "Invite link and QR code deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Public endpoints for processing invites (no authentication required)
@router.get("/public/code/{code}", response_model=ProcessInviteResponse)
async def process_public_invite_code(
    code: str,
    invite_service: InviteService = Depends(get_invite_service)
):
    """Process an invite code (public endpoint for validation)"""
    try:
        return invite_service.process_invite_code(code)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/public/link/{link_id}", response_model=ProcessInviteResponse)
async def process_public_invite_link(
    link_id: str,
    request: Request,
    invite_service: InviteService = Depends(get_invite_service)
):
    """Process an invite link (public endpoint)"""
    try:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        return invite_service.process_invite_link(
            link_id, None, ip_address, user_agent
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )