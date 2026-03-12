# Cleanvoice Python SDK

> AI-powered audio and video enhancement — remove fillers, clean noise, transcribe, and summarize from Python in one call.

[![PyPI version](https://badge.fury.io/py/cleanvoice-sdk.svg)](https://badge.fury.io/py/cleanvoice-sdk)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

```bash
pip install cleanvoice-sdk
```

---

## Table of Contents

- [Quick Start](#quick-start)
- [Authentication](#authentication)
- [Common Patterns](#common-patterns)
- [Examples](#examples)
  - [Basic Audio Cleaning](#basic-audio-cleaning)
  - [Transcription & Summary](#transcription--summary)
  - [Video Processing](#video-processing)
  - [In-Memory Audio (NumPy / librosa)](#in-memory-audio-numpy--librosa)
  - [Async Usage](#async-usage)
  - [Batch Processing](#batch-processing)
- [File Upload & Download](#file-upload--download)
- [API Reference](#api-reference)
- [Configuration Options](#configuration-options)
- [Local Media Utilities](#local-media-utilities)
- [Error Handling](#error-handling)
- [Supported Formats](#supported-formats)
- [Network Resilience](#network-resilience)
- [Development](#development)

---

## Quick Start

```python
from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()  # reads CLEANVOICE_API_KEY

result = client.process(
    "https://example.com/podcast.mp3",
    fillers=True,
    normalize=True,
    studio_sound=True,
    summarize=True,
    output_path="podcast_clean.wav",
)

print(result.audio.url)              # remote download URL
print(result.audio.local_path)       # local saved file
print(result.transcript.summary)     # AI-generated summary
```

---

## Authentication

Get your API key from the [Cleanvoice Dashboard](https://app.cleanvoice.ai/settings).

**Option A — environment variable (recommended)**

```bash
export CLEANVOICE_API_KEY="your-api-key-here"
```

```python
from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()
```

**Option B — explicit constructor**

```python
from cleanvoice import Cleanvoice

client = Cleanvoice(
    api_key="your-api-key-here",
    base_url="https://api.cleanvoice.ai/v2",  # optional
    timeout=60,                                # optional
)
```

---

## Common Patterns

Choose the pattern that fits your workflow:

| Pattern | When to use |
|---|---|
| **Process + save in one call** | Backend jobs, scripts, CLI tools |
| **Process first, download later** | When you want to inspect metadata before saving |
| **Async** | FastAPI, async workers, high-concurrency services |

```python
# 1. Process and save in one call (recommended for most backends)
result = client.process(
    "recording.mp3",
    normalize=True,
    studio_sound=True,
    output_path="cleaned.wav",        # SDK uploads → waits → downloads → saves
)
print(result.audio.local_path)

# 2. Process first, download later
result = client.process("recording.mp3", normalize=True)
saved = result.audio.download("cleaned.wav")

# 3. Async
result = await async_client.process(
    "recording.mp3",
    normalize=True,
    output_path="cleaned.wav",
)
```

> **Tip:** `output_path=...` is the lowest-friction option for backend jobs — the SDK handles upload, polling, and download, returning a ready-to-use local path in `result.audio.local_path`.

---

## Examples

### Basic Audio Cleaning

```python
from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()

result = client.process(
    "https://example.com/podcast.mp3",
    fillers=True,
    long_silences=True,
    normalize=True,
    remove_noise=True,
)

print(f"Cleaned audio: {result.audio.url}")
print(f"Removed {result.audio.statistics.FILLER_SOUND} filler sounds")
```

---

### Transcription & Summary

```python
from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()

result = client.process(
    "https://example.com/interview.wav",
    summarize=True,    # auto-enables transcription
    normalize=True,
)

print("Title:   ", result.transcript.title)
print("Summary: ", result.transcript.summary)
print("Chapters:", result.transcript.chapters)
```

> `summarize=True` automatically enables transcription. `social_content=True` automatically enables summarize.

---

### Video Processing

```python
from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()

result = client.process(
    "https://example.com/video.mp4",
    studio_sound=True,
    remove_noise=True,
    transcription=True,
    output_path="processed_video.mp4",
)

print("Media type:", "video" if result.is_video else "audio")
print("Remote URL:", result.media.url)
print("Saved to:  ", result.media.local_path)
```

> When the SDK detects a video extension (`.mp4`, `.mov`, etc.) it automatically sets `video=True` and emits a warning so you know the returned asset will be a video file.

---

### In-Memory Audio (NumPy / librosa)

Pass a `(audio_array, sample_rate)` tuple directly — the SDK writes a temporary WAV, uploads it, and continues normally.

```python
import librosa
from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()

audio, sr = librosa.load("recording.wav", sr=None, mono=True)

result = client.process(
    (audio, sr),
    studio_sound=True,
    remove_noise=True,
    output_path="processed.mp3",
)

# Download back as a NumPy array
audio_out, sr_out = result.download_audio(as_numpy=True)
```

---

### Async Usage

```python
import asyncio
from cleanvoice import AsyncCleanvoice

async def main():
    async with AsyncCleanvoice.from_env() as client:
        result = await client.process(
            "https://example.com/audio.mp3",
            normalize=True,
            studio_sound=True,
            output_path="output.wav",
        )
        print(result.audio.local_path)

asyncio.run(main())
```

---

### Batch Processing

Submit all jobs first, then poll — avoids waiting serially between files.

```python
import time
from cleanvoice import Cleanvoice

client = Cleanvoice.from_env()

files = [
    "https://example.com/episode1.mp3",
    "https://example.com/episode2.mp3",
    "https://example.com/episode3.mp3",
]

# Submit all jobs
edit_ids = [
    client.create_edit(f, fillers=True, normalize=True)
    for f in files
]

# Poll for completion
results = []
for edit_id in edit_ids:
    while True:
        edit = client.get_edit(edit_id)
        if edit.status == "SUCCESS":
            results.append(edit)
            break
        elif edit.status == "FAILURE":
            print(f"Failed: {edit_id}")
            break
        time.sleep(5)

print(f"Completed: {len(results)}/{len(files)} files")
```

---

## File Upload & Download

### Upload

```python
# Upload a file and get its remote URL
url = client.upload_file("recording.mp3")

# Upload with a custom remote filename
url = client.upload_file("recording.mp3", "my_episode.mp3")

# Upload a librosa array
import librosa
audio, sr = librosa.load("recording.wav", sr=None, mono=True)
url = client.upload_file((audio, sr), "from_array.wav")

# Local files are uploaded automatically when passed to process()
result = client.process("local_audio.mp3", fillers=True)
```

### Download

```python
# Download from a result object
path = result.audio.download("enhanced.mp3")

# Download back as a NumPy array
audio, sr = result.download_audio(as_numpy=True)

# Async download as NumPy array
audio, sr = await result.download_audio_async(as_numpy=True)

# One-liner: process and download together
result, path = client.process_and_download(
    "audio.mp3",
    "output.mp3",
    fillers=True,
    normalize=True,
)
```

> `output_path` saves the exact bytes returned by the API — the SDK does not transcode locally after download.

---

## API Reference

### `process()`

```python
client.process(
    file_input,           # str (URL or path) or (array, sample_rate)
    config=None,          # ProcessingConfig or dict
    progress_callback=None,
    *,
    output_path=None,     # save finished audio as part of the task
    download=False,       # download even without output_path
    template_id=None,     # apply a saved Cleanvoice template
    upload_type=None,     # backend-specific upload type hint
    **options,            # normalize=True, fillers=True, etc.
)
# Returns: ProcessResult
```

With a progress callback:

```python
def on_progress(data):
    pct = data.get("result", {}).get("done", 0)
    print(f"Status: {data['status']}  {pct}%")

result = client.process(
    "audio.mp3",
    fillers=True, stutters=True, long_silences=True,
    mouth_sounds=True, breath=True, remove_noise=True,
    normalize=True, studio_sound=True,
    mute_lufs=-80, target_lufs=-16,
    export_format="wav",
    summarize=True, social_content=True,
    progress_callback=on_progress,
    output_path="enhanced.wav",
)
```

---

### `create_edit()`

Submit a job without waiting for completion. Returns an `edit_id`.

```python
edit_id = client.create_edit(
    "https://example.com/audio.mp3",
    fillers=True,
    normalize=True,
    studio_sound=True,
    upload_type="podcast",
)
```

---

### `get_edit(edit_id)`

Check the status and results of a submitted job.

```python
edit = client.get_edit(edit_id)

if edit.status == "SUCCESS":
    print(edit.result.download_url)
else:
    print(edit.status)  # PENDING | STARTED | RETRY | FAILURE
```

---

### `check_auth()`

Verify credentials and inspect account details.

```python
account = client.check_auth()
print(account.user)
print(account.credits_remaining)
```

Returns a typed mapping with `user`, `account_type`, `credits_remaining`, plus any additional fields returned by the API.

---

## Configuration Options

### Audio Processing

| Option | Type | Default | Description |
|---|---|---|---|
| `fillers` | bool | `False` | Remove filler sounds (um, uh, etc.) |
| `stutters` | bool | `False` | Remove stutters |
| `long_silences` | bool | `False` | Remove long silences |
| `mouth_sounds` | bool | `False` | Remove mouth sounds |
| `hesitations` | bool | `False` | Remove hesitations |
| `breath` | bool or str | `False` | Reduce breath sounds |
| `remove_noise` | bool | `True` | Remove background noise |
| `keep_music` | bool | `False` | Preserve music sections |
| `normalize` | bool | `False` | Normalize audio levels |
| `studio_sound` | bool or str | `False` | AI-powered enhancement |

### Output

| Option | Type | Default | Description |
|---|---|---|---|
| `export_format` | str | `'auto'` | `auto`, `mp3`, `wav`, `flac`, `m4a` |
| `mute_lufs` | float | `-80` | Mute threshold in LUFS |
| `target_lufs` | float | `-16` | Target loudness in LUFS |
| `export_timestamps` | bool | `False` | Export edit timestamps |

### AI Features

| Option | Type | Default | Description |
|---|---|---|---|
| `transcription` | bool | `False` | Generate speech-to-text |
| `summarize` | bool | `False` | Generate AI summary (auto-enables transcription) |
| `social_content` | bool | `False` | Social media optimization (auto-enables summarize) |

### Other

| Option | Type | Default | Description |
|---|---|---|---|
| `video` | bool | auto | Process as video file |
| `merge` | bool | `False` | Merge multi-track audio |
| `send_email` | bool | `False` | Email results to account |

---

## Local Media Utilities

Pure-Python helpers — **FFmpeg is not required**.

### Audio Info

```python
from cleanvoice import get_audio_info

info = get_audio_info("recording.mp3")
print(f"Duration:    {info.duration}s")
print(f"Sample rate: {info.sample_rate}Hz")
print(f"Channels:    {info.channels}")
```

### Video Info

```python
from cleanvoice import get_video_info

info = get_video_info("video.mp4")
print(f"Duration:   {info.duration}s")
print(f"Resolution: {info.width}x{info.height}")
print(f"FPS:        {info.fps}")
print(f"Has audio:  {info.has_audio}")
```

### Extract Audio from Video

```python
from cleanvoice import extract_audio_from_video

audio_path = extract_audio_from_video("video.mp4", "extracted.wav")
```

---

## Error Handling

```python
from cleanvoice import Cleanvoice, ApiError, FileValidationError

client = Cleanvoice.from_env()

try:
    result = client.process("audio.mp3", fillers=True, normalize=True)
    print("Success:", result.audio.url)
except FileValidationError as e:
    print(f"File error: {e}")
except ApiError as e:
    print(f"API error {e.status_code} [{e.error_code}]: {e.message}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

---

## Network Resilience

The client automatically retries brief transient failures including connection resets, connect/read timeouts on safe requests, and temporary HTTP errors (`429`, `502`, `503`, `504`). This is designed to absorb short backend restart windows without immediately failing common flows.

Retries cover: `check_auth()`, `create_edit()`, `get_edit()`, and `process()` during polling. Edit creation retries are intentionally conservative to avoid duplicating work.

---

## Supported Formats

**Audio:** `.wav` `.mp3` `.ogg` `.flac` `.m4a` `.aiff` `.aac`

**Video:** `.mp4` `.mov` `.webm` `.avi` `.mkv`

---

## Development

```bash
git clone https://github.com/cleanvoice/cleanvoice-python-sdk
cd cleanvoice-python-sdk
pip install -e .
```

```bash
pytest                   # run tests
black src/ && isort src/ # format
mypy src/                # type check
```

**End-to-end local test** — uploads, waits, downloads, and writes JSON summaries into `results_test/`:

```bash
CLEANVOICE_API_KEY=your-key python examples/manual_test_showcase.py

# target specific scenarios:
# --scenario audio_studio_sound_only
# --scenario audio_all_inclusive
# --scenario video_defaults
# --scenario video_all_inclusive
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

---

## Requirements

- Python 3.8+
- FFmpeg not required

## Support

| | |
|---|---|
| 📖 Documentation | [docs.cleanvoice.ai](https://docs.cleanvoice.ai) |
| 📧 Email | [support@cleanvoice.ai](mailto:support@cleanvoice.ai) |
| 🐛 Issues | [GitHub Issues](https://github.com/cleanvoice/cleanvoice-python-sdk/issues) |

## License

MIT — see [LICENSE](LICENSE) for details.
