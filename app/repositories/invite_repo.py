from datetime import datetime
from typing import List, Optional, Union
import secrets
import string
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from app.models.invite_models import InviteCode, InviteLink, InviteLinkUsage, InviteType
from app.models.user_models import User


class InviteRepository:
    """Repository for invite-related database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Internal helpers
    def _generate_unique_code(self, length: int = 8) -> str:
        """Generate a unique invite code consisting of uppercase letters and digits."""
        alphabet = string.ascii_uppercase + string.digits
        while True:
            candidate = ''.join(secrets.choice(alphabet) for _ in range(length))
            if not self.db.query(InviteCode).filter(InviteCode.code == candidate).first():
                return candidate

    def _generate_unique_link_id(self, length: int = 12) -> str:
        """Generate a unique, URL-safe invite link identifier."""
        alphabet = string.ascii_lowercase + string.digits
        while True:
            candidate = ''.join(secrets.choice(alphabet) for _ in range(length))
            if not self.db.query(InviteLink).filter(InviteLink.link_id == candidate).first():
                return candidate

    @staticmethod
    def _normalize_invite_type(invite_type: Optional[Union[InviteType, str]]) -> str:
        """Ensure invite type is stored as the expected string value."""
        if isinstance(invite_type, InviteType):
            return invite_type.value
        return invite_type or InviteType.APP_GENERAL.value

    # Invite Code operations
    def create_invite_code(self, user_id: int, invite_type: InviteType = InviteType.APP_GENERAL, 
                          expires_at: Optional[datetime] = None) -> InviteCode:
        """Create a new invite code"""
        invite_code = InviteCode(
            code=self._generate_unique_code(),
            user_id=user_id,
            invite_type=self._normalize_invite_type(invite_type),
            expires_at=expires_at
        )
        self.db.add(invite_code)
        self.db.commit()
        self.db.refresh(invite_code)
        return invite_code
    
    def get_invite_code_by_code(self, code: str) -> Optional[InviteCode]:
        """Get invite code by code string"""
        return self.db.query(InviteCode).filter(InviteCode.code == code).first()
    
    def get_invite_code_by_id(self, invite_id: int) -> Optional[InviteCode]:
        """Get invite code by ID"""
        return self.db.query(InviteCode).filter(InviteCode.id == invite_id).first()
    
    def get_user_invite_codes(self, user_id: int, active_only: bool = False) -> List[InviteCode]:
        """Get all invite codes created by a user"""
        query = self.db.query(InviteCode).filter(InviteCode.user_id == user_id)
        if active_only:
            query = query.filter(
                and_(
                    InviteCode.is_active == True,
                    InviteCode.used_at.is_(None),
                    or_(
                        InviteCode.expires_at.is_(None),
                        InviteCode.expires_at > datetime.utcnow()
                    )
                )
            )
        return query.order_by(InviteCode.created_at.desc()).all()
    
    def use_invite_code(self, code: str, used_by_user_id: int) -> Optional[InviteCode]:
        """Mark an invite code as used"""
        invite_code = self.get_invite_code_by_code(code)
        if invite_code and invite_code.can_be_used():
            invite_code.used_at = datetime.utcnow()
            invite_code.used_by_user_id = used_by_user_id
            self.db.commit()
            self.db.refresh(invite_code)
            return invite_code
        return None
    
    def deactivate_invite_code(self, invite_id: int, user_id: int) -> bool:
        """Deactivate an invite code (only by creator)"""
        invite_code = self.db.query(InviteCode).filter(
            and_(
                InviteCode.id == invite_id,
                InviteCode.user_id == user_id
            )
        ).first()
        
        if invite_code:
            invite_code.is_active = False
            self.db.commit()
            return True
        return False
    
    # Invite Link operations
    def create_invite_link(self, user_id: int, title: str, description: Optional[str] = None,
                          expires_at: Optional[datetime] = None, max_uses: Optional[int] = None) -> InviteLink:
        """Create a new invite link"""
        invite_link = InviteLink(
            link_id=self._generate_unique_link_id(),
            user_id=user_id,
            title=title,
            description=description,
            expires_at=expires_at,
            max_uses=max_uses,
            invite_type=InviteType.APP_GENERAL.value,
            current_uses=0
        )
        self.db.add(invite_link)
        self.db.commit()
        self.db.refresh(invite_link)
        return invite_link
    
    def get_invite_link_by_link_id(self, link_id: str) -> Optional[InviteLink]:
        """Get invite link by link_id string"""
        return self.db.query(InviteLink).filter(InviteLink.link_id == link_id).first()
    
    def get_invite_link_by_id(self, invite_id: int) -> Optional[InviteLink]:
        """Get invite link by ID"""
        return self.db.query(InviteLink).filter(InviteLink.id == invite_id).first()
    
    def get_user_invite_links(self, user_id: int, active_only: bool = False) -> List[InviteLink]:
        """Get all invite links created by a user"""
        query = self.db.query(InviteLink).filter(InviteLink.user_id == user_id)
        if active_only:
            query = query.filter(
                and_(
                    InviteLink.is_active == True,
                    or_(
                        InviteLink.expires_at.is_(None),
                        InviteLink.expires_at > datetime.utcnow()
                    ),
                    or_(
                        InviteLink.max_uses.is_(None),
                        InviteLink.current_uses < InviteLink.max_uses
                    )
                )
            )
        return query.order_by(InviteLink.created_at.desc()).all()
    
    def use_invite_link(self, link_id: str, used_by_user_id: Optional[int] = None,
                       ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> Optional[InviteLink]:
        """Record usage of an invite link"""
        invite_link = self.get_invite_link_by_link_id(link_id)
        if invite_link and invite_link.can_be_used():
            # Create usage record
            usage = InviteLinkUsage(
                invite_link_id=invite_link.id,
                used_by_user_id=used_by_user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            self.db.add(usage)
            
            # Increment usage count
            invite_link.current_uses += 1
            self.db.commit()
            self.db.refresh(invite_link)
            return invite_link
        return None
    
    def deactivate_invite_link(self, invite_id: int, user_id: int) -> bool:
        """Deactivate an invite link (only by creator)"""
        invite_link = self.db.query(InviteLink).filter(
            and_(
                InviteLink.id == invite_id,
                InviteLink.user_id == user_id
            )
        ).first()
        
        if invite_link:
            invite_link.is_active = False
            self.db.commit()
            return True
        return False
    
    def get_invite_link_usages(self, invite_link_id: int, user_id: int) -> List[InviteLinkUsage]:
        """Get usage history for an invite link (only by creator)"""
        invite_link = self.db.query(InviteLink).filter(
            and_(
                InviteLink.id == invite_link_id,
                InviteLink.user_id == user_id
            )
        ).first()
        
        if invite_link:
            return self.db.query(InviteLinkUsage).filter(
                InviteLinkUsage.invite_link_id == invite_link_id
            ).order_by(InviteLinkUsage.used_at.desc()).all()
        return []
    
    # Statistics
    def get_user_invite_stats(self, user_id: int) -> dict:
        """Get invite statistics for a user"""
        # Invite codes stats
        total_codes = self.db.query(func.count(InviteCode.id)).filter(
            InviteCode.user_id == user_id
        ).scalar() or 0
        
        active_codes = self.db.query(func.count(InviteCode.id)).filter(
            and_(
                InviteCode.user_id == user_id,
                InviteCode.is_active == True,
                InviteCode.used_at.is_(None),
                or_(
                    InviteCode.expires_at.is_(None),
                    InviteCode.expires_at > datetime.utcnow()
                )
            )
        ).scalar() or 0
        
        used_codes = self.db.query(func.count(InviteCode.id)).filter(
            and_(
                InviteCode.user_id == user_id,
                InviteCode.used_at.isnot(None)
            )
        ).scalar() or 0
        
        # Invite links stats
        total_links = self.db.query(func.count(InviteLink.id)).filter(
            InviteLink.user_id == user_id
        ).scalar() or 0
        
        active_links = self.db.query(func.count(InviteLink.id)).filter(
            and_(
                InviteLink.user_id == user_id,
                InviteLink.is_active == True,
                or_(
                    InviteLink.expires_at.is_(None),
                    InviteLink.expires_at > datetime.utcnow()
                ),
                or_(
                    InviteLink.max_uses.is_(None),
                    InviteLink.current_uses < InviteLink.max_uses
                )
            )
        ).scalar() or 0
        
        total_link_uses = self.db.query(func.sum(InviteLink.current_uses)).filter(
            InviteLink.user_id == user_id
        ).scalar() or 0
        
        return {
            "total_invite_codes": total_codes,
            "active_invite_codes": active_codes,
            "used_invite_codes": used_codes,
            "total_invite_links": total_links,
            "active_invite_links": active_links,
            "total_link_uses": total_link_uses
        }