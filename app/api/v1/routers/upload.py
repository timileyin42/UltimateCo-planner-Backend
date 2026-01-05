from fastapi import APIRouter, UploadFile, File, HTTPException, status, Body
from app.services.gcp_storage_service import GCPStorageService
from app.core.errors import http_400_bad_request
from pydantic import BaseModel
from typing import Optional

upload_router = APIRouter()

class UploadResponse(BaseModel):
    """Response model for file upload"""
    file_url: str
    file_name: str
    file_size: int
    content_type: str

class PresignedUploadRequest(BaseModel):
    """Request model for presigned upload URL"""
    filename: str
    content_type: str
    file_type: str = "video"  # video, image, document

class PresignedUploadResponse(BaseModel):
    """Response model for presigned upload URL"""
    upload_url: str
    download_url: str
    blob_path: str
    expires_at: str
    content_type: str
    method: str

@upload_router.post("/image", response_model=UploadResponse)
async def upload_image(
    file: UploadFile = File(...)
):
    """
    Upload an image and get a downloadable link.
    No authentication required - use this for all image uploads in the app.
    
    Supported formats: JPEG, PNG, WebP, GIF
    Maximum size: 10MB
    """
    try:
        # Validate file type
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"]
        if file.content_type not in allowed_types:
            raise http_400_bad_request(
                "Invalid file type. Only JPEG, PNG, WebP, and GIF images are allowed"
            )
        
        # Validate file size (max 10MB)
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size > 10 * 1024 * 1024:
            raise http_400_bad_request("File size too large. Maximum size is 10MB")
        
        # Reset file pointer
        await file.seek(0)
        
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
            file_url=upload_result["file_url"],
            file_name=upload_result["filename"],
            file_size=file_size,
            content_type=file.content_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise http_400_bad_request(f"Failed to upload image: {str(e)}")

@upload_router.post("/presigned-url", response_model=PresignedUploadResponse)
async def get_presigned_upload_url(
    request: PresignedUploadRequest
):
    """
    Get a presigned URL for direct upload to cloud storage.
    Use this for large files like videos to avoid server load.
    
    Steps:
    1. Call this endpoint to get upload_url
    2. PUT the file directly to upload_url with Content-Type header
    3. Use download_url to reference the uploaded file
    
    Supported file types:
    - video: mp4, mov, avi, webm (max 500MB)
    - image: jpeg, png, webp, gif (max 10MB)
    - document: pdf, doc, docx (max 50MB)
    """
    try:
        # Validate content type
        video_types = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"]
        image_types = ["image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"]
        document_types = ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
        
        allowed_types = video_types + image_types + document_types
        
        if request.content_type not in allowed_types:
            raise http_400_bad_request(
                f"Invalid content type: {request.content_type}. "
                f"Allowed types: {', '.join(allowed_types)}"
            )
        
        # Determine folder based on file type
        if request.content_type in video_types:
            folder = "uploads/videos"
        elif request.content_type in image_types:
            folder = "uploads/images"
        else:
            folder = "uploads/documents"
        
        # Generate presigned URL (valid for 60 minutes)
        storage_service = GCPStorageService()
        result = await storage_service.generate_upload_signed_url(
            filename=request.filename,
            content_type=request.content_type,
            folder=folder,
            expiration_minutes=60
        )
        
        return PresignedUploadResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise http_400_bad_request(f"Failed to generate presigned URL: {str(e)}")
