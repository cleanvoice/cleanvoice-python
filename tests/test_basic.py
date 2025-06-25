"""Basic tests for Cleanvoice SDK."""

import pytest
from unittest.mock import Mock, patch
from cleanvoice import Cleanvoice, ApiError, FileValidationError


def test_cleanvoice_init():
    """Test Cleanvoice initialization."""
    cv = Cleanvoice({'api_key': 'test-key'})
    assert cv.api_client.config.api_key == 'test-key'


def test_cleanvoice_init_no_api_key():
    """Test Cleanvoice initialization without API key."""
    with pytest.raises(ValueError, match="API key is required"):
        Cleanvoice({'api_key': ''})


def test_check_auth():
    """Test authentication check."""
    cv = Cleanvoice({'api_key': 'test-key'})
    
    with patch.object(cv.api_client, 'check_auth') as mock_auth:
        mock_auth.return_value = {'user': 'test@example.com'}
        
        result = cv.check_auth()
        assert result == {'user': 'test@example.com'}
        mock_auth.assert_called_once()


def test_create_edit():
    """Test creating an edit job."""
    cv = Cleanvoice({'api_key': 'test-key'})
    
    with patch.object(cv.api_client, 'create_edit') as mock_create:
        from cleanvoice.types import CreateEditResponse
        mock_create.return_value = CreateEditResponse(id='test-edit-id')
        
        edit_id = cv.create_edit(
            'https://example.com/audio.mp3',
            {'fillers': True}
        )
        
        assert edit_id == 'test-edit-id'
        mock_create.assert_called_once()


def test_get_edit():
    """Test getting edit status."""
    cv = Cleanvoice({'api_key': 'test-key'})
    
    with patch.object(cv.api_client, 'retrieve_edit') as mock_retrieve:
        from cleanvoice.types import RetrieveEditResponse
        mock_response = RetrieveEditResponse(
            status='SUCCESS',
            task_id='test-task-id'
        )
        mock_retrieve.return_value = mock_response
        
        result = cv.get_edit('test-edit-id')
        assert result.status == 'SUCCESS'
        mock_retrieve.assert_called_once_with('test-edit-id')


def test_api_error_handling():
    """Test API error handling."""
    cv = Cleanvoice({'api_key': 'test-key'})
    
    with patch.object(cv.api_client, 'check_auth') as mock_auth:
        mock_auth.side_effect = ApiError("Authentication failed", 401)
        
        with pytest.raises(ApiError) as exc_info:
            cv.check_auth()
        
        assert "Authentication failed" in str(exc_info.value)
        assert exc_info.value.status_code == 401