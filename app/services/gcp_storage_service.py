"""
Google Cloud Storage service for file uploads and management.
Provides secure file upload, download, and management functionality.
"""

import logging
import os
import base64
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import uuid
from google.cloud import storage
from google.oauth2 import service_account
from google.cloud.exceptions import NotFound, GoogleCloudError
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class GCPStorageService:
    """Service for managing file uploads to Google Cloud Storage."""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = None
        self.bucket = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize GCP Storage client."""
        try:
            # Check if base64 encoded key is available from settings
            encoded_key = self.settings.GCP_SERVICE_ACCOUNT_KEY_BASE64
            
            if encoded_key:
                # Decode base64 key
                try:
                    decoded_bytes = base64.b64decode(encoded_key)
                    key_dict = json.loads(decoded_bytes)
                    
                    # Fix escaped newlines in private key
                    if 'private_key' in key_dict:
                        key_dict['private_key'] = key_dict['private_key'].replace('\\n', '\n')
                    
                    credentials = service_account.Credentials.from_service_account_info(key_dict)
                    
                    self.client = storage.Client(
                        project=self.settings.GCP_PROJECT_ID,
                        credentials=credentials
                    )
                    logger.info("GCP Storage client initialized using base64 encoded credentials")
                except Exception as e:
                    logger.error(f"Failed to decode base64 credentials: {str(e)}")
                    raise
            elif hasattr(self.settings, 'GOOGLE_APPLICATION_CREDENTIALS') and self.settings.GOOGLE_APPLICATION_CREDENTIALS:
                # Fallback to JSON file path
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.settings.GOOGLE_APPLICATION_CREDENTIALS
                self.client = storage.Client(project=self.settings.GCP_PROJECT_ID)
                logger.info("GCP Storage client initialized using credentials file")
            else:
                # Try default credentials (for GCP environments)
                self.client = storage.Client(project=self.settings.GCP_PROJECT_ID)
                logger.info("GCP Storage client initialized using default credentials")
            
            self.bucket = self.client.bucket(self.settings.GCP_STORAGE_BUCKET)
            logger.info(f"GCP Storage configured for bucket: {self.settings.GCP_STORAGE_BUCKET}")
            
        except Exception as e:
            logger.error(f"Failed to initialize GCP Storage client: {str(e)}")
            # Fallback to local storage in development
            if self.settings.ENVIRONMENT == "development":
                logger.warning("Using local file storage as fallback")
                self.client = None
                self.bucket = None
            else:
                raise
    
    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        folder: str = "uploads",
        user_id: Optional[int] = None,
        make_public: bool = False
    ) -> Dict[str, Any]:
        """
        Upload a file to GCP Cloud Storage.
        
        Args:
            file_content: The file content as bytes
            filename: Original filename
            content_type: MIME type of the file
            folder: Folder/prefix in the bucket
            user_id: Optional user ID for organizing files
            make_public: Whether to make the file publicly accessible (for QR codes, public assets)
            
        Returns:
            Dict containing file URL, filename, size, etc.
        """
        try:
            # Generate unique filename
            file_extension = os.path.splitext(filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            
            # Create blob path
            if user_id:
                blob_path = f"{folder}/user_{user_id}/{unique_filename}"
            else:
                blob_path = f"{folder}/{unique_filename}"
            
            if self.client and self.bucket:
                # Upload to GCP Storage
                blob = self.bucket.blob(blob_path)
                blob.upload_from_string(file_content, content_type=content_type)
                
                # Set cache control for better performance
                blob.cache_control = "public, max-age=3600"
                blob.patch()
                
                # With uniform bucket-level access, all objects are public or private based on bucket policy
                # Generate public URL directly without ACL operations
                if make_public:
                    # Public URL format: https://storage.googleapis.com/bucket_name/blob_path
                    file_url = f"https://storage.googleapis.com/{self.settings.GCP_STORAGE_BUCKET}/{blob_path}"
                else:
                    # For private files, return the blob path - we'll generate signed URLs when needed
                    file_url = blob_path  # Store path, not URL
                
                logger.info(f"File uploaded to GCP Storage: {blob_path} (public={make_public})")
                
            else:
                # Fallback to local storage
                file_url = await self._upload_local(file_content, blob_path)
                logger.info(f"File uploaded locally: {blob_path}")
            
            return {
                "file_url": file_url,
                "filename": filename,
                "unique_filename": unique_filename,
                "file_size": len(file_content),
                "content_type": content_type,
                "blob_path": blob_path,
                "is_public": make_public,
                "uploaded_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to upload file {filename}: {str(e)}")
            raise Exception(f"File upload failed: {str(e)}")
    
    async def delete_file(self, blob_path: str) -> bool:
        """
        Delete a file from GCP Cloud Storage.
        
        Args:
            blob_path: Path to the blob in the bucket
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            if self.client and self.bucket:
                blob = self.bucket.blob(blob_path)
                blob.delete()
                logger.info(f"File deleted from GCP Storage: {blob_path}")
            else:
                # Delete from local storage
                local_path = os.path.join("uploads", blob_path)
                if os.path.exists(local_path):
                    os.remove(local_path)
                    logger.info(f"File deleted locally: {local_path}")
            
            return True
            
        except NotFound:
            logger.warning(f"File not found for deletion: {blob_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete file {blob_path}: {str(e)}")
            return False
    
    async def generate_upload_signed_url(
        self,
        filename: str,
        content_type: str,
        folder: str = "uploads/videos",
        user_id: Optional[int] = None,
        expiration_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Generate a signed URL for direct upload to GCS (for large files like videos).
        
        Args:
            filename: Original filename
            content_type: MIME type of the file
            folder: Folder/prefix in the bucket
            user_id: Optional user ID for organizing files
            expiration_minutes: URL expiration time in minutes (default 60)
            
        Returns:
            Dict containing upload URL, blob path, and expiration info
        """
        try:
            # Generate unique blob path
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            sanitized_filename = os.path.basename(filename)
            
            if user_id:
                blob_path = f"{folder}/user_{user_id}/{timestamp}_{unique_id}_{sanitized_filename}"
            else:
                blob_path = f"{folder}/{timestamp}_{unique_id}_{sanitized_filename}"
            
            if self.client and self.bucket:
                blob = self.bucket.blob(blob_path)
                
                # Generate signed URL for upload (PUT method)
                upload_url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(minutes=expiration_minutes),
                    method="PUT",
                    content_type=content_type
                )
                
                # Generate download URL (will be available after upload)
                download_url = f"https://storage.googleapis.com/{self.settings.GCP_STORAGE_BUCKET}/{blob_path}"
                
                logger.info(f"Generated upload signed URL for: {blob_path}")
                
                return {
                    "upload_url": upload_url,
                    "download_url": download_url,
                    "blob_path": blob_path,
                    "expires_at": (datetime.utcnow() + timedelta(minutes=expiration_minutes)).isoformat(),
                    "content_type": content_type,
                    "method": "PUT"
                }
            else:
                # Local development fallback
                return {
                    "upload_url": f"http://localhost:8000/uploads/{blob_path}",
                    "download_url": f"/uploads/{blob_path}",
                    "blob_path": blob_path,
                    "expires_at": (datetime.utcnow() + timedelta(minutes=expiration_minutes)).isoformat(),
                    "content_type": content_type,
                    "method": "PUT"
                }
                
        except Exception as e:
            logger.error(f"Failed to generate upload signed URL: {str(e)}")
            raise
    
    async def get_file_url(self, blob_path: str, expiration_minutes: int = 60) -> Optional[str]:
        """
        Get a signed URL for a file (for private files).
        
        Args:
            blob_path: Path to the blob in the bucket
            expiration_minutes: URL expiration time in minutes
            
        Returns:
            Signed URL or None if file doesn't exist
        """
        try:
            if self.client and self.bucket:
                blob = self.bucket.blob(blob_path)
                
                # Check if blob exists
                if not blob.exists():
                    logger.warning(f"Blob not found: {blob_path}")
                    return None
                
                # Generate signed URL (works for both public and private buckets)
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(minutes=expiration_minutes),
                    method="GET"
                )
                
                return url
            else:
                # Return local file URL
                return f"/uploads/{blob_path}"
                
        except Exception as e:
            logger.error(f"Failed to generate signed URL for {blob_path}: {str(e)}")
            return None
    
    def get_public_url(self, blob_path: str) -> str:
        """
        Get public URL for a blob (doesn't check if actually public).
        Use this for files you know are public.
        
        Args:
            blob_path: Path to the blob in the bucket
            
        Returns:
            Public URL
        """
        if self.client and self.bucket:
            return f"https://storage.googleapis.com/{self.settings.GCP_STORAGE_BUCKET}/{blob_path}"
        else:
            return f"/static/{blob_path}"
    
    async def list_files(self, prefix: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        """
        List files in the bucket with optional prefix filter.
        
        Args:
            prefix: Prefix to filter files
            limit: Maximum number of files to return
            
        Returns:
            List of file information dictionaries
        """
        try:
            files = []
            
            if self.client and self.bucket:
                blobs = self.client.list_blobs(
                    self.bucket,
                    prefix=prefix,
                    max_results=limit
                )
                
                for blob in blobs:
                    files.append({
                        "name": blob.name,
                        "size": blob.size,
                        "content_type": blob.content_type,
                        "created": blob.time_created.isoformat() if blob.time_created else None,
                        "updated": blob.updated.isoformat() if blob.updated else None,
                        "public_url": f"https://storage.googleapis.com/{self.settings.GCP_STORAGE_BUCKET}/{blob.name}"
                    })
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to list files with prefix {prefix}: {str(e)}")
            return []
    
    async def _upload_local(self, file_content: bytes, blob_path: str) -> str:
        """
        Fallback method to upload file locally.
        
        Args:
            file_content: File content as bytes
            blob_path: Path where file should be stored
            
        Returns:
            Local file URL
        """
        try:
            # Create directory if it doesn't exist
            local_path = os.path.join("uploads", blob_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Write file
            with open(local_path, "wb") as f:
                f.write(file_content)
            
            return f"/uploads/{blob_path}"
            
        except Exception as e:
            logger.error(f"Failed to upload file locally: {str(e)}")
            raise
    
    def validate_file(
        self,
        filename: str,
        file_size: int,
        content_type: str,
        allowed_extensions: Optional[List[str]] = None,
        max_size_mb: int = 10
    ) -> Dict[str, Any]:
        """
        Validate file before upload.
        
        Args:
            filename: Original filename
            file_size: File size in bytes
            content_type: MIME type
            allowed_extensions: List of allowed file extensions
            max_size_mb: Maximum file size in MB
            
        Returns:
            Validation result dictionary
        """
        errors = []
        
        # Check file size
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            errors.append(f"File size ({file_size} bytes) exceeds maximum allowed size ({max_size_mb}MB)")
        
        # Check file extension
        if allowed_extensions:
            file_extension = os.path.splitext(filename)[1].lower().lstrip('.')
            if file_extension not in [ext.lower() for ext in allowed_extensions]:
                errors.append(f"File extension '{file_extension}' is not allowed. Allowed: {', '.join(allowed_extensions)}")
        
        # Check content type for images
        if content_type and content_type.startswith('image/'):
            allowed_image_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if content_type not in allowed_image_types:
                errors.append(f"Image type '{content_type}' is not supported")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "file_info": {
                "filename": filename,
                "size": file_size,
                "content_type": content_type
            }
        }


# Global instance
gcp_storage_service = GCPStorageService()