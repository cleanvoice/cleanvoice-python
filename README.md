# Cleanvoice Python SDK

Official Python SDK for [Cleanvoice AI](https://cleanvoice.ai) - AI-powered audio processing and enhancement.

[![PyPI version](https://badge.fury.io/py/cleanvoice-sdk.svg)](https://badge.fury.io/py/cleanvoice-sdk)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- 🎵 **Audio Processing**: Remove fillers, background noise, long silences, and more
- 📹 **Video Support**: Process audio tracks from video files without ffmpeg
- 📝 **Transcription**: Convert speech to text with high accuracy
- 📊 **Summarization**: Generate summaries, chapters, and key learnings
- 🔧 **Type Safe**: Full type hints with Pydantic models
- ⚡ **Developer Friendly**: Simple, intuitive API design
- 🔄 **Async Support**: Modern async/await patterns
- 🎛️ **Extensible**: Comprehensive configuration options
- 📦 **No FFmpeg Required**: Built-in audio/video handling with librosa, soundfile, and PyAV

## Installation

```bash
pip install cleanvoice-sdk
```

### Optional Dependencies

For development:
```bash
pip install cleanvoice-sdk[dev]
```

## Quick Start

```python
from cleanvoice import Cleanvoice

cv = Cleanvoice({'api_key': 'your-api-key-here'})

# Process audio with AI
result = cv.process(
    "https://example.com/podcast.mp3",
    {
        'fillers': True,
        'normalize': True,
        'transcription': True,
        'summarize': True
    }
)

print(f"Processed audio: {result.audio.url}")
print(f"Summary: {result.transcript.summary}")
```

## Authentication

Get your API key from the [Cleanvoice Dashboard](https://app.cleanvoice.ai/settings).

```python
from cleanvoice import Cleanvoice

cv = Cleanvoice({
    'api_key': 'your-api-key-here',
    # Optional: custom base URL
    'base_url': 'https://api.cleanvoice.ai/v2',
    # Optional: request timeout in seconds
    'timeout': 60
})
```

## API Reference

### `process(file_input, config, progress_callback=None)`

Process an audio or video file with AI enhancement.

**Parameters:**
- `file_input` (str): URL to audio/video file
- `config` (ProcessingConfig or dict): Processing options
- `progress_callback` (callable, optional): Callback function for progress updates

**Returns:** `ProcessResult`

```python
from cleanvoice import Cleanvoice

cv = Cleanvoice({'api_key': 'your-api-key'})

def progress_callback(data):
    print(f"Status: {data['status']}, Progress: {data.get('result', {}).get('done', 0)}%")

result = cv.process(
    "https://example.com/audio.mp3",
    {
        # Audio Enhancement
        'fillers': True,           # Remove filler sounds (um, uh, etc.)
        'stutters': True,          # Remove stutters
        'long_silences': True,     # Remove long silences
        'mouth_sounds': True,      # Remove mouth sounds
        'breath': True,            # Reduce breath sounds
        'remove_noise': True,      # Remove background noise
        'normalize': True,         # Normalize audio levels
        
        # Advanced Options
        'mute_lufs': -80,         # Mute threshold (negative number)
        'target_lufs': -16,       # Target loudness level
        'export_format': 'mp3',   # Output format: auto, mp3, wav, flac, m4a
        
        # AI Features
        'transcription': True,     # Generate transcript
        'summarize': True,         # Generate summary (requires transcription)
        'social_content': True,    # Optimize for social media
        
        # Video
        'video': False,           # Set to True for video files (auto-detected)
        
        # Multi-track
        'merge': False,           # Merge multi-track audio
    },
    progress_callback=progress_callback
)

# Access results
print(result.audio.url)           # Download URL
print(result.audio.statistics)    # Processing stats
print(result.transcript.text)     # Full transcript
print(result.transcript.summary)  # AI summary
```

### `create_edit(file_input, config)`

Create an edit job without waiting for completion.

```python
from cleanvoice import Cleanvoice

cv = Cleanvoice({'api_key': 'your-api-key'})

edit_id = cv.create_edit(
    "https://example.com/audio.mp3",
    {'fillers': True, 'normalize': True}
)

print(f'Edit ID: {edit_id}')
```

### `get_edit(edit_id)`

Get the status and results of an edit job.

```python
from cleanvoice import Cleanvoice

cv = Cleanvoice({'api_key': 'your-api-key'})

edit = cv.get_edit(edit_id)

if edit.status == 'SUCCESS':
    print(f'Download URL: {edit.result.download_url}')
else:
    print(f'Status: {edit.status}')  # PENDING, STARTED, RETRY, FAILURE
```

### `check_auth()`

Verify API authentication and get account information.

```python
from cleanvoice import Cleanvoice

cv = Cleanvoice({'api_key': 'your-api-key'})

account = cv.check_auth()
print('Account info:', account)
```

## File Handling Without FFmpeg

The SDK includes built-in support for audio and video files using PyAV without requiring FFmpeg:

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
| `breath` | bool | False | Reduce breath sounds |
| `remove_noise` | bool | True | Remove background noise |
| `keep_music` | bool | False | Preserve music sections |
| `normalize` | bool | False | Normalize audio levels |
| `sound_studio` | bool | False | AI-powered enhancement |

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
| `summarize` | bool | False | Generate AI summary (requires transcription) |
| `social_content` | bool | False | Optimize for social media (requires summarize) |

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

cv = Cleanvoice({'api_key': 'your-api-key'})

result = cv.process(
    "https://example.com/podcast.mp3",
    {
        'fillers': True,
        'long_silences': True,
        'normalize': True,
        'remove_noise': True
    }
)

print(f"Cleaned audio: {result.audio.url}")
print(f"Removed {result.audio.statistics.FILLER_SOUND} filler sounds")
```

### Transcription and Summary

```python
from cleanvoice import Cleanvoice

cv = Cleanvoice({'api_key': 'your-api-key'})

result = cv.process(
    "https://example.com/interview.wav",
    {
        'transcription': True,
        'summarize': True,
        'normalize': True
    }
)

print('Title:', result.transcript.title)
print('Summary:', result.transcript.summary)
print('Chapters:', result.transcript.chapters)
```

### Video Processing

```python
from cleanvoice import Cleanvoice

cv = Cleanvoice({'api_key': 'your-api-key'})

result = cv.process(
    "https://example.com/video.mp4",
    {
        'video': True,  # Optional: auto-detected
        'fillers': True,
        'transcription': True,
        'export_format': 'mp3'
    }
)

print('Processed audio:', result.audio.url)
```

### Batch Processing

```python
from cleanvoice import Cleanvoice
import time

cv = Cleanvoice({'api_key': 'your-api-key'})

files = [
    "https://example.com/episode1.mp3",
    "https://example.com/episode2.mp3",
    "https://example.com/episode3.mp3"
]

edit_ids = []
for file in files:
    edit_id = cv.create_edit(file, {'fillers': True, 'normalize': True})
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

cv = Cleanvoice({'api_key': 'your-api-key'})

try:
    result = cv.process(
        "https://example.com/audio.mp3",
        {'fillers': True, 'normalize': True}
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
- No FFmpeg required for basic audio/video processing

## Development

### Installing for Development

```bash
git clone https://github.com/cleanvoice/cleanvoice-python-sdk
cd cleanvoice-python-sdk
pip install -e .[dev]
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