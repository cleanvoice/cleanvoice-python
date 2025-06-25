"""Tests for file handling utilities."""

import pytest
from cleanvoice.file_handler import (
    is_url,
    is_valid_audio_file,
    is_valid_video_file,
    is_valid_media_file,
    validate_config,
)
from cleanvoice.types import FileValidationError


def test_is_url():
    """Test URL detection."""
    assert is_url('https://example.com/file.mp3') is True
    assert is_url('http://example.com/file.wav') is True
    assert is_url('ftp://example.com/file.mp4') is True
    assert is_url('/local/path/file.mp3') is False
    assert is_url('file.mp3') is False
    assert is_url('') is False


def test_is_valid_audio_file():
    """Test audio file validation."""
    assert is_valid_audio_file('file.mp3') is True
    assert is_valid_audio_file('file.wav') is True
    assert is_valid_audio_file('file.flac') is True
    assert is_valid_audio_file('file.m4a') is True
    assert is_valid_audio_file('https://example.com/audio.mp3') is True
    assert is_valid_audio_file('file.mp4') is False
    assert is_valid_audio_file('file.txt') is False


def test_is_valid_video_file():
    """Test video file validation."""
    assert is_valid_video_file('file.mp4') is True
    assert is_valid_video_file('file.avi') is True
    assert is_valid_video_file('file.mov') is True
    assert is_valid_video_file('file.mkv') is True
    assert is_valid_video_file('https://example.com/video.mp4') is True
    assert is_valid_video_file('file.mp3') is False
    assert is_valid_video_file('file.txt') is False


def test_is_valid_media_file():
    """Test media file validation."""
    assert is_valid_media_file('file.mp3') is True
    assert is_valid_media_file('file.mp4') is True
    assert is_valid_media_file('file.wav') is True
    assert is_valid_media_file('file.avi') is True
    assert is_valid_media_file('file.txt') is False


def test_validate_config():
    """Test configuration validation."""
    # Valid configs
    validate_config({})
    validate_config({'fillers': True})
    validate_config({'transcription': True, 'summarize': True})
    
    # Invalid configs
    with pytest.raises(FileValidationError, match="Summarization requires transcription"):
        validate_config({'summarize': True})
    
    with pytest.raises(FileValidationError, match="Social content requires summarization"):
        validate_config({'social_content': True})
    
    with pytest.raises(FileValidationError, match="mute_lufs must be a negative number"):
        validate_config({'mute_lufs': 5})
    
    with pytest.raises(FileValidationError, match="target_lufs must be a negative number"):
        validate_config({'target_lufs': 10})