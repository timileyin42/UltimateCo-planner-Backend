"""
Background task to clean up expired QR codes from GCP Cloud Storage bucket.
Deletes QR codes associated with expired invite codes and invite links.
"""

import logging
from datetime import datetime
import asyncio
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.invite_models import InviteCode, InviteLink
from app.services.gcp_storage_service import GCPStorageService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def cleanup_expired_qr_codes():
    """
    Delete QR code files from GCP bucket for expired invites.
    Checks both InviteCode and InviteLink models for expired entries.
    """
    db: Session = SessionLocal()
    storage_service = GCPStorageService()
    deleted_count = 0
    
    try:
        # Get all expired invite codes with QR codes
        expired_codes = db.query(InviteCode).filter(
            InviteCode.expires_at.isnot(None),
            InviteCode.expires_at < datetime.utcnow(),
            InviteCode.qr_code_url.isnot(None)
        ).all()
        
        # Get all expired invite links with QR codes
        expired_links = db.query(InviteLink).filter(
            InviteLink.expires_at.isnot(None),
            InviteLink.expires_at < datetime.utcnow(),
            InviteLink.qr_code_url.isnot(None)
        ).all()
        
        # Delete QR codes for expired invite codes
        for invite in expired_codes:
            try:
                # Extract blob path from URL or use the stored path directly
                qr_url = invite.qr_code_url
                
                # If it's a full URL, extract the blob path
                if qr_url.startswith("https://storage.googleapis.com/"):
                    # Format: https://storage.googleapis.com/bucket_name/qr_codes/user_123/filename.png
                    blob_path = "/".join(qr_url.split("/")[4:])
                else:
                    # It's already a blob path
                    blob_path = qr_url
                
                # Delete from GCP bucket
                success = await storage_service.delete_file(blob_path)
                
                if success:
                    # Clear the QR code URL from database
                    invite.qr_code_url = None
                    deleted_count += 1
                    logger.debug(f"Deleted expired QR code for invite code {invite.code}")
                    
            except Exception as e:
                logger.error(f"Failed to delete QR code for invite code {invite.id}: {str(e)}")
        
        # Delete QR codes for expired invite links
        for invite in expired_links:
            try:
                # Extract blob path from URL or use the stored path directly
                qr_url = invite.qr_code_url
                
                # If it's a full URL, extract the blob path
                if qr_url.startswith("https://storage.googleapis.com/"):
                    blob_path = "/".join(qr_url.split("/")[4:])
                else:
                    blob_path = qr_url
                
                # Delete from GCP bucket
                success = await storage_service.delete_file(blob_path)
                
                if success:
                    # Clear the QR code URL from database
                    invite.qr_code_url = None
                    deleted_count += 1
                    logger.debug(f"Deleted expired QR code for invite link {invite.link_id}")
                    
            except Exception as e:
                logger.error(f"Failed to delete QR code for invite link {invite.id}: {str(e)}")
        
        # Commit all changes to database
        db.commit()
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired QR codes from GCP bucket")
        else:
            logger.info("No expired QR codes found to clean up")
            
    except Exception as e:
        db.rollback()
        logger.error(f"QR code cleanup failed: {str(e)}")
    finally:
        db.close()


def schedule_qr_cleanup():
    """
    Schedule periodic QR code cleanup.
    Runs every 24 hours to delete QR codes for expired invites.
    """
    import asyncio
    
    async def cleanup_loop():
        while True:
            try:
                await cleanup_expired_qr_codes()
            except Exception as e:
                logger.error(f"Cleanup loop error: {str(e)}")
            
            # Run every 24 hours
            await asyncio.sleep(24 * 3600)
    
    return cleanup_loop()


@celery_app.task(name="app.tasks.cleanup_qr_codes.run_cleanup")
def run_cleanup():
    """Celery task wrapper to run QR code cleanup (executes daily via beat)."""
    asyncio.run(cleanup_expired_qr_codes())
