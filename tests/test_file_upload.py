"""Tests for file upload functionality."""

import os
import tempfile
from unittest.mock import Mock, patch, mock_open
import pytest
from cleanvoice import Cleanvoice
from cleanvoice.client import ApiClient
from cleanvoice.file_handler import upload_local_file, normalize_file_input
from cleanvoice.types import ApiError, FileValidationError


class TestFileUpload:
    """Test file upload functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {"api_key": "test-key"}
        self.cv = Cleanvoice(self.config)
        from cleanvoice.types import CleanvoiceConfig
        self.api_config = CleanvoiceConfig(**self.config)
        
    @patch('cleanvoice.client.requests.Session')
    def test_get_signed_upload_url_success(self, mock_session):
        """Test successful signed URL retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {"signedUrl": "https://signed-url.com/upload"}
        mock_response.status_code = 200
        mock_session.return_value.request.return_value = mock_response
        
        client = ApiClient(self.api_config)
        signed_url = client.get_signed_upload_url("test.mp3")
        
        assert signed_url == "https://signed-url.com/upload"
        mock_session.return_value.request.assert_called_once_with(
            method="POST",
            url="https://api.cleanvoice.ai/v2/upload?filename=test.mp3",
            json=None,
            timeout=60
        )

    @patch('cleanvoice.client.requests.Session')
    def test_get_signed_upload_url_error(self, mock_session):
        """Test error handling for signed URL retrieval."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "Invalid filename"}
        mock_session.return_value.request.return_value = mock_response
        
        client = ApiClient(self.api_config)
        
        with pytest.raises(ApiError) as exc:
            client.get_signed_upload_url("invalid.txt")
        assert "Invalid filename" in str(exc.value)

    @patch('cleanvoice.client.requests.put')
    @patch('builtins.open', new_callable=mock_open, read_data=b"fake audio data")
    def test_upload_file_success(self, mock_file, mock_put):
        """Test successful file upload."""
        mock_put.return_value.status_code = 200
        mock_put.return_value.raise_for_status.return_value = None
        
        client = ApiClient(self.api_config)
        
        # Should not raise an exception
        client.upload_file("test.mp3", "https://signed-url.com/upload")
        
        mock_file.assert_called_once_with("test.mp3", 'rb')
        mock_put.assert_called_once_with(
            "https://signed-url.com/upload", 
            data=mock_file.return_value.__enter__.return_value,
            timeout=300
        )

    @patch('cleanvoice.client.requests.put')
    def test_upload_file_request_error(self, mock_put):
        """Test upload file request error handling."""
        import requests
        mock_put.side_effect = requests.exceptions.RequestException("Network error")
        
        client = ApiClient(self.api_config)
        
        with patch('builtins.open', mock_open(read_data=b"fake audio data")):
            with pytest.raises(ApiError) as exc:
                client.upload_file("test.mp3", "https://signed-url.com/upload")
        assert "File upload failed: Network error" in str(exc.value)

    @patch('builtins.open', side_effect=IOError("Permission denied"))
    def test_upload_file_io_error(self, mock_file):
        """Test upload file IO error handling."""
        client = ApiClient(self.api_config)
        
        with pytest.raises(ApiError) as exc:
            client.upload_file("test.mp3", "https://signed-url.com/upload")
        assert "Failed to read file: Permission denied" in str(exc.value)

    @patch('cleanvoice.file_handler.os.path.exists')
    def test_upload_local_file_not_found(self, mock_exists):
        """Test error when local file doesn't exist."""
        mock_exists.return_value = False
        
        with pytest.raises(FileValidationError) as exc:
            upload_local_file("nonexistent.mp3", self.cv.api_client)
        assert "Local file not found: nonexistent.mp3" in str(exc.value)

    @patch('cleanvoice.file_handler.os.path.exists')
    @patch('cleanvoice.file_handler.is_valid_media_file')
    def test_upload_local_file_invalid_format(self, mock_is_valid, mock_exists):
        """Test error when file has invalid format."""
        mock_exists.return_value = True
        mock_is_valid.return_value = False
        
        with pytest.raises(FileValidationError) as exc:
            upload_local_file("test.txt", self.cv.api_client)
        assert "File is not a valid media file: test.txt" in str(exc.value)

    @patch('cleanvoice.file_handler.os.path.exists')
    @patch('cleanvoice.file_handler.is_valid_media_file')
    def test_upload_local_file_success(self, mock_is_valid, mock_exists):
        """Test successful local file upload."""
        mock_exists.return_value = True
        mock_is_valid.return_value = True
        
        # Mock the API client methods
        mock_client = Mock()
        mock_client.get_signed_upload_url.return_value = "https://signed-url.com/upload?key=value"
        mock_client.upload_file.return_value = None
        
        result = upload_local_file("test.mp3", mock_client)
        
        assert result == "https://signed-url.com/upload"
        mock_client.get_signed_upload_url.assert_called_once_with("test.mp3")
        mock_client.upload_file.assert_called_once_with("test.mp3", "https://signed-url.com/upload?key=value")

    def test_normalize_file_input_url(self):
        """Test normalize_file_input with URL."""
        url = "https://example.com/audio.mp3"
        result = normalize_file_input(url)
        assert result == url

    def test_normalize_file_input_invalid_url(self):
        """Test normalize_file_input with invalid URL."""
        url = "https://example.com/document.pdf"
        with pytest.raises(FileValidationError) as exc:
            normalize_file_input(url)
        assert "URL does not point to a valid media file" in str(exc.value)

    @patch('cleanvoice.file_handler.os.path.exists')
    def test_normalize_file_input_local_no_client(self, mock_exists):
        """Test normalize_file_input with local file but no API client."""
        mock_exists.return_value = True
        
        with pytest.raises(FileValidationError) as exc:
            normalize_file_input("test.mp3")
        assert "Local file uploads not yet supported" in str(exc.value)

    @patch('cleanvoice.file_handler.os.path.exists')
    @patch('cleanvoice.file_handler.is_valid_media_file')
    @patch('cleanvoice.file_handler.upload_local_file')
    def test_normalize_file_input_local_with_client(self, mock_upload, mock_is_valid, mock_exists):
        """Test normalize_file_input with local file and API client."""
        mock_exists.return_value = True
        mock_is_valid.return_value = True
        mock_upload.return_value = "https://uploaded-url.com/test.mp3"
        
        mock_client = Mock()
        result = normalize_file_input("test.mp3", mock_client)
        
        assert result == "https://uploaded-url.com/test.mp3"
        mock_upload.assert_called_once_with("test.mp3", mock_client)

    @patch('cleanvoice.cleanvoice.normalize_file_input')
    def test_cleanvoice_process_with_local_file(self, mock_normalize):
        """Test Cleanvoice.process with local file upload."""
        mock_normalize.return_value = "https://uploaded-url.com/test.mp3"
        
        # Mock the API client and responses
        with patch.object(self.cv.api_client, 'create_edit') as mock_create:
            with patch.object(self.cv, '_poll_for_completion') as mock_poll:
                with patch.object(self.cv, '_transform_result') as mock_transform:
                    mock_create.return_value = Mock(id="edit123")
                    mock_poll.return_value = Mock()
                    mock_transform.return_value = Mock()
                    
                    self.cv.process("local_file.mp3")
                    
                    # Verify normalize_file_input was called with the API client
                    mock_normalize.assert_called_once_with("local_file.mp3", self.cv.api_client)

    def test_cleanvoice_upload_file_method(self):
        """Test Cleanvoice.upload_file method."""
        with patch('cleanvoice.cleanvoice.upload_local_file') as mock_upload_local:
            mock_upload_local.return_value = "https://signed-url.com/upload"

            result = self.cv.upload_file("test.mp3")

            assert result == "https://signed-url.com/upload"
            mock_upload_local.assert_called_once_with("test.mp3", self.cv.api_client, filename=None)

    def test_cleanvoice_upload_file_with_custom_filename(self):
        """Test Cleanvoice.upload_file method with custom filename."""
        with patch('cleanvoice.cleanvoice.upload_local_file') as mock_upload_local:
            mock_upload_local.return_value = "https://signed-url.com/custom.mp3"

            result = self.cv.upload_file("local_file.mp3", "custom.mp3")

            assert result == "https://signed-url.com/custom.mp3"
            mock_upload_local.assert_called_once_with("local_file.mp3", self.cv.api_client, filename="custom.mp3")

    def test_cleanvoice_upload_file_error_handling(self):
        """Test Cleanvoice.upload_file error handling."""
        with patch('cleanvoice.cleanvoice.upload_local_file') as mock_upload_local:
            mock_upload_local.side_effect = ApiError("Upload failed")

            with pytest.raises(ApiError) as exc:
                self.cv.upload_file("test.mp3")
            assert "Upload failed" in str(exc.value)

    @patch('requests.get')
    def test_download_file_success(self, mock_get):
        """Test successful file download."""
        mock_response = Mock()
        mock_response.iter_content.return_value = [b"fake audio data"]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        with patch('builtins.open', mock_open()) as mock_file:
            result = self.cv.download_file("https://example.com/processed.mp3")
            
            assert result == "processed.mp3"
            mock_get.assert_called_once_with("https://example.com/processed.mp3", stream=True, timeout=300)
            mock_file.assert_called_once_with("processed.mp3", 'wb')

    @patch('requests.get')
    def test_download_file_custom_path(self, mock_get):
        """Test file download with custom output path."""
        mock_response = Mock()
        mock_response.iter_content.return_value = [b"fake audio data"]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        with patch('builtins.open', mock_open()) as mock_file:
            result = self.cv.download_file("https://example.com/processed.mp3", "custom_output.mp3")
            
            assert result == "custom_output.mp3"
            mock_file.assert_called_once_with("custom_output.mp3", 'wb')

    @patch('requests.get')
    def test_download_file_error(self, mock_get):
        """Test download file error handling."""
        import requests
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        
        with pytest.raises(ApiError) as exc:
            self.cv.download_file("https://example.com/processed.mp3")
        assert "File download failed: Network error" in str(exc.value)

    def test_process_and_download(self):
        """Test process_and_download convenience method."""
        with patch.object(self.cv, 'process') as mock_process:
            # Mock process result
            mock_result = Mock()
            mock_result.audio.url = "https://example.com/processed.mp3"
            mock_result.audio.local_path = "downloaded.mp3"
            mock_process.return_value = mock_result

            result, downloaded_path = self.cv.process_and_download("test.mp3")

            assert result == mock_result
            assert downloaded_path == "downloaded.mp3"
            mock_process.assert_called_once_with(
                "test.mp3",
                config=None,
                progress_callback=None,
                output_path=None,
                download=True,
                template_id=None,
                upload_type=None,
            )


class TestFileUploadIntegration:
    """Integration tests for file upload functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {"api_key": "test-key"}
        self.cv = Cleanvoice(self.config)
        from cleanvoice.types import CleanvoiceConfig
        self.api_config = CleanvoiceConfig(**self.config)

    def test_create_temporary_audio_file(self):
        """Create a temporary audio file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake mp3 data")
            temp_file = f.name
        
        try:
            # Test that file exists and has proper extension
            assert os.path.exists(temp_file)
            assert temp_file.endswith(".mp3")
            
            # Test file validation functions
            from cleanvoice.file_handler import is_valid_audio_file, is_valid_media_file
            assert is_valid_audio_file(temp_file)
            assert is_valid_media_file(temp_file)
            
        finally:
            os.unlink(temp_file)

    def test_full_upload_workflow(self):
        """Test the complete file upload workflow."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake mp3 data")
            temp_file = f.name
        
        try:
            # Mock the API client methods directly
            with patch.object(self.cv.api_client, 'get_signed_upload_url') as mock_signed:
                with patch.object(self.cv.api_client, 'upload_file') as mock_upload:
                    mock_signed.return_value = "https://signed-url.com/upload?key=value"
                    mock_upload.return_value = None
                    
                    # Test the upload
                    result = self.cv.upload_file(temp_file)
                    
                    assert result == "https://signed-url.com/upload"
                    
                    # Verify calls
                    filename = os.path.basename(temp_file)
                    mock_signed.assert_called_once_with(filename)
                    mock_upload.assert_called_once_with(temp_file, "https://signed-url.com/upload?key=value")
            
        finally:
            os.unlink(temp_file)