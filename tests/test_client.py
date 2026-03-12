import json
import os
from unittest.mock import Mock, patch

import pytest
import requests

from cleanvoice.client import ApiClient
from cleanvoice.types import (
    ApiError,
    CleanvoiceConfig,
    CreateEditRequest,
    CreateEditResponse,
    EditInput,
    ProcessingConfig,
    RetrieveEditResponse,
)


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
    assert client.session.headers['X-API-Key'] == 'test-key'
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

    with patch("cleanvoice.client.time.sleep") as mock_sleep:
        with pytest.raises(ApiError) as exc_info:
            api_client._make_request('GET', '/test')

    assert 'Request failed' in str(exc_info.value)
    assert exc_info.value.status_code is None
    assert mock_request.call_count == 4
    assert mock_sleep.call_count == 3


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

    with pytest.raises(ApiError, match="Invalid JSON response from API"):
        api_client._make_request('GET', '/test')


@patch('requests.Session.request')
def test_make_request_retries_connection_error_then_success(mock_request, api_client):
    """Transient connection errors should retry before succeeding."""
    success_response = Mock()
    success_response.status_code = 200
    success_response.json.return_value = {'success': True}
    mock_request.side_effect = [
        requests.exceptions.ConnectionError("temporary outage"),
        success_response,
    ]

    with patch("cleanvoice.client.time.sleep") as mock_sleep:
        result = api_client._make_request('GET', '/test')

    assert result == {'success': True}
    assert mock_request.call_count == 2
    mock_sleep.assert_called_once()


@patch('requests.Session.request')
def test_create_edit_retries_temporary_503_then_success(mock_request, api_client):
    """Create edit should tolerate a brief 503 during server restart."""
    edit_request = CreateEditRequest(
        input=EditInput(
            files=['https://example.com/audio.mp3'],
            config=ProcessingConfig(fillers=True),
        )
    )
    unavailable_response = Mock()
    unavailable_response.status_code = 503
    unavailable_response.json.return_value = {'message': 'Service unavailable'}
    unavailable_response.text = 'Service unavailable'

    success_response = Mock()
    success_response.status_code = 200
    success_response.json.return_value = {'id': 'edit-123'}
    mock_request.side_effect = [unavailable_response, success_response]

    with patch("cleanvoice.client.time.sleep") as mock_sleep:
        response = api_client.create_edit(edit_request)

    assert response.id == 'edit-123'
    assert mock_request.call_count == 2
    mock_sleep.assert_called_once()


@patch('requests.Session.request')
def test_check_auth_retries_temporary_503_then_success(mock_request, api_client):
    """check_auth should retry transient service outages."""
    unavailable_response = Mock()
    unavailable_response.status_code = 503
    unavailable_response.json.return_value = {'message': 'Service unavailable'}
    unavailable_response.text = 'Service unavailable'

    success_response = Mock()
    success_response.status_code = 200
    success_response.json.return_value = {'user': 'test@example.com'}
    mock_request.side_effect = [unavailable_response, success_response]

    with patch("cleanvoice.client.time.sleep") as mock_sleep:
        response = api_client.check_auth()

    assert response["user"] == 'test@example.com'
    assert mock_request.call_count == 2
    mock_sleep.assert_called_once()


@patch('requests.Session.request')
def test_retrieve_edit_retries_temporary_503_then_success(mock_request, api_client):
    """retrieve_edit should retry a transient 503 and return the final job state."""
    unavailable_response = Mock()
    unavailable_response.status_code = 503
    unavailable_response.json.return_value = {'message': 'Service unavailable'}
    unavailable_response.text = 'Service unavailable'

    success_response = Mock()
    success_response.status_code = 200
    success_response.json.return_value = {
        'status': 'SUCCESS',
        'task_id': 'task-456',
        'result': {
            'video': False,
            'download_url': 'https://example.com/result.mp3',
            'filename': 'result.mp3',
            'statistics': {'FILLER_SOUND': 0},
            'social_content': [],
            'merged_audio_url': [],
            'timestamps_markers_urls': None,
            'waveform_result': None,
        },
    }
    mock_request.side_effect = [unavailable_response, success_response]

    with patch("cleanvoice.client.time.sleep") as mock_sleep:
        result = api_client.retrieve_edit('edit-123')

    assert result.status == 'SUCCESS'
    assert mock_request.call_count == 2
    mock_sleep.assert_called_once()


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
            endpoint='/edits',
            data=edit_request.model_dump(by_alias=True, exclude_none=True)
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
            endpoint='/edits/edit-123'
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
            endpoint='/account',
            base_url='https://api.cleanvoice.ai/v1'
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

    with patch("cleanvoice.client.time.sleep"):
        for status_code in status_codes:
            mock_response = Mock()
            mock_response.status_code = status_code
            mock_response.json.return_value = {'message': f'Error {status_code}'}
            mock_response.text = f'Error {status_code}'
            mock_request.return_value = mock_response

            with pytest.raises(ApiError) as exc_info:
                api_client._make_request('GET', '/test')

            assert exc_info.value.status_code == status_code