"""File handling utilities for audio and video files without ffmpeg."""

import asyncio
import numbers
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Tuple, Union
from urllib.parse import urlparse

import httpx
import requests

from .types import ApiError, AudioInfo, FileValidationError, VideoInfo

if TYPE_CHECKING:
    import numpy as np

# Supported file extensions
AUDIO_EXTENSIONS = {
    ".wav",
    ".wave",
    ".flac",
    ".aiff",
    ".aif",
    ".au",
    ".snd",
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".oga",
    ".wma",
}

UPLOADABLE_AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".flac",
    ".m4a",
}

VIDEO_EXTENSIONS = {
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".webm",
    ".flv",
    ".wmv",
    ".m4v",
    ".3gp",
    ".3g2",
    ".asf",
    ".rm",
    ".rmvb",
}

SAFE_REMOTE_SCHEMES = {"http", "https"}

ArrayWithSampleRate = Tuple[Any, int]
MediaInput = Union[str, os.PathLike[str], ArrayWithSampleRate]
AudioArrayResult = Tuple[Any, int]
BASE_INSTALL = "pip install cleanvoice-sdk"


def _missing_media_dependency(package_name: str, feature: str) -> FileValidationError:
    return FileValidationError(
        f"{package_name} is required for {feature}. Install or reinstall with: {BASE_INSTALL}"
    )


def _import_numpy(feature: str = "in-memory audio support"):
    try:
        import numpy as np
    except ImportError as error:
        raise _missing_media_dependency("NumPy", feature) from error

    return np


def _import_librosa(feature: str = "audio file loading"):
    try:
        import librosa
    except ImportError as error:
        raise _missing_media_dependency("librosa", feature) from error

    return librosa


def _import_soundfile(feature: str = "local audio file support"):
    try:
        import soundfile as sf
    except ImportError as error:
        raise _missing_media_dependency("soundfile", feature) from error

    return sf


def _import_mutagen_file():
    try:
        from mutagen import File as MutagenFile
    except ImportError:
        return None

    return MutagenFile


def _import_av():
    try:
        import av
    except ImportError as error:
        raise _missing_media_dependency("PyAV", "video processing") from error
    return av


def is_url(file_path: str) -> bool:
    """Check if a string is a URL."""
    try:
        result = urlparse(file_path)
        return all([result.scheme, result.netloc])
    except (ValueError, AttributeError):
        return False


def is_http_url(file_path: str) -> bool:
    """Check whether a URL uses a scheme supported by execution paths."""
    if not is_url(file_path):
        return False
    parsed = urlparse(file_path)
    return parsed.scheme.lower() in SAFE_REMOTE_SCHEMES


def is_valid_audio_file(file_path: str) -> bool:
    """Check if file path has a valid audio extension."""
    if is_url(file_path):
        parsed = urlparse(file_path)
        path_ext = Path(parsed.path).suffix.lower()
    else:
        path_ext = Path(file_path).suffix.lower()

    return path_ext in AUDIO_EXTENSIONS


def is_valid_video_file(file_path: str) -> bool:
    """Check if file path has a valid video extension."""
    if is_url(file_path):
        parsed = urlparse(file_path)
        path_ext = Path(parsed.path).suffix.lower()
    else:
        path_ext = Path(file_path).suffix.lower()

    return path_ext in VIDEO_EXTENSIONS


def is_valid_media_file(file_path: str) -> bool:
    """Check if file path has a valid audio or video extension."""
    return is_valid_audio_file(file_path) or is_valid_video_file(file_path)


def is_valid_uploadable_media_file(file_path: str) -> bool:
    """Check whether a local file format can be uploaded through the API."""
    path_ext = Path(file_path).suffix.lower()
    return path_ext in UPLOADABLE_AUDIO_EXTENSIONS or path_ext in VIDEO_EXTENSIONS


def _looks_like_audio_array(value: Any) -> bool:
    """Return True for raw in-memory audio arrays or nested sample lists."""
    return hasattr(value, "__array__") or isinstance(value, list)


def _is_audio_array_with_sample_rate(file_input: Any) -> bool:
    """Identify the supported in-memory input format."""
    return (
        isinstance(file_input, tuple)
        and len(file_input) == 2
        and not isinstance(file_input[0], (str, os.PathLike))
        and isinstance(file_input[1], numbers.Integral)
    )


def _coerce_audio_array_input(file_input: Any) -> Tuple[Any, int]:
    """Validate and normalize an in-memory audio input."""
    np = _import_numpy("in-memory audio support")

    if not _is_audio_array_with_sample_rate(file_input):
        if _looks_like_audio_array(file_input):
            raise FileValidationError(
                "In-memory audio inputs must be passed as (audio_array, sample_rate)"
            )
        raise FileValidationError(
            "Unsupported input. Provide a URL, local file path, or (audio_array, sample_rate)"
        )

    audio_data, sample_rate = file_input
    sample_rate = int(sample_rate)
    if sample_rate <= 0:
        raise FileValidationError("sample_rate must be a positive integer")

    try:
        normalized = np.asarray(audio_data, dtype=np.float32)
    except Exception as error:
        raise FileValidationError(f"Failed to convert audio array: {error}")

    if normalized.size == 0:
        raise FileValidationError("Audio array cannot be empty")

    if normalized.ndim == 2 and normalized.shape[0] <= 8 and normalized.shape[1] > normalized.shape[0]:
        # librosa commonly returns multi-channel audio as (channels, samples)
        normalized = normalized.T

    if normalized.ndim not in (1, 2):
        raise FileValidationError(
            "Audio array must be 1D mono samples or 2D multi-channel samples"
        )

    if not np.isfinite(normalized).all():
        raise FileValidationError("Audio array contains NaN or infinite values")

    return normalized, sample_rate


def _write_audio_array_to_temp_file(file_input: Any) -> str:
    """Persist an in-memory audio input to a temporary WAV file."""
    sf = _import_soundfile("writing in-memory audio uploads")
    audio_data, sample_rate = _coerce_audio_array_input(file_input)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        sf.write(temp_path, audio_data, sample_rate)
        return temp_path
    except Exception as error:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise FileValidationError(f"Failed to write audio array to disk: {error}")


def _resolve_upload_source(file_input: MediaInput) -> Tuple[str, Optional[str]]:
    """Return the file path to upload and any temp file that must be cleaned up."""
    if _is_audio_array_with_sample_rate(file_input):
        temp_path = _write_audio_array_to_temp_file(file_input)
        return temp_path, temp_path

    if _looks_like_audio_array(file_input):
        raise FileValidationError(
            "In-memory audio inputs must be passed as (audio_array, sample_rate)"
        )

    if not isinstance(file_input, (str, os.PathLike)):
        raise FileValidationError(
            "Unsupported input. Provide a URL, local file path, or (audio_array, sample_rate)"
        )

    return os.fspath(file_input), None


def _resolve_download_destination(
    url: str, destination: Optional[str], default_filename: str = "downloaded_audio.mp3"
) -> str:
    """Resolve the output path for a downloaded file."""
    if destination is not None:
        return destination

    parsed = urlparse(url)
    filename = Path(parsed.path).name
    return filename or default_filename


def _prepare_download_paths(destination: str) -> Tuple[Path, str]:
    """Create a temporary sibling file used for safe atomic downloads."""
    destination_path = Path(destination)
    temp_handle = tempfile.NamedTemporaryFile(
        delete=False,
        dir=str(destination_path.parent or Path(".")),
        prefix=f".{destination_path.name}.",
        suffix=".tmp",
    )
    temp_handle.close()
    return destination_path, temp_handle.name


def signed_url_to_public_url(signed_url: str) -> str:
    """Strip query params from a signed upload URL."""
    parsed = urlparse(signed_url)
    return parsed._replace(query="", fragment="").geturl()


def download_file(url: str, destination: Optional[str] = None) -> str:
    """Download a file from URL to local filesystem."""
    if not is_http_url(url):
        raise FileValidationError(f"Invalid URL: {url}")

    destination = _resolve_download_destination(url, destination)
    temp_path = None

    try:
        destination_path, temp_path = _prepare_download_paths(destination)
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()

        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        os.replace(temp_path, destination_path)
        return str(destination_path)
    except (requests.RequestException, OSError) as e:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise FileValidationError(f"Failed to download file: {e}")


def load_audio_array(file_path: str) -> AudioArrayResult:
    """Load a local audio file into a NumPy array and return its sample rate."""
    librosa = _import_librosa("loading downloaded audio as a NumPy array")
    np = _import_numpy("loading downloaded audio as a NumPy array")

    if not os.path.exists(file_path):
        raise FileValidationError(f"Audio file not found: {file_path}")

    if is_valid_video_file(file_path):
        raise FileValidationError(
            "NumPy array output is only supported for audio files"
        )

    try:
        audio_data, sample_rate = librosa.load(file_path, sr=None, mono=False)
        return np.asarray(audio_data), int(sample_rate)
    except Exception as error:
        raise FileValidationError(f"Failed to load audio as NumPy array: {error}")


async def download_file_async(url: str, destination: Optional[str] = None) -> str:
    """Asynchronously download a file from URL to local filesystem."""
    if not is_http_url(url):
        raise FileValidationError(f"Invalid URL: {url}")

    destination = _resolve_download_destination(url, destination)
    destination_path, temp_path = _prepare_download_paths(destination)

    try:
        destination_path, temp_path = _prepare_download_paths(destination)
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url, timeout=300) as response:
                response.raise_for_status()
                with open(temp_path, "wb") as file_handle:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        await asyncio.to_thread(file_handle.write, chunk)
        os.replace(temp_path, destination_path)
        return str(destination_path)
    except (httpx.HTTPError, OSError) as error:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
        raise FileValidationError(f"Failed to download file: {error}")


async def load_audio_array_async(file_path: str) -> AudioArrayResult:
    """Asynchronously load a local audio file into a NumPy array."""
    return await asyncio.to_thread(load_audio_array, file_path)


def get_audio_info(file_path: str) -> AudioInfo:
    """Get information about an audio file using librosa and soundfile."""
    sf = None
    primary_error: Optional[Exception] = None
    try:
        sf = _import_soundfile("audio metadata inspection")
    except FileValidationError as error:
        primary_error = error
    MutagenFile = _import_mutagen_file()

    if not os.path.exists(file_path):
        raise FileValidationError(f"Audio file not found: {file_path}")

    if sf is not None:
        try:
            # Try soundfile first for format info
            info = sf.info(file_path)

            # Get additional metadata with mutagen when available.
            bitrate = None
            if MutagenFile is not None:
                try:
                    mutagen_file = MutagenFile(file_path)
                    if mutagen_file and hasattr(mutagen_file, "info"):
                        if hasattr(mutagen_file.info, "bitrate"):
                            bitrate = mutagen_file.info.bitrate
                except Exception:
                    pass

            return AudioInfo(
                duration=info.duration,
                sample_rate=info.samplerate,
                channels=info.channels,
                format=info.format,
                bitrate=bitrate,
            )
        except Exception as error:
            primary_error = error

    # Fallback to librosa when soundfile or mutagen metadata is unavailable.
    try:
        librosa = _import_librosa("audio metadata inspection")
        y, sr = librosa.load(file_path, sr=None)
        duration = len(y) / sr

        return AudioInfo(
            duration=duration,
            sample_rate=sr,
            channels=1,  # librosa loads as mono by default
            format="unknown",
            bitrate=None,
        )
    except Exception as librosa_error:
        if primary_error is not None:
            raise FileValidationError(
                f"Failed to read audio file: {primary_error}; fallback failed: {librosa_error}"
            )
        raise FileValidationError(f"Failed to read audio file: {librosa_error}")


def get_video_info(file_path: str) -> VideoInfo:
    """Get information about a video file using PyAV."""
    av = _import_av()

    if not os.path.exists(file_path):
        raise FileValidationError(f"Video file not found: {file_path}")

    try:
        with av.open(file_path, "r") as container:
            # Get video stream info
            video_stream = None
            audio_stream = None

            for stream in container.streams:
                if stream.type == "video" and video_stream is None:
                    video_stream = stream
                elif stream.type == "audio" and audio_stream is None:
                    audio_stream = stream

            if video_stream is None:
                raise FileValidationError("No video stream found in file")

            # Get video properties
            duration = (
                float(video_stream.duration * video_stream.time_base)
                if video_stream.duration
                else 0
            )
            if duration == 0 and container.duration:
                duration = float(container.duration) / av.time_base

            width = video_stream.width
            height = video_stream.height
            fps = float(video_stream.average_rate) if video_stream.average_rate else 0

            # Get audio info if available
            has_audio = audio_stream is not None
            audio_info = None

            if has_audio and audio_stream:
                audio_duration = (
                    float(audio_stream.duration * audio_stream.time_base)
                    if audio_stream.duration
                    else duration
                )
                audio_info = AudioInfo(
                    duration=audio_duration,
                    sample_rate=audio_stream.rate,
                    channels=audio_stream.channels,
                    format=audio_stream.codec.name,
                    bitrate=audio_stream.bit_rate,
                )

            return VideoInfo(
                duration=duration,
                width=width,
                height=height,
                fps=fps,
                format=video_stream.codec.name,
                has_audio=has_audio,
                audio_info=audio_info,
            )

    except Exception as e:
        raise FileValidationError(f"Failed to read video file with PyAV: {e}")


def extract_audio_from_video(video_path: str, output_path: Optional[str] = None) -> str:
    """Extract audio from video file using PyAV."""
    av = _import_av()

    if not os.path.exists(video_path):
        raise FileValidationError(f"Video file not found: {video_path}")

    if output_path is None:
        video_name = Path(video_path).stem
        output_path = f"{video_name}_extracted_audio.wav"

    try:
        input_container = av.open(video_path, "r")
        output_container = av.open(output_path, "w")

        # Find audio stream
        audio_stream = None
        for stream in input_container.streams:
            if stream.type == "audio":
                audio_stream = stream
                break

        if audio_stream is None:
            input_container.close()
            output_container.close()
            raise FileValidationError("Video file has no audio track")

        # Create output audio stream
        output_stream = output_container.add_stream("pcm_s16le", rate=audio_stream.rate)
        output_stream.channels = audio_stream.channels

        # Process audio frames
        for frame in input_container.decode(audio_stream):
            for packet in output_stream.encode(frame):
                output_container.mux(packet)

        # Flush
        for packet in output_stream.encode():
            output_container.mux(packet)

        input_container.close()
        output_container.close()

        return output_path

    except Exception as e:
        if os.path.exists(output_path):
            os.unlink(output_path)
        raise FileValidationError(f"Failed to extract audio from video: {e}")


def normalize_file_input(file_input: MediaInput, api_client=None) -> str:
    """Normalize file input to a URL format that can be processed by the API."""
    # Handle edge cases
    if file_input is None:
        raise FileValidationError("File input cannot be None")

    if _is_audio_array_with_sample_rate(file_input):
        if api_client is not None:
            return upload_local_file(file_input, api_client)
        raise FileValidationError(
            "In-memory audio uploads require an API client. Use Cleanvoice.process(...) or upload_file(...)."
        )

    if _looks_like_audio_array(file_input):
        raise FileValidationError(
            "In-memory audio inputs must be passed as (audio_array, sample_rate)"
        )

    if file_input == "":
        raise FileValidationError("File input cannot be empty")

    if is_url(file_input):
        if not is_http_url(file_input):
            raise FileValidationError(
                f"Only http and https URLs are supported: {file_input}"
            )
        # Validate URL points to a media file
        if not is_valid_media_file(file_input):
            raise FileValidationError(
                f"URL does not point to a valid media file: {file_input}"
            )
        return file_input

    # Local file path
    if not os.path.exists(file_input):
        raise FileValidationError(f"File does not exist: {file_input}")

    if not is_valid_media_file(file_input):
        raise FileValidationError(f"Unsupported file format: {file_input}")

    # If api_client is provided, upload the file
    if api_client is not None:
        return upload_local_file(file_input, api_client)
    
    # For backward compatibility, raise an error if no api_client provided
    raise FileValidationError(
        "Local file uploads not yet supported. Please provide a URL to your media file."
    )


async def normalize_file_input_async(file_input: MediaInput, api_client=None) -> str:
    """Async equivalent of normalize_file_input."""
    if file_input is None:
        raise FileValidationError("File input cannot be None")

    if _is_audio_array_with_sample_rate(file_input):
        if api_client is not None:
            return await upload_local_file_async(file_input, api_client)
        raise FileValidationError(
            "In-memory audio uploads require an API client. Use AsyncCleanvoice.process(...) or upload_file(...)."
        )

    if _looks_like_audio_array(file_input):
        raise FileValidationError(
            "In-memory audio inputs must be passed as (audio_array, sample_rate)"
        )

    if file_input == "":
        raise FileValidationError("File input cannot be empty")

    if is_url(file_input):
        if not is_http_url(file_input):
            raise FileValidationError(
                f"Only http and https URLs are supported: {file_input}"
            )
        if not is_valid_media_file(file_input):
            raise FileValidationError(
                f"URL does not point to a valid media file: {file_input}"
            )
        return file_input

    if not os.path.exists(file_input):
        raise FileValidationError(f"File does not exist: {file_input}")

    if not is_valid_media_file(file_input):
        raise FileValidationError(f"Unsupported file format: {file_input}")

    if api_client is not None:
        return await upload_local_file_async(file_input, api_client)

    raise FileValidationError(
        "Local file uploads not yet supported. Please provide a URL to your media file."
    )


def upload_local_file(
    file_path: MediaInput, api_client, filename: Optional[str] = None
) -> str:
    """Upload a local file and return the URL for processing."""
    resolved_file_path, temp_path = _resolve_upload_source(file_path)
    try:
        if not os.path.exists(resolved_file_path):
            raise FileValidationError(f"Local file not found: {resolved_file_path}")

        if not is_valid_uploadable_media_file(resolved_file_path):
            raise FileValidationError(
                f"File is not supported for upload: {resolved_file_path}"
            )

        default_upload_name = (
            "in_memory_audio.wav" if temp_path else Path(resolved_file_path).name
        )
        upload_name = filename or default_upload_name
        signed_url = api_client.get_signed_upload_url(upload_name)
        api_client.upload_file(resolved_file_path, signed_url)
        return signed_url_to_public_url(signed_url)
    except (ApiError, FileValidationError):
        raise
    except Exception as error:
        raise FileValidationError(f"Failed to upload file: {error}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


async def upload_local_file_async(
    file_path: MediaInput, api_client, filename: Optional[str] = None
) -> str:
    """Asynchronously upload a local file and return the public URL."""
    resolved_file_path, temp_path = _resolve_upload_source(file_path)
    try:
        if not os.path.exists(resolved_file_path):
            raise FileValidationError(f"Local file not found: {resolved_file_path}")

        if not is_valid_uploadable_media_file(resolved_file_path):
            raise FileValidationError(
                f"File is not supported for upload: {resolved_file_path}"
            )

        default_upload_name = (
            "in_memory_audio.wav" if temp_path else Path(resolved_file_path).name
        )
        upload_name = filename or default_upload_name
        signed_url = await api_client.get_signed_upload_url(upload_name)
        await api_client.upload_file(resolved_file_path, signed_url)
        return signed_url_to_public_url(signed_url)
    except (ApiError, FileValidationError):
        raise
    except Exception as error:
        raise FileValidationError(f"Failed to upload file: {error}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def validate_config(config: dict) -> None:
    """Validate processing configuration."""
    if not isinstance(config, dict):
        raise FileValidationError("Configuration must be a dictionary")

    # Check for conflicting options
    if config.get("summarize") and not config.get("transcription"):
        raise FileValidationError("Summarization requires transcription to be enabled")

    if config.get("social_content") and not config.get("summarize"):
        raise FileValidationError("Social content requires summarization to be enabled")

    # Validate LUFS values
    if "mute_lufs" in config and config["mute_lufs"] is not None:
        if config["mute_lufs"] > 0:
            raise FileValidationError("mute_lufs must be a negative number")

    if "target_lufs" in config and config["target_lufs"] is not None:
        if config["target_lufs"] > 0:
            raise FileValidationError("target_lufs must be a negative number")


def get_file_info(file_path: str) -> Union[AudioInfo, VideoInfo]:
    """Get information about a media file."""
    if is_valid_audio_file(file_path):
        return get_audio_info(file_path)
    elif is_valid_video_file(file_path):
        return get_video_info(file_path)
    else:
        raise FileValidationError(f"Unsupported file type: {file_path}")
