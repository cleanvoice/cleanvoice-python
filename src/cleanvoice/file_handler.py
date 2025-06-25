"""File handling utilities for audio and video files without ffmpeg."""

import os
import tempfile
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

import librosa
import requests
import soundfile as sf
from mutagen import File as MutagenFile

try:
    import av

    _HAS_AV = True
except ImportError:
    _HAS_AV = False

from .types import AudioInfo, FileValidationError, VideoInfo

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


def is_url(file_path: str) -> bool:
    """Check if a string is a URL."""
    try:
        result = urlparse(file_path)
        return all([result.scheme, result.netloc])
    except (ValueError, AttributeError):
        return False


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


def download_file(url: str, destination: Optional[str] = None) -> str:
    """Download a file from URL to local filesystem."""
    if not is_url(url):
        raise FileValidationError(f"Invalid URL: {url}")

    if destination is None:
        # Create a temporary file
        parsed = urlparse(url)
        file_ext = Path(parsed.path).suffix or ".tmp"
        fd, destination = tempfile.mkstemp(suffix=file_ext)
        os.close(fd)

    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return destination
    except requests.RequestException as e:
        if os.path.exists(destination):
            os.unlink(destination)
        raise FileValidationError(f"Failed to download file: {e}")


def get_audio_info(file_path: str) -> AudioInfo:
    """Get information about an audio file using librosa and soundfile."""
    if not os.path.exists(file_path):
        raise FileValidationError(f"Audio file not found: {file_path}")

    try:
        # Try soundfile first for format info
        info = sf.info(file_path)

        # Get additional metadata with mutagen
        bitrate = None
        try:
            mutagen_file = MutagenFile(file_path)
            if mutagen_file and hasattr(mutagen_file, "info"):
                if hasattr(mutagen_file.info, "bitrate"):
                    bitrate = mutagen_file.info.bitrate
        except Exception:
            pass  # Ignore mutagen errors

        return AudioInfo(
            duration=info.duration,
            sample_rate=info.samplerate,
            channels=info.channels,
            format=info.format,
            bitrate=bitrate,
        )

    except Exception as e:
        # Fallback to librosa
        try:
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
            raise FileValidationError(
                f"Failed to read audio file: {e}, {librosa_error}"
            )


def get_video_info(file_path: str) -> VideoInfo:
    """Get information about a video file using PyAV."""
    if not os.path.exists(file_path):
        raise FileValidationError(f"Video file not found: {file_path}")

    if not _HAS_AV:
        raise FileValidationError(
            "PyAV is required for video processing. Install with: pip install av"
        )

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
    if not _HAS_AV:
        raise FileValidationError(
            "PyAV is required for video audio extraction. Install with: pip install av"
        )

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


def normalize_file_input(file_input: str) -> str:
    """Normalize file input to a URL format that can be processed by the API."""
    if is_url(file_input):
        # Validate URL points to a media file
        if not is_valid_media_file(file_input):
            raise FileValidationError(
                f"URL does not point to a valid media file: {file_input}"
            )
        return file_input

    # Local file path
    if not os.path.exists(file_input):
        raise FileValidationError(f"Local file not found: {file_input}")

    if not is_valid_media_file(file_input):
        raise FileValidationError(f"File is not a valid media file: {file_input}")

    # For local files, you would typically upload to a temporary storage
    # For now, we'll raise an error since the API expects URLs
    raise FileValidationError(
        "Local file uploads not yet supported. Please provide a URL to your media file."
    )


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
