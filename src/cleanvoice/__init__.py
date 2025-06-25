"""
Official Python SDK for Cleanvoice AI - AI-powered audio processing

Example:
    from cleanvoice import Cleanvoice

    cv = Cleanvoice({'api_key': 'your-api-key'})
    result = cv.process('https://example.com/audio.mp3', {'fillers': True})
"""

from .cleanvoice import Cleanvoice
from .file_handler import (
    extract_audio_from_video,
    get_audio_info,
    get_file_info,
    get_video_info,
    is_url,
    is_valid_audio_file,
    is_valid_media_file,
    is_valid_video_file,
)
from .types import (
    ApiError,
    AudioInfo,
    Chapter,
    CleanvoiceConfig,
    DetailedTranscription,
    EditResult,
    EditStatistics,
    EditStatus,
    FileValidationError,
    ProcessingConfig,
    ProcessResult,
    RetrieveEditResponse,
    SimpleTranscriptionParagraph,
    Summarization,
    Transcription,
    TranscriptionParagraph,
    TranscriptionWord,
    VideoInfo,
)

__version__ = "1.0.0"
__all__ = [
    # Main class
    "Cleanvoice",
    # Configuration types
    "CleanvoiceConfig",
    "ProcessingConfig",
    # Result types
    "ProcessResult",
    "EditResult",
    "RetrieveEditResponse",
    # Status and data types
    "EditStatus",
    "EditStatistics",
    "Chapter",
    "Summarization",
    "TranscriptionWord",
    "TranscriptionParagraph",
    "DetailedTranscription",
    "SimpleTranscriptionParagraph",
    "Transcription",
    "AudioInfo",
    "VideoInfo",
    # Exceptions
    "ApiError",
    "FileValidationError",
    # Utility functions
    "is_url",
    "is_valid_audio_file",
    "is_valid_video_file",
    "is_valid_media_file",
    "get_audio_info",
    "get_video_info",
    "get_file_info",
    "extract_audio_from_video",
]
