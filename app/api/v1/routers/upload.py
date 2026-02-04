from fastapi import APIRouter, UploadFile, File, HTTPException, status, Form
from app.services.gcp_storage_service import GCPStorageService
from app.core.errors import http_400_bad_request
from pydantic import BaseModel
from typing import Optional

upload_router = APIRouter()

class UploadResponse(BaseModel):
    """Unified response for all uploads"""
    upload_type: str  # "direct" or "presigned"
    download_url: str  # PERMANENT public URL - never expires
    filename: str
    content_type: str
    blob_path: Optional[str] = None  # GCS blob path for reference
    # For presigned uploads only
    upload_url: Optional[str] = None  # URL to PUT the file to (expires in 60 min)
    expires_at: Optional[str] = None  # When upload_url expires (download_url never expires)
    # For direct uploads only
    file_size: Optional[int] = None

@upload_router.post("/", response_model=UploadResponse)
async def upload_file(
    file: Optional[UploadFile] = File(None),
    filename: Optional[str] = Form(None),
    content_type: Optional[str] = Form(None)
):
    """
    Unified upload endpoint - handles both direct uploads and presigned URLs.
    No authentication required. Always returns a download_url.

    Supported file types:
    - Images: jpeg, png, webp, gif (max 100MB) - direct upload
    - Videos: mp4, mov, avi, webm (max 500MB) - presigned URL
    - Documents: pdf, doc, docx (max 50MB) - presigned URL
    """
    try:
        # Define file types
        video_types = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"]
        image_types = ["image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"]
        document_types = ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
        
        # MODE 1: Direct file upload (for images)
        if file:
            # Validate file type
            if file.content_type not in image_types:
                raise http_400_bad_request(
                    f"Direct upload only supports images. For videos/documents, request a presigned URL. "
                    f"Allowed types: {', '.join(image_types)}"
                )
            
            # Validate file size (max 100MB for images)
            file_content = await file.read()
            file_size = len(file_content)
            
            if file_size > 100 * 1024 * 1024:
                raise http_400_bad_request("Image size too large. Maximum size is 100MB")
            
            # Upload to storage
            storage_service = GCPStorageService()
            upload_result = await storage_service.upload_file(
                file_content=file_content,
                filename=file.filename,
                content_type=file.content_type,
                folder="uploads/images",
                make_public=True
            )
            
            return UploadResponse(
                upload_type="direct",
                download_url=upload_result["file_url"],
                filename=upload_result["filename"],
                content_type=file.content_type,
                blob_path=upload_result["blob_path"],
                file_size=file_size
            )
        
        # MODE 2: Request presigned URL (for videos/large files)
        elif filename and content_type:
            # Validate content type
            allowed_types = video_types + image_types + document_types
            
            if content_type not in allowed_types:
                raise http_400_bad_request(
                    f"Invalid content type: {content_type}. "
                    f"Allowed types: {', '.join(allowed_types)}"
                )
            
            # Determine folder based on file type
            if content_type in video_types:
                folder = "uploads/videos"
            elif content_type in image_types:
                folder = "uploads/images"
            else:
                folder = "uploads/documents"
            
            # Generate presigned URL (valid for 60 minutes)
            storage_service = GCPStorageService()
            result = await storage_service.generate_upload_signed_url(
                filename=filename,
                content_type=content_type,
                folder=folder,
                expiration_minutes=60
            )
            
            return UploadResponse(
                upload_type="presigned",
                download_url=result["download_url"],
                filename=filename,
                content_type=content_type,
                blob_path=result["blob_path"],
                upload_url=result["upload_url"],
                expires_at=result["expires_at"]
            )
        
        else:
            raise http_400_bad_request(
                "Either provide a file for direct upload, or filename + content_type for presigned URL"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise http_400_bad_request(f"Upload failed: {str(e)}")
