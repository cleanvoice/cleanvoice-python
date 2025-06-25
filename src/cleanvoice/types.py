"""Type definitions for the Cleanvoice SDK."""

from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


class ProcessingConfig(BaseModel):
    """Configuration options for audio processing."""

    video: Optional[bool] = None
    send_email: Optional[bool] = None
    long_silences: Optional[bool] = None
    stutters: Optional[bool] = None
    fillers: Optional[bool] = None
    mouth_sounds: Optional[bool] = None
    hesitations: Optional[bool] = None
    muted: Optional[bool] = None
    remove_noise: Optional[bool] = None
    keep_music: Optional[bool] = None
    breath: Optional[bool] = None
    normalize: Optional[bool] = None
    autoeq: Optional[bool] = None
    sound_studio: Optional[bool] = None
    mute_lufs: Optional[float] = None
    target_lufs: Optional[float] = None
    export_format: Optional[Literal["auto", "mp3", "wav", "flac", "m4a"]] = None
    transcription: Optional[bool] = None
    summarize: Optional[bool] = None
    social_content: Optional[bool] = None
    export_timestamps: Optional[bool] = None
    signed_url: Optional[str] = None
    merge: Optional[bool] = None


class EditInput(BaseModel):
    """Input configuration for the edit request."""

    files: List[str]
    config: ProcessingConfig


class CreateEditRequest(BaseModel):
    """Request body for creating an edit."""

    input: EditInput


class CreateEditResponse(BaseModel):
    """Response from creating an edit."""

    id: str


EditStatus = str


class EditStatistics(BaseModel):
    """Statistics about the edit process."""

    BREATH: Optional[float] = None
    DEADAIR: Optional[float] = None
    STUTTERING: Optional[float] = None
    MOUTH_SOUND: Optional[float] = None
    FILLER_SOUND: Optional[float] = None


class Chapter(BaseModel):
    """Chapter information for summarization."""

    start: float
    title: str


class Summarization(BaseModel):
    """Summarization result."""

    title: str
    summary: str
    chapters: List[Chapter]
    summaries: List[str]
    key_learnings: str
    summary_of_summary: str
    episode_description: str


class TranscriptionWord(BaseModel):
    """Word-level transcription data."""

    id: int
    end: float
    text: str
    start: float


class TranscriptionParagraph(BaseModel):
    """Paragraph-level transcription data."""

    id: int
    end: float
    start: float
    speaker: str


class DetailedTranscription(BaseModel):
    """Detailed transcription with word and paragraph data."""

    words: List[TranscriptionWord]
    paragraphs: List[TranscriptionParagraph]


class SimpleTranscriptionParagraph(BaseModel):
    """Simple paragraph transcription."""

    end: float
    text: str
    start: float


class Transcription(BaseModel):
    """Transcription result."""

    paragraphs: List[SimpleTranscriptionParagraph]
    transcription: DetailedTranscription


class EditResult(BaseModel):
    """Complete edit result."""

    video: bool
    filename: str
    statistics: EditStatistics
    download_url: str
    summarization: Optional[Union[Summarization, List]] = None
    transcription: Optional[Union[Transcription, List]] = None
    social_content: List[Any] = Field(default_factory=list)
    merged_audio_url: List[str] = Field(default_factory=list)
    timestamps_markers_urls: List[str] = Field(default_factory=list)

    @field_validator('summarization', mode='before')
    @classmethod
    def validate_summarization(cls, v):
        """Convert empty list to None for summarization field."""
        if v == []:
            return None
        return v

    @field_validator('transcription', mode='before')
    @classmethod
    def validate_transcription(cls, v):
        """Convert empty list to None for transcription field."""
        if v == []:
            return None
        return v


class ProcessingProgress(BaseModel):
    """Progress data when processing is in progress."""

    done: float
    total: float
    state: str
    phase: int
    step: int
    substep: int
    job_name: str


class RetrieveEditResponse(BaseModel):
    """Response from retrieving an edit."""

    status: EditStatus
    result: Optional[Union[ProcessingProgress, EditResult]] = None
    task_id: str


class CleanvoiceConfig(BaseModel):
    """Configuration for the Cleanvoice SDK."""

    api_key: str
    base_url: Optional[str] = "https://api.cleanvoice.ai/v2"
    timeout: Optional[int] = 60


class ProcessResult(BaseModel):
    """Simplified response format for the main process method."""

    class AudioResult(BaseModel):
        url: str
        filename: str
        statistics: EditStatistics

    class TranscriptResult(BaseModel):
        text: str
        paragraphs: List[SimpleTranscriptionParagraph]
        detailed: DetailedTranscription
        summary: Optional[str] = None
        title: Optional[str] = None
        chapters: Optional[List[Chapter]] = None

    audio: AudioResult
    transcript: Optional[TranscriptResult] = None


class ApiError(Exception):
    """Exception raised for API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)


class FileValidationError(Exception):
    """Exception raised for file validation errors."""

    pass


class AudioInfo(BaseModel):
    """Information about an audio file."""

    duration: float
    sample_rate: int
    channels: int
    format: str
    bitrate: Optional[int] = None


class VideoInfo(BaseModel):
    """Information about a video file."""

    duration: float
    width: int
    height: int
    fps: float
    format: str
    has_audio: bool
    audio_info: Optional[AudioInfo] = None
