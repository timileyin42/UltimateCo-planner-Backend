from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.deps import get_db
from app.core.deps import get_current_user
from app.models.user_models import User
from app.models.notification_models import UserDevice, DevicePlatform
from app.schemas.device_schemas import (
    DeviceRegistrationRequest,
    DeviceUpdateRequest,
    DeviceResponse,
    DeviceListResponse,
    PushNotificationRequest,
    PushNotificationResponse
)
from app.services.push_service import push_service
from datetime import datetime

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/register", response_model=DeviceResponse)
async def register_device(
    device_data: DeviceRegistrationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Register a new device for push notifications."""
    try:
        # Check if device already exists for this user
        existing_device = db.query(UserDevice).filter(
            UserDevice.user_id == current_user.id,
            UserDevice.device_id == device_data.device_id
        ).first()
        
        if existing_device:
            # Update existing device
            existing_device.device_token = device_data.device_token
            existing_device.platform = device_data.platform
            existing_device.device_name = device_data.device_name
            existing_device.app_version = device_data.app_version
            existing_device.os_version = device_data.os_version
            existing_device.is_active = True
            existing_device.last_used_at = datetime.utcnow()
            existing_device.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(existing_device)
            return existing_device
        
        # Create new device
        new_device = UserDevice(
            user_id=current_user.id,
            device_token=device_data.device_token,
            device_id=device_data.device_id,
            platform=device_data.platform,
            device_name=device_data.device_name,
            app_version=device_data.app_version,
            os_version=device_data.os_version,
            is_active=True,
            last_used_at=datetime.utcnow()
        )
        
        db.add(new_device)
        db.commit()
        db.refresh(new_device)
        
        return new_device
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register device: {str(e)}"
        )


@router.get("/", response_model=DeviceListResponse)
async def get_user_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all devices for the current user."""
    devices = db.query(UserDevice).filter(
        UserDevice.user_id == current_user.id
    ).order_by(UserDevice.last_used_at.desc()).all()
    
    return DeviceListResponse(
        devices=devices,
        total=len(devices)
    )


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    device_data: DeviceUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a device."""
    device = db.query(UserDevice).filter(
        UserDevice.user_id == current_user.id,
        UserDevice.device_id == device_id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Update fields if provided
    if device_data.device_token is not None:
        device.device_token = device_data.device_token
    if device_data.device_name is not None:
        device.device_name = device_data.device_name
    if device_data.app_version is not None:
        device.app_version = device_data.app_version
    if device_data.os_version is not None:
        device.os_version = device_data.os_version
    if device_data.is_active is not None:
        device.is_active = device_data.is_active
    
    device.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(device)
    
    return device


@router.delete("/{device_id}")
async def delete_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a device."""
    device = db.query(UserDevice).filter(
        UserDevice.user_id == current_user.id,
        UserDevice.device_id == device_id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    db.delete(device)
    db.commit()
    
    return {"message": "Device deleted successfully"}


@router.post("/update-token")
async def update_device_token(
    device_id: str,
    new_token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update device token (for token refresh scenarios)."""
    device = db.query(UserDevice).filter(
        UserDevice.user_id == current_user.id,
        UserDevice.device_id == device_id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    device.device_token = new_token
    device.last_used_at = datetime.utcnow()
    device.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": "Device token updated successfully"}