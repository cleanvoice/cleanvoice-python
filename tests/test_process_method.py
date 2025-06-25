"""Tests for the process method with various scenarios."""

import pytest
from unittest.mock import Mock, patch, call
from cleanvoice import Cleanvoice, ApiError, ProcessingConfig
from cleanvoice.types import (
    CreateEditResponse,
    RetrieveEditResponse,
    EditResult,
    ProcessResult,
    EditStatistics,
    Transcription,
    SimpleTranscriptionParagraph,
    DetailedTranscription,
    Summarization,
    Chapter,
    ProcessingProgress,
)


@pytest.fixture
def cleanvoice_client():
    """Create a Cleanvoice client for testing."""
    return Cleanvoice({'api_key': 'test-key'})


@pytest.fixture
def mock_edit_result():
    """Create a mock edit result."""
    return EditResult(
        video=False,
        download_url='https://example.com/processed.mp3',
        filename='processed.mp3',
        statistics=EditStatistics(
            FILLER_SOUND=5,
            LONG_SILENCE=2,
            total_length=120.5,
            edited_length=110.2
        ),
        transcription=Transcription(
            paragraphs=[
                SimpleTranscriptionParagraph(text="Hello world", start=0.0, end=1.0),
                SimpleTranscriptionParagraph(text="This is a test", start=1.0, end=2.0)
            ],
            transcription=DetailedTranscription(words=[], paragraphs=[])
        ),
        summarization=Summarization(
            title="Test Audio",
            summary="A test recording",
            chapters=[
                Chapter(title="Introduction", start=0.0)
            ],
            summaries=["Summary 1"],
            key_learnings="Key learning",
            summary_of_summary="Brief summary",
            episode_description="Episode description"
        )
    )


def test_process_with_dict_config(cleanvoice_client):
    """Test process method with dictionary configuration."""
    with patch.object(cleanvoice_client, '_poll_for_completion') as mock_poll, \
         patch.object(cleanvoice_client, '_transform_result') as mock_transform, \
         patch.object(cleanvoice_client.api_client, 'create_edit') as mock_create:
        
        mock_create.return_value = CreateEditResponse(id='edit-123')
        mock_poll.return_value = Mock()
        mock_transform.return_value = Mock()
        
        result = cleanvoice_client.process(
            'https://example.com/audio.mp3',
            {
                'fillers': True,
                'normalize': True,
                'transcription': True
            }
        )
        
        mock_create.assert_called_once()
        mock_poll.assert_called_once_with('edit-123', progress_callback=None)
        mock_transform.assert_called_once()


def test_process_with_processing_config_object(cleanvoice_client):
    """Test process method with ProcessingConfig object."""
    config = ProcessingConfig(fillers=True, normalize=True)
    
    with patch.object(cleanvoice_client, '_poll_for_completion') as mock_poll, \
         patch.object(cleanvoice_client, '_transform_result') as mock_transform, \
         patch.object(cleanvoice_client.api_client, 'create_edit') as mock_create:
        
        mock_create.return_value = CreateEditResponse(id='edit-456')
        mock_poll.return_value = Mock()
        mock_transform.return_value = Mock()
        
        result = cleanvoice_client.process(
            'https://example.com/audio.mp3',
            config
        )
        
        mock_create.assert_called_once()
        mock_poll.assert_called_once_with('edit-456', progress_callback=None)


def test_process_with_progress_callback(cleanvoice_client):
    """Test process method with progress callback."""
    callback_calls = []
    
    def progress_callback(data):
        callback_calls.append(data)
    
    with patch.object(cleanvoice_client, '_poll_for_completion') as mock_poll, \
         patch.object(cleanvoice_client, '_transform_result') as mock_transform, \
         patch.object(cleanvoice_client.api_client, 'create_edit') as mock_create:
        
        mock_create.return_value = CreateEditResponse(id='edit-789')
        mock_poll.return_value = Mock()
        mock_transform.return_value = Mock()
        
        result = cleanvoice_client.process(
            'https://example.com/audio.mp3',
            {'fillers': True},
            progress_callback=progress_callback
        )
        
        mock_poll.assert_called_once_with('edit-789', progress_callback=progress_callback)


def test_process_auto_detect_video(cleanvoice_client):
    """Test process method auto-detects video files."""
    with patch('cleanvoice.cleanvoice.is_valid_video_file') as mock_is_video, \
         patch.object(cleanvoice_client, '_poll_for_completion') as mock_poll, \
         patch.object(cleanvoice_client, '_transform_result') as mock_transform, \
         patch.object(cleanvoice_client.api_client, 'create_edit') as mock_create:
        
        mock_is_video.return_value = True
        mock_create.return_value = CreateEditResponse(id='edit-video')
        mock_poll.return_value = Mock()
        mock_transform.return_value = Mock()
        
        result = cleanvoice_client.process(
            'https://example.com/video.mp4',
            {'fillers': True}
        )
        
        mock_is_video.assert_called_once_with('https://example.com/video.mp4')
        mock_create.assert_called_once()


def test_process_error_handling(cleanvoice_client):
    """Test process method error handling."""
    with patch.object(cleanvoice_client.api_client, 'create_edit') as mock_create:
        mock_create.side_effect = Exception("Network error")
        
        with pytest.raises(ApiError, match="An unknown error occurred during processing"):
            cleanvoice_client.process('https://example.com/audio.mp3', {'fillers': True})


def test_process_api_error_passthrough(cleanvoice_client):
    """Test process method passes through ApiError."""
    with patch.object(cleanvoice_client.api_client, 'create_edit') as mock_create:
        mock_create.side_effect = ApiError("Authentication failed", 401)
        
        with pytest.raises(ApiError, match="Authentication failed"):
            cleanvoice_client.process('https://example.com/audio.mp3', {'fillers': True})


def test_transform_result_success(cleanvoice_client, mock_edit_result):
    """Test _transform_result with successful edit result."""
    # Create a mock response with dict result (simulating actual API response)
    response = Mock()
    response.result = mock_edit_result.model_dump()
    
    result = cleanvoice_client._transform_result(response)
    
    assert isinstance(result, ProcessResult)
    assert result.audio.url == 'https://example.com/processed.mp3'
    assert result.audio.filename == 'processed.mp3'
    assert result.audio.statistics.FILLER_SOUND == 5
    assert result.transcript.text == "Hello world This is a test"
    assert result.transcript.title == "Test Audio"
    assert result.transcript.summary == "A test recording"
    assert len(result.transcript.chapters) == 1


def test_transform_result_no_result(cleanvoice_client):
    """Test _transform_result with no result data."""
    response = RetrieveEditResponse(
        status='SUCCESS',
        task_id='task-123',
        result=None
    )
    
    with pytest.raises(ApiError, match="Edit result not available"):
        cleanvoice_client._transform_result(response)


def test_transform_result_in_progress(cleanvoice_client):
    """Test _transform_result with in-progress result."""
    progress = ProcessingProgress(
        done=50,
        total=100,
        state='processing',
        phase=1,
        step=2,
        substep=3,
        job_name='test-job'
    )
    
    response = RetrieveEditResponse(
        status='PENDING',
        task_id='task-123',
        result=progress
    )
    
    with pytest.raises(ApiError, match="Edit is still in progress"):
        cleanvoice_client._transform_result(response)


def test_poll_for_completion_success(cleanvoice_client):
    """Test _poll_for_completion with successful completion."""
    edit_result = EditResult(
        video=False,
        download_url='https://example.com/result.mp3',
        filename='result.mp3',
        statistics=EditStatistics(
            FILLER_SOUND=0,
            LONG_SILENCE=0,
            total_length=60.0,
            edited_length=60.0
        )
    )
    
    success_response = RetrieveEditResponse(
        status='SUCCESS',
        task_id='task-123',
        result=edit_result
    )
    
    with patch.object(cleanvoice_client.api_client, 'retrieve_edit') as mock_retrieve:
        mock_retrieve.return_value = success_response
        
        result = cleanvoice_client._poll_for_completion('edit-123')
        
        assert result == success_response
        mock_retrieve.assert_called_once_with('edit-123')


def test_poll_for_completion_failure(cleanvoice_client):
    """Test _poll_for_completion with failure status."""
    failure_response = RetrieveEditResponse(
        status='FAILURE',
        task_id='task-123',
        result=None
    )
    
    with patch.object(cleanvoice_client.api_client, 'retrieve_edit') as mock_retrieve:
        mock_retrieve.return_value = failure_response
        
        with pytest.raises(ApiError, match="Edit processing failed"):
            cleanvoice_client._poll_for_completion('edit-123')


def test_poll_for_completion_with_callback(cleanvoice_client):
    """Test _poll_for_completion with progress callback."""
    progress1 = ProcessingProgress(done=25, total=100, state='pending', phase=1, step=1, substep=1, job_name='test')
    progress2 = ProcessingProgress(done=75, total=100, state='started', phase=1, step=2, substep=1, job_name='test')
    final_result = EditResult(video=False, download_url='test.mp3', filename='test.mp3', statistics=EditStatistics(FILLER_SOUND=0, LONG_SILENCE=0, total_length=60.0, edited_length=60.0))
    
    responses = [
        RetrieveEditResponse(status='PENDING', task_id='task-123', result=progress1),
        RetrieveEditResponse(status='STARTED', task_id='task-123', result=progress2),
        RetrieveEditResponse(status='SUCCESS', task_id='task-123', result=final_result)
    ]
    
    callback_calls = []
    def progress_callback(data):
        callback_calls.append(data)
    
    with patch.object(cleanvoice_client.api_client, 'retrieve_edit') as mock_retrieve, \
         patch('time.sleep') as mock_sleep:
        
        mock_retrieve.side_effect = responses
        
        result = cleanvoice_client._poll_for_completion(
            'edit-123',
            progress_callback=progress_callback
        )
        
        assert len(callback_calls) == 3
        assert callback_calls[0]['status'] == 'PENDING'
        assert callback_calls[1]['status'] == 'STARTED'
        assert callback_calls[2]['status'] == 'SUCCESS'
        assert all(call_data['edit_id'] == 'edit-123' for call_data in callback_calls)


def test_poll_for_completion_timeout(cleanvoice_client):
    """Test _poll_for_completion timeout after max attempts."""
    progress = ProcessingProgress(done=0, total=100, state='pending', phase=1, step=1, substep=1, job_name='test')
    pending_response = RetrieveEditResponse(
        status='PENDING',
        task_id='task-123',
        result=progress
    )
    
    with patch.object(cleanvoice_client.api_client, 'retrieve_edit') as mock_retrieve, \
         patch('time.sleep') as mock_sleep:
        
        mock_retrieve.return_value = pending_response
        
        with pytest.raises(ApiError, match="Edit processing timeout"):
            cleanvoice_client._poll_for_completion('edit-123', max_attempts=3)
        
        assert mock_retrieve.call_count == 3


def test_poll_for_completion_callback_error_handling(cleanvoice_client):
    """Test _poll_for_completion handles callback errors gracefully."""
    def failing_callback(data):
        raise Exception("Callback error")
    
    final_result = EditResult(video=False, download_url='test.mp3', filename='test.mp3', statistics=EditStatistics(FILLER_SOUND=0, LONG_SILENCE=0, total_length=60.0, edited_length=60.0))
    success_response = RetrieveEditResponse(
        status='SUCCESS',
        task_id='task-123',
        result=final_result
    )
    
    with patch.object(cleanvoice_client.api_client, 'retrieve_edit') as mock_retrieve:
        mock_retrieve.return_value = success_response
        
        # Should not raise exception despite callback failure
        result = cleanvoice_client._poll_for_completion(
            'edit-123',
            progress_callback=failing_callback
        )
        
        assert result == success_response