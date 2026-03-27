# Changelog

All notable changes to the Cleanvoice Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.3] - 2026-03-27

### Changed
- Bumped package metadata, the exported SDK version, and the HTTP user agent to `2.0.3`.

## [2.0.2] - 2026-03-18

### Fixed
- Accepted additional backend worker phase statuses such as `PREPROCESSING`, `CLASSIFICATION`, `EDITING`, and `EXPORT` when polling `GET /edits/{id}`.
- Prevented `RetrieveEditResponse` validation failures during `process()`, `get_edit()`, and `process_and_download()` when the API returns intermediate worker states.

### Testing
- Added regression coverage for polling through backend phase statuses before `SUCCESS`.
- Verified the hotfix against the live API with local test media, including cases that surfaced `CLASSIFICATION` and `EDITING`.

## [2.0.1] - 2026-03-12

### Added
- `AsyncCleanvoice` and `AsyncApiClient` for async processing and polling.
- `Cleanvoice.from_env()` and `AsyncCleanvoice.from_env()` convenience constructors.
- Result helpers such as `result.audio.download(...)` and `await result.audio.download_async(...)`.

### Changed
- `process()` and `create_edit()` now accept direct keyword options like `normalize=True` and `studio_sound=True`.
- `process()` can save the finished audio as part of the task via `output_path=...`.
- `studio_sound` is now the canonical public config field. `sound_studio` remains accepted as a legacy alias.
- SDK result models now mirror the v2 API and `worker_new` output shape more closely, including summary/social/waveform metadata.
- Transport retries and polling are more resilient to brief backend restarts and transient failures.
- Local media support is now part of the base `cleanvoice-sdk` install.
- Package metadata, public version exports, and HTTP user agent now report `2.0.1`.
- README and release packaging were refreshed before publishing the `2.0.1` artifacts.

## [1.0.1] - 2024-12-26

### Added
- **File Upload Support**: Upload local audio/video files for processing
  - `upload_file(file_path, filename=None)` method for explicit file uploads
  - `process()` method now accepts local file paths with automatic upload
  - Support for custom filenames during upload
  - Comprehensive error handling for file upload operations

- **File Download Support**: Download processed audio files locally
  - `download_file(url, output_path=None)` method for downloading processed files
  - Automatic filename extraction from URLs when no output path specified
  - Support for custom output paths and filenames

- **Complete Workflow Method**: One-step processing and downloading
  - `process_and_download()` method for streamlined workflow
  - Combines upload, processing, and download in a single call
  - Perfect for batch processing scenarios

- **Low-level API Methods**: Direct access to upload functionality
  - `get_signed_upload_url(filename)` for getting signed upload URLs
  - `upload_file(file_path, signed_url)` for direct file uploads
  - Full compatibility with Cleanvoice API v2 upload endpoints

### Enhanced
- **File Input Flexibility**: `process()` method now supports both URLs and local files
- **Error Handling**: Improved error messages and validation for file operations
- **Type Safety**: Full type hints for all new methods and parameters
- **Documentation**: Comprehensive examples and usage patterns

### Examples Added
- `examples/file_upload_example.py` - Detailed file upload demonstrations
- `examples/complete_workflow.py` - End-to-end workflow examples
- Updated `examples/basic_usage.py` with file upload/download patterns

### Testing
- **22 new test cases** covering all file upload and download functionality
- Comprehensive error handling tests
- Integration tests for complete workflows
- Mocked tests to avoid external dependencies during testing

### Documentation
- Updated README.md with file upload and download sections
- Added usage examples for all new methods
- Documented complete workflow patterns
- Enhanced API reference documentation

## [1.0.0] - 2024-12-01

### Added
- Initial release of Cleanvoice Python SDK
- Audio processing with AI enhancement
- Video file support without ffmpeg dependency
- Speech-to-text transcription
- AI-powered summarization
- Type-safe API with Pydantic models
- Comprehensive configuration options
- Progress callback support
- Error handling and validation

### Features
- Remove fillers, stutters, and background noise
- Normalize audio levels and enhance quality
- Generate transcripts and summaries
- Support for multiple audio/video formats
- Async/await patterns for modern Python development