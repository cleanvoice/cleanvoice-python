"""Advanced tests for file handling utilities."""

import pytest
from unittest.mock import Mock, patch, mock_open
import tempfile
import os
from cleanvoice.file_handler import (
    normalize_file_input,
    get_audio_info,
    get_video_info,
    get_file_info,
    extract_audio_from_video,
)
from cleanvoice.types import FileValidationError, AudioInfo, VideoInfo


def test_normalize_file_input_url():
    """Test normalize_file_input with URL."""
    url = 'https://example.com/audio.mp3'
    result = normalize_file_input(url)
    assert result == url


def test_normalize_file_input_local_file():
    """Test normalize_file_input with local file path."""
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
        temp_path = temp_file.name
        
    try:
        result = normalize_file_input(temp_path)
        assert result.startswith('file://')
        assert temp_path in result
    finally:
        os.unlink(temp_path)


def test_normalize_file_input_nonexistent_file():
    """Test normalize_file_input with nonexistent file."""
    with pytest.raises(FileValidationError, match="File does not exist"):
        normalize_file_input('/nonexistent/path/audio.mp3')


def test_normalize_file_input_empty_string():
    """Test normalize_file_input with empty string."""
    with pytest.raises(FileValidationError, match="File input cannot be empty"):
        normalize_file_input('')


def test_normalize_file_input_none():
    """Test normalize_file_input with None."""
    with pytest.raises(FileValidationError, match="File input cannot be empty"):
        normalize_file_input(None)


def test_normalize_file_input_unsupported_format():
    """Test normalize_file_input with unsupported file format."""
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
        temp_path = temp_file.name
        
    try:
        with pytest.raises(FileValidationError, match="Unsupported file format"):
            normalize_file_input(temp_path)
    finally:
        os.unlink(temp_path)


@patch('librosa.load')
@patch('librosa.get_duration')
@patch('soundfile.info')
def test_get_audio_info_success(mock_sf_info, mock_duration, mock_load):
    """Test get_audio_info with successful audio file."""
    # Mock soundfile info
    mock_sf_info.return_value = Mock(
        samplerate=44100,
        channels=2,
        frames=88200
    )
    
    # Mock librosa duration
    mock_duration.return_value = 2.0
    
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
        temp_path = temp_file.name
        
    try:
        result = get_audio_info(temp_path)
        
        assert isinstance(result, AudioInfo)
        assert result.duration == 2.0
        assert result.sample_rate == 44100
        assert result.channels == 2
        assert result.file_path == temp_path
    finally:
        os.unlink(temp_path)


@patch('librosa.load')
def test_get_audio_info_error(mock_load):
    """Test get_audio_info with error loading file."""
    mock_load.side_effect = Exception("Cannot load audio file")
    
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
        temp_path = temp_file.name
        
    try:
        with pytest.raises(FileValidationError, match="Error reading audio file"):
            get_audio_info(temp_path)
    finally:
        os.unlink(temp_path)


def test_get_audio_info_nonexistent_file():
    """Test get_audio_info with nonexistent file."""
    with pytest.raises(FileValidationError, match="File does not exist"):
        get_audio_info('/nonexistent/audio.mp3')


@patch('av.open')
def test_get_video_info_success(mock_av_open):
    """Test get_video_info with successful video file."""
    # Mock PyAV container
    mock_container = Mock()
    mock_video_stream = Mock()
    mock_video_stream.width = 1920
    mock_video_stream.height = 1080
    mock_video_stream.average_rate = Mock()
    mock_video_stream.average_rate.numerator = 30
    mock_video_stream.average_rate.denominator = 1
    
    mock_audio_stream = Mock()
    
    mock_container.streams.video = [mock_video_stream]
    mock_container.streams.audio = [mock_audio_stream]
    mock_container.duration = 5000000  # 5 seconds in microseconds
    
    mock_av_open.return_value.__enter__.return_value = mock_container
    
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
        temp_path = temp_file.name
        
    try:
        result = get_video_info(temp_path)
        
        assert isinstance(result, VideoInfo)
        assert result.duration == 5.0
        assert result.width == 1920
        assert result.height == 1080
        assert result.fps == 30.0
        assert result.has_audio is True
        assert result.file_path == temp_path
    finally:
        os.unlink(temp_path)


@patch('av.open')
def test_get_video_info_no_audio(mock_av_open):
    """Test get_video_info with video file without audio."""
    mock_container = Mock()
    mock_video_stream = Mock()
    mock_video_stream.width = 1280
    mock_video_stream.height = 720
    mock_video_stream.average_rate = Mock()
    mock_video_stream.average_rate.numerator = 24
    mock_video_stream.average_rate.denominator = 1
    
    mock_container.streams.video = [mock_video_stream]
    mock_container.streams.audio = []
    mock_container.duration = 3000000
    
    mock_av_open.return_value.__enter__.return_value = mock_container
    
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
        temp_path = temp_file.name
        
    try:
        result = get_video_info(temp_path)
        
        assert result.has_audio is False
        assert result.width == 1280
        assert result.height == 720
        assert result.fps == 24.0
    finally:
        os.unlink(temp_path)


@patch('av.open')
def test_get_video_info_error(mock_av_open):
    """Test get_video_info with error loading file."""
    mock_av_open.side_effect = Exception("Cannot open video file")
    
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
        temp_path = temp_file.name
        
    try:
        with pytest.raises(FileValidationError, match="Error reading video file"):
            get_video_info(temp_path)
    finally:
        os.unlink(temp_path)


def test_get_video_info_nonexistent_file():
    """Test get_video_info with nonexistent file."""
    with pytest.raises(FileValidationError, match="File does not exist"):
        get_video_info('/nonexistent/video.mp4')


@patch('cleanvoice.file_handler.get_audio_info')
def test_get_file_info_audio(mock_get_audio):
    """Test get_file_info with audio file."""
    mock_audio_info = AudioInfo(
        duration=3.5,
        sample_rate=44100,
        channels=2,
        file_path='test.mp3'
    )
    mock_get_audio.return_value = mock_audio_info
    
    result = get_file_info('test.mp3')
    assert result == mock_audio_info
    mock_get_audio.assert_called_once_with('test.mp3')


@patch('cleanvoice.file_handler.get_video_info')
def test_get_file_info_video(mock_get_video):
    """Test get_file_info with video file."""
    mock_video_info = VideoInfo(
        duration=10.0,
        width=1920,
        height=1080,
        fps=30.0,
        has_audio=True,
        file_path='test.mp4'
    )
    mock_get_video.return_value = mock_video_info
    
    result = get_file_info('test.mp4')
    assert result == mock_video_info
    mock_get_video.assert_called_once_with('test.mp4')


def test_get_file_info_unsupported():
    """Test get_file_info with unsupported file format."""
    with pytest.raises(FileValidationError, match="Unsupported file format"):
        get_file_info('test.txt')


@patch('av.open')
@patch('soundfile.write')
def test_extract_audio_from_video_success(mock_sf_write, mock_av_open):
    """Test extract_audio_from_video with successful extraction."""
    # Mock PyAV container and audio stream
    mock_container = Mock()
    mock_audio_stream = Mock()
    mock_frame = Mock()
    mock_frame.to_ndarray.return_value = [[0.1, 0.2], [0.3, 0.4]]  # Mock audio data
    
    mock_audio_stream.decode.return_value = [mock_frame]
    mock_audio_stream.rate = 44100
    mock_container.streams.audio = [mock_audio_stream]
    
    mock_av_open.return_value.__enter__.return_value = mock_container
    
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
        video_path = temp_video.name
        
    try:
        output_path = extract_audio_from_video(video_path)
        
        assert output_path.endswith('.wav')
        mock_sf_write.assert_called_once()
        
        # Test with custom output path
        custom_output = 'custom_audio.wav'
        result = extract_audio_from_video(video_path, custom_output)
        assert result == custom_output
        
    finally:
        os.unlink(video_path)


@patch('av.open')
def test_extract_audio_from_video_no_audio(mock_av_open):
    """Test extract_audio_from_video with video file without audio."""
    mock_container = Mock()
    mock_container.streams.audio = []
    
    mock_av_open.return_value.__enter__.return_value = mock_container
    
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
        video_path = temp_video.name
        
    try:
        with pytest.raises(FileValidationError, match="No audio stream found"):
            extract_audio_from_video(video_path)
    finally:
        os.unlink(video_path)


@patch('av.open')
def test_extract_audio_from_video_error(mock_av_open):
    """Test extract_audio_from_video with error during extraction."""
    mock_av_open.side_effect = Exception("Cannot open video file")
    
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
        video_path = temp_video.name
        
    try:
        with pytest.raises(FileValidationError, match="Error extracting audio"):
            extract_audio_from_video(video_path)
    finally:
        os.unlink(video_path)


def test_extract_audio_from_video_nonexistent():
    """Test extract_audio_from_video with nonexistent file."""
    with pytest.raises(FileValidationError, match="File does not exist"):
        extract_audio_from_video('/nonexistent/video.mp4')


def test_extract_audio_from_video_invalid_format():
    """Test extract_audio_from_video with invalid file format."""
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
        file_path = temp_file.name
        
    try:
        with pytest.raises(FileValidationError, match="is not a valid video file"):
            extract_audio_from_video(file_path)
    finally:
        os.unlink(file_path)