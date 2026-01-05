import pytest
from fastapi.testclient import TestClient
from io import BytesIO
from PIL import Image
import json

class TestUploadEndpoints:
    """Test cases for upload API endpoints."""
    
    def test_upload_image_success(self, client: TestClient):
        """Test successful image upload without authentication."""
        # Create a test image
        image = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        image.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {
            'file': ('test_image.jpg', img_bytes, 'image/jpeg')
        }
        
        response = client.post("/api/v1/upload/image", files=files)
        
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert "file_url" in data
        assert "file_name" in data
        assert "file_size" in data
        assert "content_type" in data
        assert data["content_type"] == "image/jpeg"
        assert data["file_size"] > 0
    
    def test_upload_image_png(self, client: TestClient):
        """Test uploading PNG image."""
        image = Image.new('RGB', (100, 100), color='blue')
        img_bytes = BytesIO()
        image.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        files = {
            'file': ('test_image.png', img_bytes, 'image/png')
        }
        
        response = client.post("/api/v1/upload/image", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["content_type"] == "image/png"
    
    def test_upload_image_invalid_type(self, client: TestClient):
        """Test uploading invalid file type."""
        files = {
            'file': ('test.txt', BytesIO(b'test content'), 'text/plain')
        }
        
        response = client.post("/api/v1/upload/image", files=files)
        
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]
    
    def test_upload_image_too_large(self, client: TestClient):
        """Test uploading file that exceeds size limit."""
        # Create file larger than 10MB
        large_content = b'x' * (11 * 1024 * 1024)
        
        files = {
            'file': ('large_image.jpg', BytesIO(large_content), 'image/jpeg')
        }
        
        response = client.post("/api/v1/upload/image", files=files)
        
        assert response.status_code == 400
        assert "too large" in response.json()["detail"].lower()
    
    def test_get_presigned_url_video(self, client: TestClient):
        """Test getting presigned URL for video upload."""
        request_data = {
            "filename": "my_video.mp4",
            "content_type": "video/mp4",
            "file_type": "video"
        }
        
        response = client.post("/api/v1/upload/presigned-url", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "upload_url" in data
        assert "download_url" in data
        assert "blob_path" in data
        assert "expires_at" in data
        assert "content_type" in data
        assert "method" in data
        assert data["content_type"] == "video/mp4"
        assert data["method"] == "PUT"
        assert "my_video.mp4" in data["blob_path"]
    
    def test_get_presigned_url_image(self, client: TestClient):
        """Test getting presigned URL for image upload."""
        request_data = {
            "filename": "photo.jpg",
            "content_type": "image/jpeg",
            "file_type": "image"
        }
        
        response = client.post("/api/v1/upload/presigned-url", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "upload_url" in data
        assert "download_url" in data
        assert data["content_type"] == "image/jpeg"
        assert "uploads/images" in data["blob_path"]
    
    def test_get_presigned_url_document(self, client: TestClient):
        """Test getting presigned URL for document upload."""
        request_data = {
            "filename": "document.pdf",
            "content_type": "application/pdf",
            "file_type": "document"
        }
        
        response = client.post("/api/v1/upload/presigned-url", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "upload_url" in data
        assert data["content_type"] == "application/pdf"
        assert "uploads/documents" in data["blob_path"]
    
    def test_get_presigned_url_invalid_content_type(self, client: TestClient):
        """Test getting presigned URL with invalid content type."""
        request_data = {
            "filename": "test.exe",
            "content_type": "application/x-executable",
            "file_type": "other"
        }
        
        response = client.post("/api/v1/upload/presigned-url", json=request_data)
        
        assert response.status_code == 400
        assert "Invalid content type" in response.json()["detail"]
    
    def test_upload_webp_image(self, client: TestClient):
        """Test uploading WebP image."""
        image = Image.new('RGB', (100, 100), color='green')
        img_bytes = BytesIO()
        image.save(img_bytes, format='WEBP')
        img_bytes.seek(0)
        
        files = {
            'file': ('test_image.webp', img_bytes, 'image/webp')
        }
        
        response = client.post("/api/v1/upload/image", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["content_type"] == "image/webp"
    
    def test_presigned_url_quicktime_video(self, client: TestClient):
        """Test getting presigned URL for QuickTime video."""
        request_data = {
            "filename": "video.mov",
            "content_type": "video/quicktime",
            "file_type": "video"
        }
        
        response = client.post("/api/v1/upload/presigned-url", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["content_type"] == "video/quicktime"
        assert "uploads/videos" in data["blob_path"]
