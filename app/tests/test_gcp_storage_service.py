"""
Tests for GCP Storage Service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.gcp_storage_service import GCPStorageService, gcp_storage_service
import os
from datetime import datetime


class TestGCPStorageService:
    """Test cases for GCP Storage Service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_settings = Mock()
        self.mock_settings.GCP_PROJECT_ID = "test-project"
        self.mock_settings.GCP_STORAGE_BUCKET = "test-bucket"
        self.mock_settings.GCP_STORAGE_REGION = "us-central1"
        self.mock_settings.GOOGLE_APPLICATION_CREDENTIALS = "/path/to/credentials.json"
        self.mock_settings.ENVIRONMENT = "test"
        
        self.mock_client = Mock()
        self.mock_bucket = Mock()
        self.mock_blob = Mock()
        
        self.service = GCPStorageService()
    
    @patch('app.services.gcp_storage_service.get_settings')
    @patch('app.services.gcp_storage_service.storage.Client')
    def test_initialize_client_success(self, mock_storage_client, mock_get_settings):
        """Test successful GCP client initialization."""
        mock_get_settings.return_value = self.mock_settings
        mock_storage_client.return_value = self.mock_client
        self.mock_client.bucket.return_value = self.mock_bucket
        
        service = GCPStorageService()
        
        assert service.client == self.mock_client
        assert service.bucket == self.mock_bucket
        mock_storage_client.assert_called_once_with(project=self.mock_settings.GCP_PROJECT_ID)
    
    @patch('app.services.gcp_storage_service.get_settings')
    @patch('app.services.gcp_storage_service.storage.Client')
    def test_initialize_client_failure_development(self, mock_storage_client, mock_get_settings):
        """Test client initialization failure in development environment."""
        mock_get_settings.return_value = self.mock_settings
        self.mock_settings.ENVIRONMENT = "development"
        mock_storage_client.side_effect = Exception("GCP Error")
        
        service = GCPStorageService()
        
        assert service.client is None
        assert service.bucket is None
    
    @pytest.mark.asyncio
    async def test_upload_file_success(self):
        """Test successful file upload to GCP Storage."""
        with patch.object(self.service, 'client', self.mock_client), \
             patch.object(self.service, 'bucket', self.mock_bucket), \
             patch.object(self.service, 'settings', self.mock_settings):
            
            self.mock_bucket.blob.return_value = self.mock_blob
            
            file_content = b"test file content"
            filename = "test.jpg"
            content_type = "image/jpeg"
            
            result = await self.service.upload_file(
                file_content=file_content,
                filename=filename,
                content_type=content_type,
                folder="test",
                user_id=1
            )
            
            assert "file_url" in result
            assert result["filename"] == filename
            assert result["file_size"] == len(file_content)
            assert result["content_type"] == content_type
            
            self.mock_blob.upload_from_string.assert_called_once_with(
                file_content, content_type=content_type
            )
    
    @pytest.mark.asyncio
    async def test_upload_file_local_fallback(self):
        """Test file upload with local fallback when GCP is unavailable."""
        with patch.object(self.service, 'client', None), \
             patch.object(self.service, 'bucket', None), \
             patch.object(self.service, '_upload_local') as mock_upload_local:
            
            mock_upload_local.return_value = "/uploads/test/file.jpg"
            
            file_content = b"test file content"
            filename = "test.jpg"
            content_type = "image/jpeg"
            
            result = await self.service.upload_file(
                file_content=file_content,
                filename=filename,
                content_type=content_type
            )
            
            assert "file_url" in result
            mock_upload_local.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_file_success(self):
        """Test successful file deletion from GCP Storage."""
        with patch.object(self.service, 'client', self.mock_client), \
             patch.object(self.service, 'bucket', self.mock_bucket):
            
            self.mock_bucket.blob.return_value = self.mock_blob
            
            result = await self.service.delete_file("test/file.jpg")
            
            assert result is True
            self.mock_blob.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_file_not_found(self):
        """Test file deletion when file doesn't exist."""
        from google.cloud.exceptions import NotFound
        
        with patch.object(self.service, 'client', self.mock_client), \
             patch.object(self.service, 'bucket', self.mock_bucket):
            
            self.mock_bucket.blob.return_value = self.mock_blob
            self.mock_blob.delete.side_effect = NotFound("File not found")
            
            result = await self.service.delete_file("test/nonexistent.jpg")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_file_url_success(self):
        """Test successful signed URL generation."""
        with patch.object(self.service, 'client', self.mock_client), \
             patch.object(self.service, 'bucket', self.mock_bucket):
            
            self.mock_bucket.blob.return_value = self.mock_blob
            self.mock_blob.generate_signed_url.return_value = "https://signed-url.com"
            
            result = await self.service.get_file_url("test/file.jpg")
            
            assert result == "https://signed-url.com"
            self.mock_blob.generate_signed_url.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_files_success(self):
        """Test successful file listing."""
        with patch.object(self.service, 'client', self.mock_client), \
             patch.object(self.service, 'bucket', self.mock_bucket), \
             patch.object(self.service, 'settings', self.mock_settings):
            
            mock_blob1 = Mock()
            mock_blob1.name = "test/file1.jpg"
            mock_blob1.size = 1024
            mock_blob1.content_type = "image/jpeg"
            mock_blob1.time_created = datetime.now()
            mock_blob1.updated = datetime.now()
            
            mock_blob2 = Mock()
            mock_blob2.name = "test/file2.png"
            mock_blob2.size = 2048
            mock_blob2.content_type = "image/png"
            mock_blob2.time_created = datetime.now()
            mock_blob2.updated = datetime.now()
            
            self.mock_client.list_blobs.return_value = [mock_blob1, mock_blob2]
            
            result = await self.service.list_files(prefix="test/")
            
            assert len(result) == 2
            assert result[0]["name"] == "test/file1.jpg"
            assert result[1]["name"] == "test/file2.png"
    
    def test_validate_file_success(self):
        """Test successful file validation."""
        result = self.service.validate_file(
            filename="test.jpg",
            file_size=1024,
            content_type="image/jpeg",
            allowed_extensions=["jpg", "png"],
            max_size_mb=10
        )
        
        assert result["is_valid"] is True
        assert len(result["errors"]) == 0
    
    def test_validate_file_size_exceeded(self):
        """Test file validation with size exceeded."""
        result = self.service.validate_file(
            filename="large.jpg",
            file_size=20 * 1024 * 1024,  # 20MB
            content_type="image/jpeg",
            max_size_mb=10
        )
        
        assert result["is_valid"] is False
        assert any("exceeds maximum" in error for error in result["errors"])
    
    def test_validate_file_invalid_extension(self):
        """Test file validation with invalid extension."""
        result = self.service.validate_file(
            filename="test.exe",
            file_size=1024,
            content_type="application/octet-stream",
            allowed_extensions=["jpg", "png"]
        )
        
        assert result["is_valid"] is False
        assert any("not allowed" in error for error in result["errors"])
    
    def test_validate_file_invalid_image_type(self):
        """Test file validation with invalid image content type."""
        result = self.service.validate_file(
            filename="test.jpg",
            file_size=1024,
            content_type="image/bmp",
            allowed_extensions=["jpg"]
        )
        
        assert result["is_valid"] is False
        assert any("not supported" in error for error in result["errors"])
    
    @pytest.mark.asyncio
    async def test_upload_local_success(self):
        """Test successful local file upload."""
        with patch('os.makedirs'), \
             patch('builtins.open', create=True) as mock_open:
            
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            result = await self.service._upload_local(b"test content", "test/file.jpg")
            
            assert result == "/uploads/test/file.jpg"
            mock_file.write.assert_called_once_with(b"test content")
    
    @pytest.mark.asyncio
    async def test_upload_local_failure(self):
        """Test local file upload failure."""
        with patch('os.makedirs'), \
             patch('builtins.open', side_effect=Exception("Write error")):
            
            with pytest.raises(Exception):
                await self.service._upload_local(b"test content", "test/file.jpg")


class TestGlobalInstance:
    """Test the global GCP storage service instance."""
    
    def test_global_instance_exists(self):
        """Test that global instance is available."""
        assert gcp_storage_service is not None
        assert isinstance(gcp_storage_service, GCPStorageService)