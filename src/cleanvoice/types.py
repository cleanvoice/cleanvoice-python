"""Type definitions for the Cleanvoice SDK."""

from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import TypedDict


class AccountInfo(TypedDict, total=False):
    """Typed account payload returned by the authentication check."""

    user: str
    account: Dict[str, Any]
    account_type: str
    credits_remaining: int


class ProcessingConfig(BaseModel):
    """Configuration options for audio processing."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    video: Optional[bool] = None
    send_email: Optional[bool] = None
    audio_for_edl: Optional[bool] = None
    long_silences: Optional[bool] = None
    stutters: Optional[bool] = None
    fillers: Optional[bool] = None
    mouth_sounds: Optional[bool] = None
    hesitations: Optional[bool] = None
    muted: Optional[bool] = None
    remove_noise: Optional[bool] = None
    keep_music: Optional[bool] = None
    breath: Optional[Union[bool, str]] = None
    normalize: Optional[bool] = None
    autoeq: Optional[bool] = None
    studio_sound: Optional[Union[bool, str]] = None
    mute_lufs: Optional[float] = None
    target_lufs: Optional[float] = None
    export_format: Optional[Literal["auto", "mp3", "wav", "flac", "m4a"]] = None
    transcription: Optional[bool] = None
    summarize: Optional[bool] = None
    social_content: Optional[bool] = None
    export_timestamps: Optional[bool] = None
    signed_url: Optional[str] = None
    merge: Optional[bool] = None
    automix: Optional[bool] = None
    trim: Optional[bool] = None
    waveform_preview: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_aliases(cls, data: Any) -> Any:
        """Accept legacy config names while exposing a single public field."""
        if isinstance(data, dict):
            normalized = dict(data)
            if "sound_studio" in normalized and "studio_sound" not in normalized:
                normalized["studio_sound"] = normalized.pop("sound_studio")
            return normalized
        return data

    @property
    def sound_studio(self) -> Optional[Union[bool, str]]:
        """Backward-compatible access for older callers."""
        return self.studio_sound


class EditInput(BaseModel):
    """Input configuration for the edit request."""

    files: List[str]
    config: ProcessingConfig
    upload_type: Optional[str] = None
    template_id: Optional[int] = None


class CreateEditRequest(BaseModel):
    """Request body for creating an edit."""

    input: EditInput


class CreateEditResponse(BaseModel):
    """Response from creating an edit."""

    id: str


EditStatus = Literal[
    "FAILURE",
    "PENDING",
    "PREPROCESSING",
    "CLASSIFICATION",
    "EDITING",
    "POSTPROCESSING",
    "EXPORT",
    "PROCESSING",
    "QUEUED",
    "RETRY",
    "STARTED",
    "SUCCESS",
]


class EditStatistics(BaseModel):
    """Statistics about the edit process."""

    model_config = ConfigDict(extra="allow")

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


class SocialContent(BaseModel):
    """Social content generated from the processed audio."""

    model_config = ConfigDict(extra="allow")

    newsletter: Optional[str] = None
    twitter_thread: Optional[str] = None
    linkedin: Optional[str] = None


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
    social_content: Union[SocialContent, List[Any]] = Field(default_factory=list)
    merged_audio_url: Any = Field(default_factory=list)
    timestamps_markers_urls: Optional[Union[Dict[str, str], List[str]]] = None
    waveform_result: Any = None

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

    @field_validator("result", mode="before")
    @classmethod
    def normalize_empty_result(cls, value: Any) -> Any:
        """Treat empty API payloads as missing progress/result data."""
        if value == {}:
            return None
        return value


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
        local_path: Optional[str] = None
        merged_audio_url: Any = None
        timestamps_markers_urls: Optional[Union[Dict[str, str], List[str]]] = None
        waveform_result: Any = None

        def download(self, output_path: Optional[str] = None) -> str:
            """Download the processed audio and store the saved path."""
            from .file_handler import download_file

            self.local_path = download_file(self.url, output_path)
            return self.local_path

        async def download_async(self, output_path: Optional[str] = None) -> str:
            """Asynchronously download the processed audio."""
            from .file_handler import download_file_async

            self.local_path = await download_file_async(self.url, output_path)
            return self.local_path

    class TranscriptResult(BaseModel):
        text: str
        paragraphs: List[SimpleTranscriptionParagraph]
        detailed: DetailedTranscription
        summary: Optional[str] = None
        title: Optional[str] = None
        chapters: Optional[List[Chapter]] = None
        summarization: Optional[Summarization] = None

    audio: AudioResult
    video: bool = False
    transcript: Optional[TranscriptResult] = None
    summarization: Optional[Summarization] = None
    social_content: Union[SocialContent, List[Any]] = Field(default_factory=list)
    timestamps_markers_urls: Optional[Union[Dict[str, str], List[str]]] = None
    waveform_result: Any = None
    task_id: Optional[str] = None

    @property
    def media(self) -> AudioResult:
        """Return the processed asset regardless of whether it is audio or video."""
        return self.audio

    @property
    def is_video(self) -> bool:
        """Expose the returned media type in a readable way."""
        return self.video

    def download_audio(
        self, output_path: Optional[str] = None, as_numpy: bool = False
    ) -> Union[str, Tuple[Any, int]]:
        """Download the processed audio and optionally load it as a NumPy array."""
        if self.video and as_numpy:
            raise ApiError(
                "NumPy array output is only supported for audio results, not video"
            )

        saved_path = self.audio.download(output_path)
        if not as_numpy:
            return saved_path

        from .file_handler import load_audio_array

        return load_audio_array(saved_path)

    async def download_audio_async(
        self, output_path: Optional[str] = None, as_numpy: bool = False
    ) -> Union[str, Tuple[Any, int]]:
        """Asynchronously download the processed audio and optionally load it as a NumPy array."""
        if self.video and as_numpy:
            raise ApiError(
                "NumPy array output is only supported for audio results, not video"
            )

        saved_path = await self.audio.download_async(output_path)
        if not as_numpy:
            return saved_path

        from .file_handler import load_audio_array_async

        return await load_audio_array_async(saved_path)

    def download_media(self, output_path: Optional[str] = None) -> str:
        """Download the processed media and return the saved path."""
        return self.audio.download(output_path)

    async def download_media_async(self, output_path: Optional[str] = None) -> str:
        """Asynchronously download the processed media and return the saved path."""
        return await self.audio.download_async(output_path)

    def download_audio_array(self, output_path: Optional[str] = None) -> Tuple[Any, int]:
        """Download an audio result and return (audio_array, sample_rate)."""
        result = self.download_audio(output_path=output_path, as_numpy=True)
        return result

    async def download_audio_array_async(
        self, output_path: Optional[str] = None
    ) -> Tuple[Any, int]:
        """Asynchronously download an audio result and return (audio_array, sample_rate)."""
        result = await self.download_audio_async(output_path=output_path, as_numpy=True)
        return result


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
