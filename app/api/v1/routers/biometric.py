from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user_models import User
from app.models.biometric_models import BiometricType, DeviceType, BiometricStatus, UserDevice, BiometricAuth
from app.services.biometric_service import BiometricService
from app.schemas.biometric_schemas import (
    DeviceRegistrationRequest, DeviceResponse, DeviceListResponse, UpdateDeviceRequest,
    BiometricSetupRequest, BiometricAuthResponse, BiometricAuthListResponse,
    BiometricAuthenticationRequest, BiometricAuthenticationResponse,
    AuthChallengeResponse, BiometricTokenResponse, BiometricTokenListResponse,
    BiometricAuthAttemptResponse, AuthAttemptListResponse,
    DisableBiometricRequest, RevokeDeviceRequest,
    BiometricStatsResponse, BiometricHealthCheckResponse, BiometricConfigResponse
)

router = APIRouter()


@router.post("/devices/register", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    device_data: DeviceRegistrationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Register a new device for biometric authentication"""
    biometric_service = BiometricService(db)
    return biometric_service.register_device(current_user.id, device_data.model_dump())


@router.get("/devices", response_model=DeviceListResponse)
async def get_user_devices(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all devices registered for the current user"""
    biometric_service = BiometricService(db)
    devices = biometric_service.get_user_devices(current_user.id)
    
    # Apply pagination
    offset = (page - 1) * per_page
    paginated_devices = devices[offset:offset + per_page]
    
    return DeviceListResponse(
        devices=paginated_devices,
        total=len(devices),
        page=page,
        per_page=per_page,
        has_next=offset + per_page < len(devices),
        has_prev=page > 1
    )


@router.put("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    device_data: UpdateDeviceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update device information"""
    device = db.query(UserDevice).filter(
        and_(
            UserDevice.user_id == current_user.id,
            UserDevice.device_id == device_id
        )
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Update device fields
    update_data = device_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(device, field, value)
    
    device.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(device)
    return device


@router.post("/setup", response_model=BiometricAuthResponse, status_code=status.HTTP_201_CREATED)
async def setup_biometric_auth(
    setup_data: BiometricSetupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Setup biometric authentication for a device"""
    biometric_service = BiometricService(db)
    return biometric_service.setup_biometric_auth(
        user_id=current_user.id,
        device_id=setup_data.device_id,
        biometric_type=setup_data.biometric_type,
        public_key=setup_data.public_key,
        biometric_template_hash=setup_data.biometric_template_hash
    )


@router.get("/challenge", response_model=AuthChallengeResponse)
async def get_auth_challenge(
    db: Session = Depends(get_db)
):
    """Generate an authentication challenge for biometric login"""
    biometric_service = BiometricService(db)
    challenge = biometric_service.generate_auth_challenge()
    
    return AuthChallengeResponse(
        challenge=challenge,
        expires_at=datetime.utcnow() + timedelta(minutes=5)  # 5 minute expiry
    )


@router.post("/authenticate", response_model=BiometricAuthenticationResponse)
async def authenticate_with_biometric(
    auth_data: BiometricAuthenticationRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Authenticate user using biometric data"""
    biometric_service = BiometricService(db)
    
    # Get client info for logging
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    try:
        result = biometric_service.authenticate_with_biometric(
            device_id=auth_data.device_id,
            biometric_type=auth_data.biometric_type,
            biometric_signature=auth_data.biometric_signature,
            challenge=auth_data.challenge,
            user_identifier=auth_data.user_identifier
        )
        
        # Update device last used
        device = db.query(UserDevice).filter(
            UserDevice.device_id == auth_data.device_id
        ).first()
        if device:
            device.last_used_at = datetime.utcnow()
            db.commit()
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed due to system error"
        )


@router.get("/auths", response_model=BiometricAuthListResponse)
async def get_biometric_auths(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get biometric authentications for the current user"""
    query = db.query(BiometricAuth).filter(BiometricAuth.user_id == current_user.id)
    
    if device_id:
        query = query.filter(BiometricAuth.device_id == device_id)
    
    total = query.count()
    offset = (page - 1) * per_page
    auths = query.offset(offset).limit(per_page).all()
    
    return BiometricAuthListResponse(
        biometric_auths=auths,
        total=total,
        page=page,
        per_page=per_page,
        has_next=offset + per_page < total,
        has_prev=page > 1
    )


@router.get("/attempts", response_model=AuthAttemptListResponse)
async def get_auth_attempts(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get authentication attempts for the current user"""
    biometric_service = BiometricService(db)
    offset = (page - 1) * per_page
    
    attempts = biometric_service.get_auth_attempts(
        user_id=current_user.id,
        device_id=device_id,
        limit=per_page
    )
    
    # Apply offset manually since service doesn't support it
    paginated_attempts = attempts[offset:offset + per_page]
    
    return AuthAttemptListResponse(
        attempts=paginated_attempts,
        total=len(attempts),
        page=page,
        per_page=per_page,
        has_next=offset + per_page < len(attempts),
        has_prev=page > 1
    )


@router.get("/tokens", response_model=BiometricTokenListResponse)
async def get_biometric_tokens(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    active_only: bool = Query(True, description="Show only active tokens"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get biometric tokens for the current user"""
    from app.models.biometric_models import BiometricToken
    from sqlalchemy import and_, desc
    
    query = db.query(BiometricToken).filter(BiometricToken.user_id == current_user.id)
    
    if device_id:
        query = query.filter(BiometricToken.device_id == device_id)
    
    if active_only:
        query = query.filter(BiometricToken.is_active == True)
    
    total = query.count()
    offset = (page - 1) * per_page
    tokens = query.order_by(desc(BiometricToken.created_at)).offset(offset).limit(per_page).all()
    
    return BiometricTokenListResponse(
        tokens=tokens,
        total=total,
        page=page,
        per_page=per_page,
        has_next=offset + per_page < total,
        has_prev=page > 1
    )


@router.post("/disable", status_code=status.HTTP_200_OK)
async def disable_biometric_auth(
    disable_data: DisableBiometricRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disable biometric authentication for a device or specific type"""
    biometric_service = BiometricService(db)
    success = biometric_service.disable_biometric_auth(
        user_id=current_user.id,
        device_id=disable_data.device_id,
        biometric_type=disable_data.biometric_type
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No biometric authentication found to disable"
        )
    
    return {"message": "Biometric authentication disabled successfully"}


@router.post("/revoke-device", status_code=status.HTTP_200_OK)
async def revoke_device(
    revoke_data: RevokeDeviceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke all access for a device"""
    biometric_service = BiometricService(db)
    success = biometric_service.revoke_device(
        user_id=current_user.id,
        device_id=revoke_data.device_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    return {"message": "Device access revoked successfully"}


@router.get("/stats", response_model=BiometricStatsResponse)
async def get_biometric_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get biometric authentication statistics for the current user"""
    from app.models.biometric_models import UserDevice, BiometricAuth, BiometricAuthAttempt
    from sqlalchemy import and_, func
    
    # Get device stats
    total_devices = db.query(UserDevice).filter(UserDevice.user_id == current_user.id).count()
    active_devices = db.query(UserDevice).filter(
        and_(UserDevice.user_id == current_user.id, UserDevice.is_active == True)
    ).count()
    
    # Get biometric auth stats
    total_biometric_auths = db.query(BiometricAuth).filter(
        BiometricAuth.user_id == current_user.id
    ).count()
    active_biometric_auths = db.query(BiometricAuth).filter(
        and_(
            BiometricAuth.user_id == current_user.id,
            BiometricAuth.status == BiometricStatus.ACTIVE
        )
    ).count()
    
    # Get attempt stats for today
    today = datetime.utcnow().date()
    successful_attempts_today = db.query(BiometricAuthAttempt).filter(
        and_(
            BiometricAuthAttempt.user_id == current_user.id,
            BiometricAuthAttempt.success == True,
            func.date(BiometricAuthAttempt.attempted_at) == today
        )
    ).count()
    
    failed_attempts_today = db.query(BiometricAuthAttempt).filter(
        and_(
            BiometricAuthAttempt.user_id == current_user.id,
            BiometricAuthAttempt.success == False,
            func.date(BiometricAuthAttempt.attempted_at) == today
        )
    ).count()
    
    # Get last successful login
    last_successful = db.query(BiometricAuthAttempt).filter(
        and_(
            BiometricAuthAttempt.user_id == current_user.id,
            BiometricAuthAttempt.success == True
        )
    ).order_by(BiometricAuthAttempt.attempted_at.desc()).first()
    
    return BiometricStatsResponse(
        total_devices=total_devices,
        active_devices=active_devices,
        total_biometric_auths=total_biometric_auths,
        active_biometric_auths=active_biometric_auths,
        successful_attempts_today=successful_attempts_today,
        failed_attempts_today=failed_attempts_today,
        last_successful_login=last_successful.attempted_at if last_successful else None
    )


@router.get("/health/{device_id}", response_model=List[BiometricHealthCheckResponse])
async def check_biometric_health(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check the health status of biometric authentication for a device"""
    biometric_service = BiometricService(db)
    auths = biometric_service.get_device_biometric_auths(current_user.id, device_id)
    
    health_checks = []
    for auth in auths:
        issues = []
        
        # Check if auth is active
        if auth.status != BiometricStatus.ACTIVE:
            issues.append(f"Authentication is {auth.status.value}")
        
        # Check if recently used (within 30 days)
        if auth.last_used_at:
            days_since_use = (datetime.utcnow() - auth.last_used_at).days
            if days_since_use > 30:
                issues.append(f"Not used for {days_since_use} days")
        else:
            issues.append("Never used")
        
        health_checks.append(BiometricHealthCheckResponse(
            device_id=device_id,
            biometric_type=auth.biometric_type,
            status=auth.status,
            last_used=auth.last_used_at,
            is_healthy=len(issues) == 0,
            issues=issues
        ))
    
    return health_checks


@router.get("/config", response_model=BiometricConfigResponse)
async def get_biometric_config():
    """Get biometric authentication configuration"""
    return BiometricConfigResponse(
        supported_types=[BiometricType.FACE_ID, BiometricType.FINGERPRINT, BiometricType.VOICE],
        max_devices_per_user=10,
        token_expiry_hours=24,
        challenge_expiry_minutes=5,
        max_failed_attempts=5,
        lockout_duration_minutes=30
    )


@router.post("/cleanup-tokens", status_code=status.HTTP_200_OK)
async def cleanup_expired_tokens(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clean up expired biometric tokens (admin endpoint)"""
    biometric_service = BiometricService(db)
    cleaned_count = biometric_service.cleanup_expired_tokens()
    
    return {"message": f"Cleaned up {cleaned_count} expired tokens"}