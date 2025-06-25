"""Tests for the ApiClient class."""

import pytest
import json
from unittest.mock import Mock, patch
import requests
from cleanvoice.client import ApiClient
from cleanvoice.types import (
    CleanvoiceConfig,
    CreateEditRequest,
    CreateEditResponse,
    RetrieveEditResponse,
    EditInput,
    ProcessingConfig,
    ApiError,
)
import os

@pytest.fixture
def api_client():
    """Create an ApiClient for testing."""
    config = CleanvoiceConfig(api_key='test-api-key')
    return ApiClient(config)


def test_api_client_init():
    """Test ApiClient initialization."""
    config = CleanvoiceConfig(
        api_key='test-key',
        base_url='https://custom.api.url',
        timeout=30
    )
    client = ApiClient(config)
    
    assert client.config == config
    assert client.session.headers['Authorization'] == 'Bearer test-key'
    assert client.session.headers['Content-Type'] == 'application/json'
    assert 'cleanvoice-python-sdk' in client.session.headers['User-Agent']


@patch('requests.Session.request')
def test_make_request_success(mock_request, api_client):
    """Test successful API request."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'success': True}
    mock_request.return_value = mock_response
    
    result = api_client._make_request('POST', '/test', {'data': 'test'})
    
    assert result == {'success': True}
    mock_request.assert_called_once_with(
        method='POST',
        url='https://api.cleanvoice.ai/v2/test',
        json={'data': 'test'},
        timeout=60
    )


@patch('requests.Session.request')
def test_make_request_with_custom_config(mock_request):
    """Test API request with custom configuration."""
    config = CleanvoiceConfig(
        api_key='custom-key',
        base_url='https://custom.api.url',
        timeout=30
    )
    client = ApiClient(config)
    
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'data': 'response'}
    mock_request.return_value = mock_response
    
    result = client._make_request('GET', '/custom')
    
    mock_request.assert_called_once_with(
        method='GET',
        url='https://custom.api.url/custom',
        json=None,
        timeout=30
    )


@patch('requests.Session.request')
def test_make_request_api_error(mock_request, api_client):
    """Test API request that returns an error."""
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        'message': 'Invalid request',
        'code': 'INVALID_REQUEST'
    }
    mock_request.return_value = mock_response
    
    with pytest.raises(ApiError) as exc_info:
        api_client._make_request('POST', '/test', {'invalid': 'data'})
    
    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == 'INVALID_REQUEST'
    assert 'Invalid request' in str(exc_info.value)


@patch('requests.Session.request')
def test_make_request_401_unauthorized(mock_request, api_client):
    """Test 401 unauthorized response."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.json.return_value = {'message': 'Unauthorized'}
    mock_request.return_value = mock_response
    
    with pytest.raises(ApiError) as exc_info:
        api_client._make_request('GET', '/protected')
    
    assert exc_info.value.status_code == 401
    assert 'Unauthorized' in str(exc_info.value)


@patch('requests.Session.request')
def test_make_request_network_error(mock_request, api_client):
    """Test network error during request."""
    mock_request.side_effect = requests.exceptions.ConnectionError("Network error")
    
    with pytest.raises(ApiError) as exc_info:
        api_client._make_request('GET', '/test')
    
    assert 'Request failed' in str(exc_info.value)
    assert exc_info.value.status_code is None


@patch('requests.Session.request')
def test_make_request_timeout(mock_request, api_client):
    """Test timeout during request."""
    mock_request.side_effect = requests.exceptions.Timeout("Request timeout")
    
    with pytest.raises(ApiError) as exc_info:
        api_client._make_request('GET', '/test')
    
    assert 'Request failed' in str(exc_info.value)


@patch('requests.Session.request')
def test_make_request_invalid_json(mock_request, api_client):
    """Test response with invalid JSON."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
    mock_response.text = "Invalid response"
    mock_request.return_value = mock_response
    
    with pytest.raises(json.JSONDecodeError):
        api_client._make_request('GET', '/test')


def test_create_edit(api_client):
    """Test create_edit method."""
    edit_request = CreateEditRequest(
        input=EditInput(
            files=[os.getenv('CLEANVOICE_TEST_AUDIO_URL', 'https://example.com/audio.mp3')],
            config=ProcessingConfig(fillers=True)
        )
    )
    
    expected_response = {'id': 'edit-123'}
    
    with patch.object(api_client, '_make_request') as mock_request:
        mock_request.return_value = expected_response
        
        result = api_client.create_edit(edit_request)
        
        assert isinstance(result, CreateEditResponse)
        assert result.id == 'edit-123'
        mock_request.assert_called_once_with(
            method='POST',
            endpoint='/edit',
            data=edit_request.model_dump(exclude_none=True)
        )


def test_retrieve_edit(api_client):
    """Test retrieve_edit method."""
    expected_response = {
        'status': 'SUCCESS',
        'task_id': 'task-456',
        'result': {
            'video': False,
            'download_url': 'https://example.com/result.mp3',
            'filename': 'result.mp3',
            'statistics': {
                'FILLER_SOUND': 0,
                'LONG_SILENCE': 0,
                'total_length': 60.0,
                'edited_length': 60.0
            }
        }
    }
    
    with patch.object(api_client, '_make_request') as mock_request:
        mock_request.return_value = expected_response
        
        result = api_client.retrieve_edit('edit-123')
        
        assert isinstance(result, RetrieveEditResponse)
        assert result.status == 'SUCCESS'
        assert result.task_id == 'task-456'
        mock_request.assert_called_once_with(
            method='GET',
            endpoint='/edit/edit-123'
        )


def test_check_auth(api_client):
    """Test check_auth method."""
    expected_response = {
        'user': 'test@example.com',
        'account_type': 'premium',
        'credits_remaining': 100
    }
    
    with patch.object(api_client, '_make_request') as mock_request:
        mock_request.return_value = expected_response
        
        result = api_client.check_auth()
        
        assert result == expected_response
        mock_request.assert_called_once_with(
            method='GET',
            endpoint='/auth/check'
        )


@patch('requests.Session.request')
def test_error_response_structure_variations(mock_request, api_client):
    """Test different error response structures."""
    # Test error with message field
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.json.return_value = {'message': 'Simple error message'}
    mock_request.return_value = mock_response
    
    with pytest.raises(ApiError) as exc_info:
        api_client._make_request('POST', '/test')
    
    assert 'Simple error message' in str(exc_info.value)
    
    # Test error without message field (fallback to HTTP status)
    mock_response.json.return_value = {'some_other_field': 'data'}
    
    with pytest.raises(ApiError) as exc_info:
        api_client._make_request('POST', '/test')
    
    assert 'HTTP 400' in str(exc_info.value)


@patch('requests.Session.request')
def test_http_status_error_codes(mock_request, api_client):
    """Test various HTTP status codes."""
    status_codes = [400, 401, 403, 404, 429, 500, 502, 503]
    
    for status_code in status_codes:
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.json.return_value = {'message': f'Error {status_code}'}
        mock_request.return_value = mock_response
        
        with pytest.raises(ApiError) as exc_info:
            api_client._make_request('GET', '/test')
        
        assert exc_info.value.status_code == status_code