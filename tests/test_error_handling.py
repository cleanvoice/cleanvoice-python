"""Tests for error handling and edge cases."""

import pytest
from unittest.mock import Mock, patch
from cleanvoice import Cleanvoice, ApiError, FileValidationError, ProcessingConfig
from cleanvoice.types import CreateEditResponse, RetrieveEditResponse


@pytest.fixture
def cleanvoice_client():
    """Create a Cleanvoice client for testing."""
    return Cleanvoice({'api_key': 'test-key'})


def test_cleanvoice_init_empty_api_key():
    """Test Cleanvoice initialization with empty API key."""
    with pytest.raises(ValueError, match="API key is required"):
        Cleanvoice({'api_key': ''})


def test_cleanvoice_init_none_api_key():
    """Test Cleanvoice initialization with None API key."""
    with pytest.raises(Exception):  # Pydantic validation error
        Cleanvoice({'api_key': None})


def test_cleanvoice_init_missing_api_key():
    """Test Cleanvoice initialization with missing API key."""
    with pytest.raises(Exception):  # Pydantic validation error for missing required field
        Cleanvoice({})


def test_process_invalid_config_summarize_without_transcription(cleanvoice_client):
    """Test process with invalid config: summarize without transcription."""
    with pytest.raises(ApiError, match="An unknown error occurred during processing"):
        cleanvoice_client.process(
            'https://example.com/audio.mp3',
            {'summarize': True}
        )


def test_process_invalid_config_social_content_without_summarize(cleanvoice_client):
    """Test process with invalid config: social_content without summarize."""
    with pytest.raises(ApiError, match="An unknown error occurred during processing"):
        cleanvoice_client.process(
            'https://example.com/audio.mp3',
            {'social_content': True}
        )


def test_process_invalid_config_positive_mute_lufs(cleanvoice_client):
    """Test process with invalid config: positive mute_lufs."""
    with pytest.raises(ApiError, match="An unknown error occurred during processing"):
        cleanvoice_client.process(
            'https://example.com/audio.mp3',
            {'mute_lufs': 5}
        )


def test_process_invalid_config_positive_target_lufs(cleanvoice_client):
    """Test process with invalid config: positive target_lufs."""
    with pytest.raises(ApiError, match="An unknown error occurred during processing"):
        cleanvoice_client.process(
            'https://example.com/audio.mp3',
            {'target_lufs': 10}
        )


def test_create_edit_invalid_config(cleanvoice_client):
    """Test create_edit with invalid configuration."""
    with pytest.raises(ApiError, match="An unknown error occurred while creating edit"):
        cleanvoice_client.create_edit(
            'https://example.com/audio.mp3',
            {'mute_lufs': 20}  # Should be negative
        )


def test_process_api_client_error(cleanvoice_client):
    """Test process method when API client raises error."""
    with patch.object(cleanvoice_client.api_client, 'create_edit') as mock_create:
        mock_create.side_effect = ApiError("Server error", 500)
        
        with pytest.raises(ApiError, match="Server error"):
            cleanvoice_client.process('https://example.com/audio.mp3', {'fillers': True})


def test_create_edit_api_client_error(cleanvoice_client):
    """Test create_edit method when API client raises error."""
    with patch.object(cleanvoice_client.api_client, 'create_edit') as mock_create:
        mock_create.side_effect = ApiError("Rate limit exceeded", 429)
        
        with pytest.raises(ApiError, match="Rate limit exceeded"):
            cleanvoice_client.create_edit('https://example.com/audio.mp3', {'fillers': True})


def test_get_edit_api_client_error(cleanvoice_client):
    """Test get_edit method when API client raises error."""
    with patch.object(cleanvoice_client.api_client, 'retrieve_edit') as mock_retrieve:
        mock_retrieve.side_effect = ApiError("Edit not found", 404)
        
        with pytest.raises(ApiError, match="Edit not found"):
            cleanvoice_client.get_edit('nonexistent-edit-id')


def test_get_edit_unexpected_error(cleanvoice_client):
    """Test get_edit method with unexpected error."""
    with patch.object(cleanvoice_client.api_client, 'retrieve_edit') as mock_retrieve:
        mock_retrieve.side_effect = Exception("Unexpected error")
        
        with pytest.raises(ApiError, match="An unknown error occurred while retrieving edit"):
            cleanvoice_client.get_edit('edit-123')


def test_check_auth_api_client_error(cleanvoice_client):
    """Test check_auth method when API client raises error."""
    with patch.object(cleanvoice_client.api_client, 'check_auth') as mock_auth:
        mock_auth.side_effect = ApiError("Invalid API key", 401)
        
        with pytest.raises(ApiError, match="Invalid API key"):
            cleanvoice_client.check_auth()


def test_check_auth_unexpected_error(cleanvoice_client):
    """Test check_auth method with unexpected error."""
    with patch.object(cleanvoice_client.api_client, 'check_auth') as mock_auth:
        mock_auth.side_effect = Exception("Network timeout")
        
        with pytest.raises(ApiError, match="Authentication check failed"):
            cleanvoice_client.check_auth()


def test_poll_for_completion_retrieve_error(cleanvoice_client):
    """Test _poll_for_completion when retrieve_edit raises error."""
    with patch.object(cleanvoice_client.api_client, 'retrieve_edit') as mock_retrieve:
        mock_retrieve.side_effect = ApiError("Network error", 500)
        
        with pytest.raises(ApiError, match="Network error"):
            cleanvoice_client._poll_for_completion('edit-123')


def test_process_with_invalid_pydantic_config(cleanvoice_client):
    """Test process with invalid ProcessingConfig construction."""
    with pytest.raises(Exception):  # Pydantic validation error
        cleanvoice_client.process(
            'https://example.com/audio.mp3',
            {'export_format': 'invalid_format'}  # Not in allowed literals
        )


def test_create_edit_with_invalid_pydantic_config(cleanvoice_client):
    """Test create_edit with invalid ProcessingConfig construction.""" 
    with pytest.raises(Exception):  # Pydantic validation error
        cleanvoice_client.create_edit(
            'https://example.com/audio.mp3',
            {'export_format': 'xyz'}  # Not in allowed literals
        )


def test_process_empty_file_input(cleanvoice_client):
    """Test process with empty file input."""
    with patch('cleanvoice.cleanvoice.normalize_file_input') as mock_normalize:
        mock_normalize.side_effect = FileValidationError("File input cannot be empty")
        
        with pytest.raises(ApiError, match="An unknown error occurred during processing"):
            cleanvoice_client.process('', {'fillers': True})


def test_create_edit_empty_file_input(cleanvoice_client):
    """Test create_edit with empty file input."""
    with patch('cleanvoice.cleanvoice.normalize_file_input') as mock_normalize:
        mock_normalize.side_effect = FileValidationError("File input cannot be empty")
        
        with pytest.raises(ApiError, match="An unknown error occurred while creating edit"):
            cleanvoice_client.create_edit('', {'fillers': True})


def test_process_none_config_handling(cleanvoice_client):
    """Test process method handles None config correctly."""
    with patch.object(cleanvoice_client, '_poll_for_completion') as mock_poll, \
         patch.object(cleanvoice_client, '_transform_result') as mock_transform, \
         patch.object(cleanvoice_client.api_client, 'create_edit') as mock_create:
        
        mock_create.return_value = CreateEditResponse(id='edit-none')
        mock_poll.return_value = Mock()
        mock_transform.return_value = Mock()
        
        # Should not raise error with None config
        result = cleanvoice_client.process('https://example.com/audio.mp3', None)
        
        mock_create.assert_called_once()


def test_create_edit_none_config_handling(cleanvoice_client):
    """Test create_edit method handles None config correctly."""
    with patch.object(cleanvoice_client.api_client, 'create_edit') as mock_create:
        mock_create.return_value = CreateEditResponse(id='edit-none')
        
        # Should not raise error with None config
        result = cleanvoice_client.create_edit('https://example.com/audio.mp3', None)
        
        assert result == 'edit-none'
        mock_create.assert_called_once()


def test_transform_result_malformed_edit_result(cleanvoice_client):
    """Test _transform_result with malformed edit result."""
    # Create a mock response with malformed dict result
    response = Mock()
    response.result = {'invalid': 'structure'}  # Missing required fields like download_url
    
    with pytest.raises(Exception):  # Should raise validation error when creating EditResult
        cleanvoice_client._transform_result(response)


def test_process_value_error_passthrough(cleanvoice_client):
    """Test process method passes through ValueError."""
    with patch('cleanvoice.cleanvoice.validate_config') as mock_validate:
        mock_validate.side_effect = ValueError("Invalid value")
        
        with pytest.raises(ValueError, match="Invalid value"):
            cleanvoice_client.process('https://example.com/audio.mp3', {'fillers': True})


def test_create_edit_value_error_passthrough(cleanvoice_client):
    """Test create_edit method passes through ValueError."""
    with patch('cleanvoice.cleanvoice.validate_config') as mock_validate:
        mock_validate.side_effect = ValueError("Invalid configuration value")
        
        with pytest.raises(ValueError, match="Invalid configuration value"):
            cleanvoice_client.create_edit('https://example.com/audio.mp3', {'fillers': True})


def test_api_error_attributes():
    """Test ApiError class attributes and behavior."""
    # Test with all parameters
    error = ApiError("Test message", 400, "TEST_CODE")
    assert str(error) == "Test message"
    assert error.status_code == 400
    assert error.error_code == "TEST_CODE"
    
    # Test with minimal parameters
    error_minimal = ApiError("Simple error")
    assert str(error_minimal) == "Simple error"
    assert error_minimal.status_code is None
    assert error_minimal.error_code is None


def test_file_validation_error():
    """Test FileValidationError class."""
    error = FileValidationError("Invalid file format")
    assert str(error) == "Invalid file format"
    assert isinstance(error, Exception)


def test_cleanvoice_config_dict_handling():
    """Test Cleanvoice handles both dict and CleanvoiceConfig objects."""
    # Test with dict
    cv1 = Cleanvoice({'api_key': 'test-key'})
    assert cv1.api_client.config.api_key == 'test-key'
    
    # Test with CleanvoiceConfig object
    from cleanvoice.types import CleanvoiceConfig
    config = CleanvoiceConfig(api_key='test-key-2')
    cv2 = Cleanvoice(config)
    assert cv2.api_client.config.api_key == 'test-key-2'