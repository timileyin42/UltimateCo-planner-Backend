from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from datetime import datetime, timedelta
import uuid
import hashlib
import secrets
import base64
import json
from fastapi import HTTPException, status
import logging
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.exceptions import InvalidSignature

from app.models.biometric_models import (
    UserDevice, BiometricAuth, BiometricAuthAttempt, BiometricToken,
    BiometricType, DeviceType, BiometricStatus
)
from app.models.user_models import User
from app.core.security import create_access_token, verify_password

logger = logging.getLogger(__name__)


class BiometricService:
    def __init__(self, db: Session):
        self.db = db

    def register_device(
        self, 
        user_id: int, 
        device_data: Dict[str, Any]
    ) -> UserDevice:
        """Register a new device for biometric authentication"""
        # Check if device already exists
        existing_device = self.db.query(UserDevice).filter(
            and_(
                UserDevice.user_id == user_id,
                UserDevice.device_id == device_data.get('device_id')
            )
        ).first()
        
        if existing_device:
            # Update existing device
            existing_device.device_name = device_data.get('device_name', existing_device.device_name)
            existing_device.device_type = DeviceType(device_data.get('device_type', existing_device.device_type.value))
            existing_device.os_version = device_data.get('os_version', existing_device.os_version)
            existing_device.app_version = device_data.get('app_version', existing_device.app_version)
            existing_device.is_active = True
            existing_device.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(existing_device)
            return existing_device
        
        # Create new device
        device = UserDevice(
            user_id=user_id,
            device_id=device_data['device_id'],
            device_name=device_data.get('device_name', 'Unknown Device'),
            device_type=DeviceType(device_data.get('device_type', 'mobile')),
            os_version=device_data.get('os_version'),
            app_version=device_data.get('app_version'),
            is_active=True
        )
        
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def setup_biometric_auth(
        self, 
        user_id: int, 
        device_id: str,
        biometric_type: BiometricType,
        public_key: str,
        biometric_template_hash: Optional[str] = None
    ) -> BiometricAuth:
        """Setup biometric authentication for a device"""
        # Verify device belongs to user
        device = self.db.query(UserDevice).filter(
            and_(
                UserDevice.user_id == user_id,
                UserDevice.device_id == device_id,
                UserDevice.is_active == True
            )
        ).first()
        
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found or inactive"
            )
        
        # Check if biometric auth already exists for this device and type
        existing_auth = self.db.query(BiometricAuth).filter(
            and_(
                BiometricAuth.user_id == user_id,
                BiometricAuth.device_id == device_id,
                BiometricAuth.biometric_type == biometric_type
            )
        ).first()
        
        if existing_auth:
            # Update existing auth
            existing_auth.public_key = public_key
            existing_auth.biometric_template_hash = biometric_template_hash
            existing_auth.status = BiometricStatus.ACTIVE
            existing_auth.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(existing_auth)
            return existing_auth
        
        # Create new biometric auth
        biometric_auth = BiometricAuth(
            user_id=user_id,
            device_id=device_id,
            biometric_type=biometric_type,
            public_key=public_key,
            biometric_template_hash=biometric_template_hash,
            status=BiometricStatus.ACTIVE
        )
        
        self.db.add(biometric_auth)
        self.db.commit()
        self.db.refresh(biometric_auth)
        return biometric_auth

    def authenticate_with_biometric(
        self, 
        device_id: str,
        biometric_type: BiometricType,
        biometric_signature: str,
        challenge: str,
        user_identifier: Optional[str] = None  # email or username
    ) -> Dict[str, Any]:
        """Authenticate user using biometric data"""
        try:
            # Find biometric auth record
            query = self.db.query(BiometricAuth).filter(
                and_(
                    BiometricAuth.device_id == device_id,
                    BiometricAuth.biometric_type == biometric_type,
                    BiometricAuth.status == BiometricStatus.ACTIVE
                )
            )
            
            # If user identifier provided, filter by user
            if user_identifier:
                user = self.db.query(User).filter(
                    or_(User.email == user_identifier, User.username == user_identifier)
                ).first()
                if user:
                    query = query.filter(BiometricAuth.user_id == user.id)
            
            biometric_auth = query.first()
            
            if not biometric_auth:
                self._log_auth_attempt(
                    device_id=device_id,
                    biometric_type=biometric_type,
                    success=False,
                    failure_reason="Biometric authentication not found"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Biometric authentication not configured"
                )
            
            # Verify signature (simplified - in production, use proper cryptographic verification)
            if not self._verify_biometric_signature(
                biometric_auth.public_key, 
                biometric_signature, 
                challenge
            ):
                self._log_auth_attempt(
                    user_id=biometric_auth.user_id,
                    device_id=device_id,
                    biometric_type=biometric_type,
                    success=False,
                    failure_reason="Invalid biometric signature"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Biometric authentication failed"
                )
            
            # Get user
            user = self.db.query(User).filter(User.id == biometric_auth.user_id).first()
            if not user or not user.is_active:
                self._log_auth_attempt(
                    user_id=biometric_auth.user_id,
                    device_id=device_id,
                    biometric_type=biometric_type,
                    success=False,
                    failure_reason="User not found or inactive"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User account not found or inactive"
                )
            
            # Create biometric token
            biometric_token = self._create_biometric_token(
                user_id=user.id,
                device_id=device_id,
                biometric_type=biometric_type
            )
            
            # Create access token
            access_token = create_access_token(data={"sub": str(user.id)})
            
            # Log successful attempt
            self._log_auth_attempt(
                user_id=user.id,
                device_id=device_id,
                biometric_type=biometric_type,
                success=True
            )
            
            # Update last login
            user.last_login = datetime.utcnow()
            self.db.commit()
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "biometric_token": biometric_token.token,
                "expires_in": 3600,  # 1 hour
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name
                }
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Biometric authentication error: {str(e)}")
            self._log_auth_attempt(
                device_id=device_id,
                biometric_type=biometric_type,
                success=False,
                failure_reason=f"System error: {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication system error"
            )

    def get_user_devices(self, user_id: int) -> List[UserDevice]:
        """Get all devices registered for a user"""
        return self.db.query(UserDevice).filter(
            UserDevice.user_id == user_id
        ).order_by(desc(UserDevice.last_used_at)).all()

    def get_device_biometric_auths(self, user_id: int, device_id: str) -> List[BiometricAuth]:
        """Get all biometric authentications for a device"""
        return self.db.query(BiometricAuth).filter(
            and_(
                BiometricAuth.user_id == user_id,
                BiometricAuth.device_id == device_id
            )
        ).all()

    def disable_biometric_auth(
        self, 
        user_id: int, 
        device_id: str, 
        biometric_type: Optional[BiometricType] = None
    ) -> bool:
        """Disable biometric authentication for a device or specific type"""
        query = self.db.query(BiometricAuth).filter(
            and_(
                BiometricAuth.user_id == user_id,
                BiometricAuth.device_id == device_id
            )
        )
        
        if biometric_type:
            query = query.filter(BiometricAuth.biometric_type == biometric_type)
        
        auths = query.all()
        
        for auth in auths:
            auth.status = BiometricStatus.DISABLED
            auth.updated_at = datetime.utcnow()
        
        self.db.commit()
        return len(auths) > 0

    def revoke_device(self, user_id: int, device_id: str) -> bool:
        """Revoke all access for a device"""
        # Disable device
        device = self.db.query(UserDevice).filter(
            and_(
                UserDevice.user_id == user_id,
                UserDevice.device_id == device_id
            )
        ).first()
        
        if device:
            device.is_active = False
            device.updated_at = datetime.utcnow()
        
        # Disable all biometric auths for device
        self.disable_biometric_auth(user_id, device_id)
        
        # Revoke all biometric tokens for device
        tokens = self.db.query(BiometricToken).filter(
            and_(
                BiometricToken.user_id == user_id,
                BiometricToken.device_id == device_id,
                BiometricToken.is_active == True
            )
        ).all()
        
        for token in tokens:
            token.is_active = False
            token.revoked_at = datetime.utcnow()
        
        self.db.commit()
        return True

    def get_auth_attempts(
        self, 
        user_id: int, 
        device_id: Optional[str] = None,
        limit: int = 50
    ) -> List[BiometricAuthAttempt]:
        """Get authentication attempts for a user"""
        query = self.db.query(BiometricAuthAttempt).filter(
            BiometricAuthAttempt.user_id == user_id
        )
        
        if device_id:
            query = query.filter(BiometricAuthAttempt.device_id == device_id)
        
        return query.order_by(desc(BiometricAuthAttempt.attempted_at)).limit(limit).all()

    def _create_biometric_token(
        self, 
        user_id: int, 
        device_id: str, 
        biometric_type: BiometricType
    ) -> BiometricToken:
        """Create a biometric token for the session"""
        token = BiometricToken(
            user_id=user_id,
            device_id=device_id,
            biometric_type=biometric_type,
            token=self._generate_secure_token(),
            expires_at=datetime.utcnow() + timedelta(hours=24)  # 24 hour expiry
        )
        
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    def _verify_biometric_signature(
        self, 
        public_key: str, 
        signature: str, 
        challenge: str
    ) -> bool:
        """
        Verify biometric signature using proper cryptographic verification.
        Supports both RSA and ECDSA signatures for production use.
        """
        try:
            # Decode the signature and challenge
            decoded_signature = base64.b64decode(signature)
            challenge_bytes = challenge.encode('utf-8')
            
            # Parse the public key (PEM format)
            try:
                public_key_obj = serialization.load_pem_public_key(
                    public_key.encode('utf-8')
                )
            except Exception:
                # Try loading as DER format if PEM fails
                try:
                    public_key_obj = serialization.load_der_public_key(
                        base64.b64decode(public_key)
                    )
                except Exception:
                    logger.error("Failed to parse public key")
                    return False
            
            # Verify signature based on key type
            if isinstance(public_key_obj, rsa.RSAPublicKey):
                return self._verify_rsa_signature(
                    public_key_obj, decoded_signature, challenge_bytes
                )
            elif isinstance(public_key_obj, ec.EllipticCurvePublicKey):
                return self._verify_ecdsa_signature(
                    public_key_obj, decoded_signature, challenge_bytes
                )
            else:
                logger.error(f"Unsupported key type: {type(public_key_obj)}")
                return False
                
        except Exception as e:
            logger.error(f"Signature verification error: {str(e)}")
            return False
    
    def _verify_rsa_signature(
        self, 
        public_key: rsa.RSAPublicKey, 
        signature: bytes, 
        challenge: bytes
    ) -> bool:
        """Verify RSA signature with PSS padding"""
        try:
            public_key.verify(
                signature,
                challenge,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except InvalidSignature:
            # Try PKCS1v15 padding as fallback
            try:
                public_key.verify(
                    signature,
                    challenge,
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
                return True
            except InvalidSignature:
                return False
        except Exception as e:
            logger.error(f"RSA signature verification error: {str(e)}")
            return False
    
    def _verify_ecdsa_signature(
        self, 
        public_key: ec.EllipticCurvePublicKey, 
        signature: bytes, 
        challenge: bytes
    ) -> bool:
        """Verify ECDSA signature"""
        try:
            public_key.verify(
                signature,
                challenge,
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except InvalidSignature:
            return False
        except Exception as e:
            logger.error(f"ECDSA signature verification error: {str(e)}")
            return False

    def _log_auth_attempt(
        self, 
        device_id: str,
        biometric_type: BiometricType,
        success: bool,
        user_id: Optional[int] = None,
        failure_reason: Optional[str] = None
    ):
        """Log authentication attempt"""
        attempt = BiometricAuthAttempt(
            user_id=user_id,
            device_id=device_id,
            biometric_type=biometric_type,
            success=success,
            failure_reason=failure_reason if not success else None,
            attempted_at=datetime.utcnow()
        )
        
        self.db.add(attempt)
        self.db.commit()

    def _generate_secure_token(self) -> str:
        """Generate a secure random token"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8')

    def generate_auth_challenge(self) -> str:
        """Generate a challenge for biometric authentication"""
        challenge_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'nonce': secrets.token_hex(16)
        }
        
        challenge_string = f"{challenge_data['timestamp']}:{challenge_data['nonce']}"
        return base64.b64encode(challenge_string.encode()).decode('utf-8')

    def cleanup_expired_tokens(self):
        """Clean up expired biometric tokens"""
        expired_tokens = self.db.query(BiometricToken).filter(
            and_(
                BiometricToken.expires_at < datetime.utcnow(),
                BiometricToken.is_active == True
            )
        ).all()
        
        for token in expired_tokens:
            token.is_active = False
            token.revoked_at = datetime.utcnow()
        
        self.db.commit()
        return len(expired_tokens)