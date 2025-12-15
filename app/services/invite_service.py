import os
import io
import base64
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
try:
    from qrcode.image.styles.colorfills import SquareGradiantColorFill  # type: ignore
    HAS_GRADIENT = True
except ImportError:
    # Fallback for older qrcode versions
    SquareGradiantColorFill = None  # type: ignore
    HAS_GRADIENT = False
from PIL import Image

from app.repositories.invite_repo import InviteRepository
from app.models.invite_models import InviteCode, InviteLink, InviteType
from app.schemas.invite import (
    InviteCodeCreate, InviteCodeResponse,
    InviteLinkCreate, InviteLinkResponse,
    QRCodeRequest, QRCodeResponse,
    InviteStatsResponse, ProcessInviteResponse
)
from app.core.config import settings
from app.services.gcp_storage_service import GCPStorageService


class InviteService:
    """Service for managing invites and QR code generation"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repo = InviteRepository(db)
        self.storage_service = GCPStorageService()
        
        # For local/development fallback only
        self.qr_code_base_path = "static/qr_codes"
        if settings.ENVIRONMENT == "development":
            os.makedirs(self.qr_code_base_path, exist_ok=True)
    
    async def generate_qr_code(self, data: str, size: int = 200, 
                        style: str = "default", user_id: Optional[int] = None) -> Tuple[str, str]:
        """Generate QR code and upload to GCS, return URL and base64 data"""
        try:
            # Create QR code instance
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            # Generate styled QR code
            if style == "gradient" and HAS_GRADIENT:
                img = qr.make_image(
                    image_factory=StyledPilImage,
                    module_drawer=RoundedModuleDrawer(),
                    color_mask=SquareGradiantColorFill(
                        back_color=(255, 255, 255),
                        center_color=(255, 100, 100),
                        edge_color=(255, 200, 0)
                    )
                )
            elif style == "rounded":
                img = qr.make_image(
                    image_factory=StyledPilImage,
                    module_drawer=RoundedModuleDrawer()
                )
            else:
                img = qr.make_image(fill_color="black", back_color="white")
            
            # Resize image
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            
            # Convert to bytes
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_bytes = buffer.getvalue()
            img_base64 = base64.b64encode(img_bytes).decode()
            
            # Generate filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"qr_{timestamp}_{hash(data) % 10000}.png"
            
            # Upload to GCS (or local storage in development)
            if self.storage_service.client and self.storage_service.bucket:
                # Production: Upload to GCS as PUBLIC (QR codes are meant to be shared)
                upload_result = await self.storage_service.upload_file(
                    file_content=img_bytes,
                    filename=filename,
                    content_type="image/png",
                    folder="qr_codes",
                    user_id=user_id,
                    make_public=True  # QR codes can be public
                )
                file_url = upload_result["file_url"]
            else:
                # Development: Save locally
                file_path = os.path.join(self.qr_code_base_path, filename)
                img.save(file_path)
                file_url = f"/static/qr_codes/{filename}"
            
            return file_url, img_base64
            
        except Exception as e:
            raise Exception(f"Failed to generate QR code: {str(e)}")
    
    async def create_invite_code(self, user_id: int, invite_data: InviteCodeCreate) -> InviteCodeResponse:
        """Create a new invite code with QR code"""
        try:
            # Create invite code
            invite_code = self.repo.create_invite_code(
                user_id=user_id,
                invite_type=invite_data.invite_type,
                expires_at=invite_data.expires_at
            )
            
            # Generate QR code for the invite
            invite_url = f"{settings.FRONTEND_URL}/invite/{invite_code.code}"
            qr_code_path, _ = await self.generate_qr_code(invite_url, style="gradient", user_id=user_id)
            
            # Update invite code with QR code URL
            invite_code.qr_code_url = qr_code_path
            self.db.commit()
            self.db.refresh(invite_code)
            
            return InviteCodeResponse.model_validate(invite_code)
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to create invite code: {str(e)}")
    
    async def create_invite_link(self, user_id: int, invite_data: InviteLinkCreate) -> InviteLinkResponse:
        """Create a new invite link with QR code"""
        try:
            # Create invite link
            invite_link = self.repo.create_invite_link(
                user_id=user_id,
                title=invite_data.title,
                description=invite_data.description,
                expires_at=invite_data.expires_at,
                max_uses=invite_data.max_uses
            )
            
            # Generate QR code for the invite link
            invite_url = f"{settings.FRONTEND_URL}/invite/{invite_link.link_id}"
            qr_code_path, _ = await self.generate_qr_code(invite_url, style="gradient", user_id=user_id)
            
            # Update invite link with QR code URL
            invite_link.qr_code_url = qr_code_path
            self.db.commit()
            self.db.refresh(invite_link)
            
            return InviteLinkResponse.model_validate(invite_link)
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to create invite link: {str(e)}")
    
    async def generate_custom_qr_code(self, qr_request: QRCodeRequest, user_id: Optional[int] = None) -> QRCodeResponse:
        """Generate a custom QR code for any data"""
        try:
            qr_code_path, qr_base64 = await self.generate_qr_code(
                qr_request.data, 
                qr_request.size,
                user_id=user_id
            )
            
            return QRCodeResponse(
                qr_code_url=qr_code_path,
                data=qr_request.data
            )
            
        except Exception as e:
            raise Exception(f"Failed to generate custom QR code: {str(e)}")
    
    def process_invite_code(self, code: str, user_id: Optional[int] = None) -> ProcessInviteResponse:
        """Process an invite code"""
        try:
            invite_code = self.repo.get_invite_code_by_code(code)
            
            if not invite_code:
                return ProcessInviteResponse(
                    success=False,
                    message="Invalid invite code"
                )
            
            if not invite_code.can_be_used():
                return ProcessInviteResponse(
                    success=False,
                    message="Invite code is expired or already used"
                )
            
            # Mark as used if user_id provided
            if user_id:
                used_invite = self.repo.use_invite_code(code, user_id)
                if not used_invite:
                    return ProcessInviteResponse(
                        success=False,
                        message="Failed to process invite code"
                    )
            
            return ProcessInviteResponse(
                success=True,
                message="Invite code processed successfully",
                invite_type=invite_code.invite_type,
                creator_id=invite_code.user_id
            )
            
        except Exception as e:
            return ProcessInviteResponse(
                success=False,
                message=f"Error processing invite code: {str(e)}"
            )
    
    def process_invite_link(self, link_id: str, user_id: Optional[int] = None,
                           ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> ProcessInviteResponse:
        """Process an invite link"""
        try:
            invite_link = self.repo.get_invite_link_by_link_id(link_id)
            
            if not invite_link:
                return ProcessInviteResponse(
                    success=False,
                    message="Invalid invite link"
                )
            
            if not invite_link.can_be_used():
                return ProcessInviteResponse(
                    success=False,
                    message="Invite link is expired or has reached maximum uses"
                )
            
            # Record usage
            used_invite = self.repo.use_invite_link(
                link_id, user_id, ip_address, user_agent
            )
            
            if not used_invite:
                return ProcessInviteResponse(
                    success=False,
                    message="Failed to process invite link"
                )
            
            return ProcessInviteResponse(
                success=True,
                message="Invite link processed successfully",
                creator_id=invite_link.user_id
            )
            
        except Exception as e:
            return ProcessInviteResponse(
                success=False,
                message=f"Error processing invite link: {str(e)}"
            )
    
    def get_user_invite_codes(self, user_id: int, active_only: bool = False) -> List[InviteCodeResponse]:
        """Get all invite codes for a user"""
        invite_codes = self.repo.get_user_invite_codes(user_id, active_only)
        return [InviteCodeResponse.model_validate(code) for code in invite_codes]
    
    def get_user_invite_links(self, user_id: int, active_only: bool = False) -> List[InviteLinkResponse]:
        """Get all invite links for a user"""
        invite_links = self.repo.get_user_invite_links(user_id, active_only)
        return [InviteLinkResponse.model_validate(link) for link in invite_links]
    
    def get_invite_stats(self, user_id: int) -> InviteStatsResponse:
        """Get invite statistics for a user"""
        stats = self.repo.get_user_invite_stats(user_id)
        return InviteStatsResponse(**stats)
    
    def deactivate_invite_code(self, invite_id: int, user_id: int) -> bool:
        """Deactivate an invite code"""
        return self.repo.deactivate_invite_code(invite_id, user_id)
    
    def deactivate_invite_link(self, invite_id: int, user_id: int) -> bool:
        """Deactivate an invite link"""
        return self.repo.deactivate_invite_link(invite_id, user_id)
    
    async def generate_user_profile_qr(self, user_id: int) -> QRCodeResponse:
        """Generate QR code for user profile sharing"""
        try:
            profile_url = f"{settings.FRONTEND_URL}/profile/{user_id}"
            qr_code_path, _ = await self.generate_qr_code(profile_url, style="gradient", user_id=user_id)
            
            return QRCodeResponse(
                qr_code_url=qr_code_path,
                data=profile_url
            )
            
        except Exception as e:
            raise Exception(f"Failed to generate profile QR code: {str(e)}")
    
    async def generate_app_invite_qr(self) -> QRCodeResponse:
        """Generate QR code for general app invitation"""
        try:
            app_url = settings.FRONTEND_URL
            qr_code_path, _ = await self.generate_qr_code(app_url, style="gradient")
            
            return QRCodeResponse(
                qr_code_url=qr_code_path,
                data=app_url
            )
            
        except Exception as e:
            raise Exception(f"Failed to generate app invite QR code: {str(e)}")
    
    async def delete_invite_code_with_qr(self, invite_id: int, user_id: int) -> bool:
        """Delete an invite code and its QR code from both database and GCP bucket"""
        try:
            # Get the invite code
            invite_code = self.repo.get_invite_code_by_id(invite_id)
            
            if not invite_code or invite_code.user_id != user_id:
                return False
            
            # Delete QR code from GCP bucket if it exists
            if invite_code.qr_code_url:
                qr_url = invite_code.qr_code_url
                
                # Extract blob path from URL or use the stored path directly
                if qr_url.startswith("https://storage.googleapis.com/"):
                    # Format: https://storage.googleapis.com/bucket_name/qr_codes/user_123/filename.png
                    blob_path = "/".join(qr_url.split("/")[4:])
                else:
                    # It's already a blob path
                    blob_path = qr_url
                
                # Delete from GCP bucket
                await self.storage_service.delete_file(blob_path)
            
            # Delete from database (soft delete)
            invite_code.is_deleted = True
            self.db.commit()
            
            return True
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to delete invite code with QR: {str(e)}")
    
    async def delete_invite_link_with_qr(self, invite_id: int, user_id: int) -> bool:
        """Delete an invite link and its QR code from both database and GCP bucket"""
        try:
            # Get the invite link
            invite_link = self.repo.get_invite_link_by_id(invite_id)
            
            if not invite_link or invite_link.user_id != user_id:
                return False
            
            # Delete QR code from GCP bucket if it exists
            if invite_link.qr_code_url:
                qr_url = invite_link.qr_code_url
                
                # Extract blob path from URL or use the stored path directly
                if qr_url.startswith("https://storage.googleapis.com/"):
                    blob_path = "/".join(qr_url.split("/")[4:])
                else:
                    blob_path = qr_url
                
                # Delete from GCP bucket
                await self.storage_service.delete_file(blob_path)
            
            # Delete from database (soft delete)
            invite_link.is_deleted = True
            self.db.commit()
            
            return True
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to delete invite link with QR: {str(e)}")