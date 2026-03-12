"""Advanced tests for file handling utilities."""

import asyncio
import os
import subprocess
import sys
import tempfile
from unittest.mock import MagicMock, Mock, patch

import pytest
import soundfile as sf

from cleanvoice.file_handler import (
    extract_audio_from_video,
    get_audio_info,
    get_file_info,
    get_video_info,
    normalize_file_input,
    normalize_file_input_async,
    upload_local_file,
    upload_local_file_async,
)
from cleanvoice.types import AudioInfo, FileValidationError, VideoInfo


def _numpy_import_works() -> bool:
    result = subprocess.run(
        [sys.executable, "-c", "import numpy"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


HAS_WORKING_NUMPY = _numpy_import_works()


def test_normalize_file_input_url():
    """normalize_file_input should return valid media URLs unchanged."""
    url = "https://example.com/audio.mp3"
    assert normalize_file_input(url) == url


def test_normalize_file_input_local_file_requires_client():
    """Local files still need an API client for upload."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        with pytest.raises(
            FileValidationError,
            match="Local file uploads not yet supported",
        ):
            normalize_file_input(temp_path)
    finally:
        os.unlink(temp_path)


def test_normalize_file_input_none():
    """None should raise a clear validation error."""
    with pytest.raises(FileValidationError, match="File input cannot be None"):
        normalize_file_input(None)


@pytest.mark.skipif(not HAS_WORKING_NUMPY, reason="NumPy import crashes in this environment")
def test_normalize_file_input_audio_array_tuple_uses_upload_flow():
    """In-memory audio should be delegated to the upload path."""
    mock_client = Mock()
    import numpy as np

    audio = np.array([0.1, -0.1, 0.2, -0.2], dtype=np.float32)
    with patch(
        "cleanvoice.file_handler.upload_local_file",
        return_value="https://uploaded-url.com/in-memory.wav",
    ) as mock_upload:
        result = normalize_file_input((audio, 16000), mock_client)

    assert result == "https://uploaded-url.com/in-memory.wav"
    mock_upload.assert_called_once_with((audio, 16000), mock_client)


@pytest.mark.skipif(not HAS_WORKING_NUMPY, reason="NumPy import crashes in this environment")
def test_normalize_file_input_rejects_bare_audio_array():
    """Bare arrays should ask the caller for a sample rate."""
    import numpy as np

    with pytest.raises(
        FileValidationError,
        match="In-memory audio inputs must be passed as \\(audio_array, sample_rate\\)",
    ):
        normalize_file_input(np.array([0.1, 0.2], dtype=np.float32))


@pytest.mark.skipif(not HAS_WORKING_NUMPY, reason="NumPy import crashes in this environment")
def test_upload_local_file_audio_array_tuple_writes_temp_file():
    """Uploading in-memory audio should persist a temp WAV and clean it up."""
    mock_client = Mock()
    import numpy as np

    audio = np.array([0.1, -0.1, 0.2, -0.2], dtype=np.float32)
    observed = {}

    def fake_signed_url(filename):
        observed["filename"] = filename
        return "https://signed-url.com/upload?token=123"

    def fake_upload(file_path, signed_url):
        observed["file_path"] = file_path
        observed["signed_url"] = signed_url
        observed["exists_during_upload"] = os.path.exists(file_path)
        written_audio, sample_rate = sf.read(file_path)
        observed["sample_rate"] = sample_rate
        observed["samples"] = written_audio.tolist()

    mock_client.get_signed_upload_url.side_effect = fake_signed_url
    mock_client.upload_file.side_effect = fake_upload

    result = upload_local_file((audio, 16000), mock_client)

    assert result == "https://signed-url.com/upload"
    assert observed["filename"] == "in_memory_audio.wav"
    assert observed["signed_url"] == "https://signed-url.com/upload?token=123"
    assert observed["exists_during_upload"] is True
    assert observed["sample_rate"] == 16000
    assert len(observed["samples"]) == len(audio)
    assert not os.path.exists(observed["file_path"])


@pytest.mark.skipif(not HAS_WORKING_NUMPY, reason="NumPy import crashes in this environment")
def test_normalize_file_input_async_audio_array_tuple_uses_upload_flow():
    """Async normalization should support the same in-memory tuple input."""

    async def run_test():
        mock_client = Mock()
        import numpy as np

        audio = np.array([0.1, -0.1, 0.2, -0.2], dtype=np.float32)

        with patch(
            "cleanvoice.file_handler.upload_local_file_async",
            return_value="https://uploaded-url.com/in-memory-async.wav",
        ) as mock_upload:
            result = await normalize_file_input_async((audio, 22050), mock_client)

        assert result == "https://uploaded-url.com/in-memory-async.wav"
        mock_upload.assert_called_once_with((audio, 22050), mock_client)

    asyncio.run(run_test())


@pytest.mark.skipif(not HAS_WORKING_NUMPY, reason="NumPy import crashes in this environment")
def test_upload_local_file_async_audio_array_tuple_writes_temp_file():
    """Async uploads should also write a temp WAV and clean it up."""

    async def run_test():
        mock_client = Mock()
        import numpy as np

        audio = np.array([0.1, -0.1, 0.2, -0.2], dtype=np.float32)
        observed = {}

        async def fake_signed_url(filename):
            observed["filename"] = filename
            return "https://signed-url.com/upload?token=456"

        async def fake_upload(file_path, signed_url):
            observed["file_path"] = file_path
            observed["signed_url"] = signed_url
            observed["exists_during_upload"] = os.path.exists(file_path)
            written_audio, sample_rate = sf.read(file_path)
            observed["sample_rate"] = sample_rate

        mock_client.get_signed_upload_url.side_effect = fake_signed_url
        mock_client.upload_file.side_effect = fake_upload

        result = await upload_local_file_async((audio, 22050), mock_client)

        assert result == "https://signed-url.com/upload"
        assert observed["filename"] == "in_memory_audio.wav"
        assert observed["signed_url"] == "https://signed-url.com/upload?token=456"
        assert observed["exists_during_upload"] is True
        assert observed["sample_rate"] == 22050
        assert not os.path.exists(observed["file_path"])

    asyncio.run(run_test())


@patch("cleanvoice.file_handler._import_mutagen_file")
@patch("cleanvoice.file_handler._import_soundfile")
def test_get_audio_info_success(mock_import_soundfile, mock_import_mutagen):
    """Audio info should be populated from soundfile and mutagen metadata."""
    mock_sf_module = Mock()
    mock_sf_module.info.return_value = Mock(
        duration=2.0,
        samplerate=44100,
        channels=2,
        format="WAV",
    )
    mock_import_soundfile.return_value = mock_sf_module
    mock_mutagen = Mock(return_value=Mock(info=Mock(bitrate=192000)))
    mock_import_mutagen.return_value = mock_mutagen

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        result = get_audio_info(temp_path)
        assert result == AudioInfo(
            duration=2.0,
            sample_rate=44100,
            channels=2,
            format="WAV",
            bitrate=192000,
        )
    finally:
        os.unlink(temp_path)


@patch("cleanvoice.file_handler._import_mutagen_file", return_value=None)
@patch("cleanvoice.file_handler._import_soundfile")
def test_get_audio_info_without_mutagen_still_returns_metadata(
    mock_import_soundfile, mock_import_mutagen
):
    """Audio info should still work when mutagen is not installed."""
    mock_sf_module = Mock()
    mock_sf_module.info.return_value = Mock(
        duration=1.0,
        samplerate=22050,
        channels=1,
        format="WAV",
    )
    mock_import_soundfile.return_value = mock_sf_module

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        result = get_audio_info(temp_path)
        assert result == AudioInfo(
            duration=1.0,
            sample_rate=22050,
            channels=1,
            format="WAV",
            bitrate=None,
        )
    finally:
        os.unlink(temp_path)


@patch("cleanvoice.file_handler._import_librosa")
@patch("cleanvoice.file_handler._import_soundfile")
def test_get_audio_info_missing_media_extra_has_clear_message(
    mock_import_soundfile, mock_import_librosa
):
    """Missing runtime media dependencies should point callers to the base install."""
    mock_import_soundfile.side_effect = FileValidationError(
        "soundfile is required for audio metadata inspection. Install or reinstall with: pip install cleanvoice-sdk"
    )
    mock_import_librosa.side_effect = FileValidationError(
        "librosa is required for audio metadata inspection. Install or reinstall with: pip install cleanvoice-sdk"
    )

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        with pytest.raises(
            FileValidationError, match=r"pip install cleanvoice-sdk"
        ):
            get_audio_info(temp_path)
    finally:
        os.unlink(temp_path)


@patch("cleanvoice.file_handler._import_av")
def test_get_video_info_success(mock_import_av):
    """Video info should be read from the first video/audio streams."""
    mock_video_stream = Mock(
        type="video",
        duration=150,
        time_base=0.1,
        width=1920,
        height=1080,
        average_rate=30,
        codec=Mock(name="codec"),
    )
    mock_video_stream.codec.name = "h264"

    mock_audio_stream = Mock(
        type="audio",
        duration=100,
        time_base=0.1,
        rate=48000,
        channels=2,
        bit_rate=128000,
        codec=Mock(name="codec"),
    )
    mock_audio_stream.codec.name = "aac"

    mock_container = Mock()
    mock_container.streams = [mock_video_stream, mock_audio_stream]
    mock_container.duration = None
    mock_av_module = MagicMock()
    mock_av_module.open.return_value.__enter__.return_value = mock_container
    mock_import_av.return_value = mock_av_module

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        result = get_video_info(temp_path)
        assert isinstance(result, VideoInfo)
        assert result.duration == 15.0
        assert result.width == 1920
        assert result.height == 1080
        assert result.fps == 30.0
        assert result.has_audio is True
        assert result.audio_info.sample_rate == 48000
    finally:
        os.unlink(temp_path)


@patch("cleanvoice.file_handler.get_audio_info")
def test_get_file_info_audio(mock_get_audio):
    """Audio files should delegate to get_audio_info."""
    mock_info = AudioInfo(
        duration=3.5,
        sample_rate=44100,
        channels=2,
        format="MP3",
        bitrate=128000,
    )
    mock_get_audio.return_value = mock_info

    assert get_file_info("test.mp3") == mock_info
    mock_get_audio.assert_called_once_with("test.mp3")


@patch("cleanvoice.file_handler.get_video_info")
def test_get_file_info_video(mock_get_video):
    """Video files should delegate to get_video_info."""
    mock_info = VideoInfo(
        duration=10.0,
        width=1920,
        height=1080,
        fps=30.0,
        format="h264",
        has_audio=True,
        audio_info=None,
    )
    mock_get_video.return_value = mock_info

    assert get_file_info("test.mp4") == mock_info
    mock_get_video.assert_called_once_with("test.mp4")


@patch("cleanvoice.file_handler._import_av")
def test_extract_audio_from_video_no_audio(mock_import_av):
    """extract_audio_from_video should fail clearly for silent videos."""
    mock_input = Mock()
    mock_input.streams = [Mock(type="video")]
    mock_output = Mock()
    mock_av_module = Mock()
    mock_av_module.open.side_effect = [mock_input, mock_output]
    mock_import_av.return_value = mock_av_module

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_video:
        video_path = temp_video.name

    try:
        with pytest.raises(
            FileValidationError,
            match="Failed to extract audio from video: Video file has no audio track",
        ):
            extract_audio_from_video(video_path)
    finally:
        os.unlink(video_path)
