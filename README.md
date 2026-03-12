# Cleanvoice Python SDK

Python SDK for the [Cleanvoice API](https://cleanvoice.ai). Use it to submit media, poll edit jobs, and download processed results from Python applications and backend services.

[![PyPI version](https://badge.fury.io/py/cleanvoice-sdk.svg)](https://badge.fury.io/py/cleanvoice-sdk)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- Audio and video processing requests
- Transcription, summarization, and social-content options
- Sync and async clients with a matching high-level API
- Typed request and response models
- Automatic retries for transient network and service failures
- Built-in support for local files, in-memory audio, NumPy helpers, and video utilities

## Installation

Install the SDK:
```bash
pip install cleanvoice-sdk
```

## Quick Start

```python
from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()

result = client.process(
    "https://example.com/podcast.mp3",
    fillers=True,
    normalize=True,
    studio_sound=True,
    summarize=True,
    output_path="podcast_clean.wav",
)

print(f"Processed audio: {result.audio.url}")
print(f"Saved locally to: {result.audio.local_path}")
print(f"Summary: {result.transcript.summary}")
```

## Common Usage Patterns

Most integrations fit one of these three patterns:

1. Process and save in one call:

```python
result = client.process(
    "local_or_remote_media",
    normalize=True,
    studio_sound=True,
    output_path="cleaned_output.wav",
)
```

2. Process first, download later:

```python
result = client.process("local_or_remote_media", normalize=True)
saved_path = result.audio.download("cleaned_output.wav")
```

3. Use async in web backends or workers:

```python
result = await async_client.process(
    "local_or_remote_media",
    normalize=True,
    output_path="cleaned_output.wav",
)
```

In practice, `output_path=...` is the lowest-friction option for backend jobs because the SDK uploads, waits, downloads, and returns a ready-to-use local path in `result.audio.local_path`.

## Authentication

Get your API key from the [Cleanvoice Dashboard](https://app.cleanvoice.ai/settings).

```python
from cleanvoice import Cleanvoice

client = Cleanvoice(
    api_key="your-api-key-here",
    base_url="https://api.cleanvoice.ai/v2",  # optional
    timeout=60,  # optional
)
```

Or set environment variables and use:

```python
from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()
```

## Network Resilience

The client automatically retries brief transient failures such as connection resets, connect/read timeouts on safe requests, and temporary HTTP responses like `429`, `502`, `503`, and `504`.

This is designed to absorb short backend restart windows without immediately failing common flows such as:

- `check_auth()`
- `create_edit(...)`
- `get_edit(...)`
- `process(...)` while polling for completion

Retries are intentionally conservative for edit creation so short backend restarts do not immediately fail a request or duplicate work.

## API Reference

### `process(file_input, config=None, progress_callback=None, *, output_path=None, download=False, template_id=None, upload_type=None, **options)`

Process an audio or video file with AI enhancement.

**Parameters:**
- `file_input` (`str` or `(audio_array, sample_rate)`): URL, local media path, or an in-memory audio array paired with its sample rate
- `config` (`ProcessingConfig` or `dict`, optional): Processing options
- `progress_callback` (callable, optional): Callback function for progress updates
- `output_path` (str, optional): Save the finished audio locally as part of the task
- `download` (bool, optional): Download the finished audio even when `output_path` is omitted
- `template_id` (int, optional): Apply a saved Cleanvoice template
- `upload_type` (str, optional): Forward a backend-specific upload type hint with the edit request
- `**options`: Direct config kwargs such as `normalize=True` or `studio_sound=True`

**Returns:** `ProcessResult`

```python
from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()

def progress_callback(data):
    print(f"Status: {data['status']}, Progress: {data.get('result', {}).get('done', 0)}%")

result = client.process(
    "https://example.com/audio.mp3",
    fillers=True,
    stutters=True,
    long_silences=True,
    mouth_sounds=True,
    breath=True,
    remove_noise=True,
    normalize=True,
    studio_sound=True,
    mute_lufs=-80,
    target_lufs=-16,
    export_format="wav",
    summarize=True,
    social_content=True,
    progress_callback=progress_callback,
    output_path="enhanced_audio.wav",
)

print(result.audio.url)            # Download URL
print(result.audio.local_path)     # Local saved file
print(result.audio.statistics)     # Processing stats
print(result.transcript.text)      # Full transcript
print(result.transcript.summary)   # AI summary
```

### Processing In-Memory Audio

If you already loaded audio with `librosa`, you can pass the returned `(audio_array, sample_rate)` tuple directly. The SDK writes a temporary WAV, uploads it, and continues normally.

```python
import librosa

from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()

audio, sample_rate = librosa.load("local_audio.wav", sr=None, mono=True)
result = client.process(
    (audio, sample_rate),
    studio_sound=True,
    remove_noise=True,
    output_path="processed_from_array.mp3",
)

print(result.media.local_path)
```

### `create_edit(file_input, config=None, *, template_id=None, upload_type=None, **options)`

Create an edit job without waiting for completion.

```python
from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()

edit_id = client.create_edit(
    "https://example.com/audio.mp3",
    fillers=True,
    normalize=True,
    studio_sound=True,
    upload_type="podcast",
)

print(f'Edit ID: {edit_id}')
```

## File Upload and Download

### Upload Local Files

Upload local audio/video files for processing:

```python
import librosa

from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()

# Upload a file and get its URL
uploaded_url = client.upload_file("local_audio.mp3")
print(f"Uploaded to: {uploaded_url}")

# Upload with custom filename
uploaded_url = client.upload_file("local_audio.mp3", "my_custom_name.mp3")

# Process local file directly. The SDK uploads it automatically.
result = client.process("local_audio.mp3", fillers=True)

# Upload an in-memory array loaded with librosa.
audio, sample_rate = librosa.load("local_audio.wav", sr=None, mono=True)
uploaded_url = client.upload_file((audio, sample_rate), "from_array.wav")
```

### Download Processed Files

Download the enhanced audio files:

```python
# Download later from the result object
downloaded_path = result.audio.download("enhanced_audio.mp3")
print(f"Downloaded later to: {downloaded_path}")

# Download and get back (audio_array, sample_rate)
audio_array, sample_rate = result.download_audio(as_numpy=True)
print(audio_array.shape, sample_rate)

# Or let process handle the download inside the task
result = client.process(
    "audio.mp3",
    fillers=True,
    normalize=True,
    output_path="output.mp3",
)
print(f"Processed and saved to: {result.audio.local_path}")

# Process and download in one step
result, downloaded_path = client.process_and_download(
    "audio.mp3",
    "output.mp3",
    fillers=True,
    normalize=True,
)
print(f"Processed and saved to: {downloaded_path}")
```

`output_path` always saves the exact bytes returned by the API. The SDK does not transcode locally after download.

`result.download_audio(as_numpy=True)` and `await result.download_audio_async(as_numpy=True)` are available for audio results when you want the downloaded file loaded back into a NumPy array at the file's original sample rate.

### Manual Scenario Runner

For an end-to-end local verification that uploads, waits, downloads, and writes JSON summaries into `results_test/`, run:

```bash
CLEANVOICE_API_KEY=your-api-key python examples/manual_test_showcase.py
```

You can target specific recipes with repeated `--scenario` flags such as `audio_studio_sound_only`, `audio_all_inclusive`, `video_defaults`, or `video_all_inclusive`.

### Complete Workflow

```python
from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()

# Upload, process, and download in one line
result, output_file = client.process_and_download(
    "input_audio.mp3",     # Local file (automatically uploaded)
    "enhanced_output.mp3", # Output filename  
    fillers=True,
    normalize=True,
    summarize=True,
)
```

### `get_edit(edit_id)`

Get the status and results of an edit job.

```python
from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()

edit = client.get_edit(edit_id)

if edit.status == 'SUCCESS':
    print(f'Download URL: {edit.result.download_url}')
else:
    print(f'Status: {edit.status}')  # PENDING, STARTED, RETRY, FAILURE
```

### `check_auth()`

Verify API authentication and get account information.

```python
from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()

account = client.check_auth()
print('Account info:', account)
```

Returns a typed mapping with common fields such as `user`, `account_type`, and `credits_remaining`, while preserving any extra account data returned by the API.

## Async Support

Use `AsyncCleanvoice` for async applications:

```python
import asyncio

from cleanvoice import AsyncCleanvoice


async def main():
    async with AsyncCleanvoice.from_env() as client:
        result = await client.process(
            "https://example.com/audio.mp3",
            normalize=True,
            studio_sound=True,
            output_path="async_output.wav",
        )
        print(result.audio.local_path)


asyncio.run(main())
```

## Local Media Utilities

The SDK includes local audio/video helper utilities. These helpers do not require FFmpeg.

### Audio File Information

```python
from cleanvoice import get_audio_info

info = get_audio_info('path/to/audio.mp3')
print(f"Duration: {info.duration}s")
print(f"Sample Rate: {info.sample_rate}Hz")
print(f"Channels: {info.channels}")
```

### Video File Information

```python
from cleanvoice import get_video_info

info = get_video_info('path/to/video.mp4')
print(f"Duration: {info.duration}s")
print(f"Resolution: {info.width}x{info.height}")
print(f"FPS: {info.fps}")
print(f"Has Audio: {info.has_audio}")
```

### Extract Audio from Video

```python
from cleanvoice import extract_audio_from_video

audio_path = extract_audio_from_video(
    'path/to/video.mp4',
    'extracted_audio.wav'  # Optional output path
)
print(f"Extracted audio: {audio_path}")
```

## Configuration Options

### Audio Processing

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `fillers` | bool | False | Remove filler sounds (um, uh, etc.) |
| `stutters` | bool | False | Remove stutters |
| `long_silences` | bool | False | Remove long silences |
| `mouth_sounds` | bool | False | Remove mouth sounds |
| `hesitations` | bool | False | Remove hesitations |
| `breath` | bool or str | False | Reduce breath sounds |
| `remove_noise` | bool | True | Remove background noise |
| `keep_music` | bool | False | Preserve music sections |
| `normalize` | bool | False | Normalize audio levels |
| `studio_sound` | bool or str | False | AI-powered enhancement |

### Output Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `export_format` | str | 'auto' | Output format: auto, mp3, wav, flac, m4a |
| `mute_lufs` | float | -80 | Mute threshold in LUFS (negative) |
| `target_lufs` | float | -16 | Target loudness in LUFS (negative) |
| `export_timestamps` | bool | False | Export edit timestamps |

### AI Features

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `transcription` | bool | False | Generate speech-to-text |
| `summarize` | bool | False | Generate AI summary. The SDK auto-enables transcription. |
| `social_content` | bool | False | Optimize for social media. The SDK auto-enables summarize. |

### Other Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `video` | bool | auto-detected | Process video file |
| `merge` | bool | False | Merge multi-track audio |
| `send_email` | bool | False | Email results to account |

## Examples

### Basic Audio Cleaning

```python
from cleanvoice import Cleanvoice

cv = Cleanvoice.from_env()

result = cv.process(
    "https://example.com/podcast.mp3",
    fillers=True,
    long_silences=True,
    normalize=True,
    remove_noise=True,
)

print(f"Cleaned audio: {result.audio.url}")
print(f"Removed {result.audio.statistics.FILLER_SOUND} filler sounds")
```

### Transcription and Summary

```python
from cleanvoice import Cleanvoice

cv = Cleanvoice.from_env()

result = cv.process(
    "https://example.com/interview.wav",
    summarize=True,
    normalize=True,
)

print('Title:', result.transcript.title)
print('Summary:', result.transcript.summary)
print('Chapters:', result.transcript.chapters)
```

### Video Processing

```python
from cleanvoice import Cleanvoice

cv = Cleanvoice.from_env()

result = cv.process(
    "https://example.com/video.mp4",
    studio_sound=True,
    remove_noise=True,
    transcription=True,
    output_path='processed_video.mp4',
)

print('Returned media type:', 'video' if result.is_video else 'audio')
print('Processed file:', result.media.url)
print('Saved locally:', result.media.local_path)
```

When the SDK sees a video extension such as `.mp4`, it auto-forces `video=True` and emits a warning so callers know the returned asset will stay a video file.

### Batch Processing

```python
from cleanvoice import Cleanvoice
import time

cv = Cleanvoice.from_env()

files = [
    "https://example.com/episode1.mp3",
    "https://example.com/episode2.mp3",
    "https://example.com/episode3.mp3"
]

edit_ids = []
for file in files:
    edit_id = cv.create_edit(file, fillers=True, normalize=True)
    edit_ids.append(edit_id)

# Poll for completion
results = []
for edit_id in edit_ids:
    while True:
        edit = cv.get_edit(edit_id)
        if edit.status == 'SUCCESS':
            results.append(edit)
            break
        elif edit.status == 'FAILURE':
            print(f"Failed: {edit_id}")
            break
        else:
            time.sleep(5)  # Wait 5 seconds before polling again

print(f'All processing completed: {len(results)} files')
```

## Error Handling

```python
from cleanvoice import Cleanvoice, ApiError, FileValidationError

cv = Cleanvoice.from_env()

try:
    result = cv.process(
        "https://example.com/audio.mp3",
        fillers=True,
        normalize=True,
    )
    print('Success:', result.audio.url)
except ApiError as e:
    print(f'API Error: {e.message}')
    if e.status_code:
        print(f'HTTP Status: {e.status_code}')
        print(f'Error Code: {e.error_code}')
except FileValidationError as e:
    print(f'File Error: {e}')
except Exception as e:
    print(f'Unexpected Error: {e}')
```

## Supported File Formats

### Audio Formats
- WAV (.wav)
- MP3 (.mp3)
- OGG (.ogg)
- FLAC (.flac)
- M4A (.m4a)
- AIFF (.aiff)
- AAC (.aac)

### Video Formats
- MP4 (.mp4)
- MOV (.mov)
- WebM (.webm)
- AVI (.avi)
- MKV (.mkv)

## Requirements

- Python 3.8+
- FFmpeg is not required for the SDK's local media helper utilities

## Development

### Installing for Development

```bash
git clone https://github.com/cleanvoice/cleanvoice-python-sdk
cd cleanvoice-python-sdk
pip install -e .
```

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black src/
isort src/
```

### Type Checking

```bash
mypy src/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- 📖 [Documentation](https://docs.cleanvoice.ai)
- 📧 [Email Support](mailto:support@cleanvoice.ai)
- 🐛 [Report Issues](https://github.com/cleanvoice/cleanvoice-python-sdk/issues)