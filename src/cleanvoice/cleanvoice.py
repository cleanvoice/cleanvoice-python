"""Main Cleanvoice SDK classes."""

import asyncio
import os
import time
import warnings
from typing import Any, Callable, Dict, Optional, Tuple, Union

from .client import ApiClient, AsyncApiClient, is_transient_api_error
from .file_handler import (
    download_file,
    download_file_async,
    is_valid_video_file,
    MediaInput,
    normalize_file_input,
    normalize_file_input_async,
    upload_local_file,
    upload_local_file_async,
    validate_config,
)
from .types import (
    AccountInfo,
    ApiError,
    CleanvoiceConfig,
    CreateEditRequest,
    EditInput,
    EditResult,
    FileValidationError,
    ProcessingConfig,
    ProcessResult,
    RetrieveEditResponse,
)

ConfigInput = Optional[Union[ProcessingConfig, Dict[str, Any]]]
ProgressCallback = Optional[Callable[[Dict[str, Any]], None]]


class _CleanvoiceBase:
    """Shared orchestration for sync and async Cleanvoice clients."""

    def __init__(self, config: CleanvoiceConfig):
        self.config = config

    @staticmethod
    def _coerce_client_config(
        config: Optional[Union[CleanvoiceConfig, Dict[str, Any]]] = None,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CleanvoiceConfig:
        """Build a CleanvoiceConfig from flexible user inputs."""
        if isinstance(config, CleanvoiceConfig):
            data = config.model_dump(exclude_none=True)
        elif isinstance(config, dict):
            data = dict(config)
        elif config is None:
            data = {}
        else:
            raise ValueError("config must be a CleanvoiceConfig, dict, or None")

        if api_key is not None:
            data["api_key"] = api_key
        if base_url is not None:
            data["base_url"] = base_url
        if timeout is not None:
            data["timeout"] = timeout

        resolved = CleanvoiceConfig(**data)
        if not resolved.api_key:
            raise ValueError("API key is required")
        return resolved

    @classmethod
    def from_env(
        cls,
        *,
        api_key_env: str = "CLEANVOICE_API_KEY",
        base_url_env: str = "CLEANVOICE_BASE_URL",
        timeout_env: str = "CLEANVOICE_TIMEOUT",
    ):
        """Create a client from environment variables."""
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(f"Environment variable {api_key_env} is required")

        timeout_value = os.getenv(timeout_env)
        timeout = int(timeout_value) if timeout_value else None

        return cls(
            api_key=api_key,
            base_url=os.getenv(base_url_env) or None,
            timeout=timeout,
        )

    @staticmethod
    def _build_processing_config(
        file_input: MediaInput,
        config: ConfigInput,
        overrides: Dict[str, Any],
    ) -> ProcessingConfig:
        """Merge dict/model config with direct keyword overrides."""
        config_data: Dict[str, Any] = {}

        if isinstance(config, ProcessingConfig):
            config_data = config.model_dump(exclude_none=True)
        elif isinstance(config, dict):
            config_data = dict(config)
        elif config is not None:
            raise ValueError("config must be a ProcessingConfig, dict, or None")

        config_data.update({key: value for key, value in overrides.items() if value is not None})
        processing_config = ProcessingConfig(**config_data)

        # Match backend behavior: social content implies summarize, summarize implies transcription.
        if processing_config.social_content:
            processing_config.summarize = True
        if processing_config.summarize:
            processing_config.transcription = True

        detected_video_input = isinstance(file_input, str) and is_valid_video_file(
            file_input
        )
        if detected_video_input:
            if processing_config.video is False:
                warnings.warn(
                    "Video input detected. Overriding video=False so the SDK returns the processed video file.",
                    stacklevel=3,
                )
            elif processing_config.video is None:
                warnings.warn(
                    "Video input detected. The SDK will process this file as video and return the processed video file.",
                    stacklevel=3,
                )
            processing_config.video = True
        elif processing_config.video is None:
            processing_config.video = False

        validate_config(processing_config.model_dump(exclude_none=True))
        return processing_config

    @staticmethod
    def _build_edit_request(
        file_url: str,
        config: ProcessingConfig,
        *,
        template_id: Optional[int] = None,
        upload_type: Optional[str] = None,
    ) -> CreateEditRequest:
        """Build the request payload expected by the v2 API."""
        return CreateEditRequest(
            input=EditInput(
                files=[file_url],
                config=config,
                template_id=template_id,
                upload_type=upload_type,
            )
        )

    @staticmethod
    def _emit_progress(
        progress_callback: ProgressCallback,
        response: RetrieveEditResponse,
        edit_id: str,
        attempt: int,
    ) -> None:
        """Safely emit a progress update."""
        if not progress_callback:
            return

        try:
            progress_callback(
                {
                    "status": response.status,
                    "result": response.result,
                    "edit_id": edit_id,
                    "attempt": attempt,
                }
            )
        except Exception:
            pass

    @staticmethod
    def _transform_result(response: RetrieveEditResponse) -> ProcessResult:
        """Transform API response to a Python-friendly result."""
        if not response.result:
            raise ApiError("Edit result not available")

        if isinstance(response.result, EditResult):
            edit_result = response.result
        elif isinstance(response.result, dict) and "download_url" in response.result:
            edit_result = EditResult(**response.result)
        else:
            raise ApiError(
                "Edit is still in progress, cannot transform to final result"
            )

        summarization = edit_result.summarization
        transcript_result = None

        if edit_result.transcription:
            transcription = edit_result.transcription
            full_text = " ".join(paragraph.text for paragraph in transcription.paragraphs)
            transcript_result = ProcessResult.TranscriptResult(
                text=full_text,
                paragraphs=transcription.paragraphs,
                detailed=transcription.transcription,
                summary=summarization.summary if summarization else None,
                title=summarization.title if summarization else None,
                chapters=summarization.chapters if summarization else None,
                summarization=summarization,
            )

        return ProcessResult(
            audio=ProcessResult.AudioResult(
                url=edit_result.download_url,
                filename=edit_result.filename,
                statistics=edit_result.statistics,
                merged_audio_url=edit_result.merged_audio_url,
                timestamps_markers_urls=edit_result.timestamps_markers_urls,
                waveform_result=edit_result.waveform_result,
            ),
            video=edit_result.video,
            transcript=transcript_result,
            summarization=summarization,
            social_content=edit_result.social_content,
            timestamps_markers_urls=edit_result.timestamps_markers_urls,
            waveform_result=edit_result.waveform_result,
            task_id=response.task_id if isinstance(response.task_id, str) else None,
        )

    @staticmethod
    def _should_download(output_path: Optional[str], download: bool) -> bool:
        return download or output_path is not None

    @staticmethod
    def _failure_message(edit_id: str, response: RetrieveEditResponse) -> str:
        """Build a useful error message for failed edit jobs."""
        detail = None
        result = response.result

        if hasattr(result, "model_dump"):
            result = result.model_dump(exclude_none=True)

        if isinstance(result, dict):
            detail = result.get("message") or result.get("state") or result.get("job_name")
        elif isinstance(result, str):
            detail = result

        if detail:
            return f"Edit processing failed for {edit_id}: {detail}"
        return f"Edit processing failed for {edit_id}"


class Cleanvoice(_CleanvoiceBase):
    """Synchronous Cleanvoice SDK client."""

    def __init__(
        self,
        config: Optional[Union[CleanvoiceConfig, Dict[str, Any]]] = None,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        resolved_config = self._coerce_client_config(
            config, api_key=api_key, base_url=base_url, timeout=timeout
        )
        super().__init__(resolved_config)
        self.api_client = ApiClient(resolved_config)

    def __enter__(self) -> "Cleanvoice":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def process(
        self,
        file_input: MediaInput,
        config: ConfigInput = None,
        progress_callback: ProgressCallback = None,
        *,
        output_path: Optional[str] = None,
        download: bool = False,
        template_id: Optional[int] = None,
        upload_type: Optional[str] = None,
        **config_kwargs: Any,
    ) -> ProcessResult:
        """Process a file and optionally download the finished audio."""
        processing_config = self._build_processing_config(
            file_input, config, config_kwargs
        )

        try:
            file_url = normalize_file_input(file_input, self.api_client)
            edit_request = self._build_edit_request(
                file_url,
                processing_config,
                template_id=template_id,
                upload_type=upload_type,
            )
            edit_response = self.api_client.create_edit(edit_request)
            response = self._poll_for_completion(
                edit_response.id, progress_callback=progress_callback
            )
            result = self._transform_result(response)

            if self._should_download(output_path, download):
                result.download_audio(output_path)

            return result
        except Exception as error:
            if isinstance(error, (ApiError, FileValidationError, ValueError)):
                raise error
            raise ApiError(f"An unknown error occurred during processing: {error}")

    def create_edit(
        self,
        file_input: MediaInput,
        config: ConfigInput = None,
        *,
        template_id: Optional[int] = None,
        upload_type: Optional[str] = None,
        **config_kwargs: Any,
    ) -> str:
        """Create an edit job and return its task id."""
        processing_config = self._build_processing_config(
            file_input, config, config_kwargs
        )

        try:
            file_url = normalize_file_input(file_input, self.api_client)
            edit_request = self._build_edit_request(
                file_url,
                processing_config,
                template_id=template_id,
                upload_type=upload_type,
            )
            response = self.api_client.create_edit(edit_request)
            return response.id
        except Exception as error:
            if isinstance(error, (ApiError, FileValidationError, ValueError)):
                raise error
            raise ApiError(
                f"An unknown error occurred while creating edit: {error}"
            )

    def get_edit(self, edit_id: str) -> RetrieveEditResponse:
        """Get the status and results of an edit job."""
        try:
            return self.api_client.retrieve_edit(edit_id)
        except Exception as error:
            if isinstance(error, ApiError):
                raise error
            raise ApiError(
                f"An unknown error occurred while retrieving edit: {error}"
            )

    def upload_file(
        self, file_path: MediaInput, filename: Optional[str] = None
    ) -> str:
        """Upload a local file and return the resulting public URL."""
        return upload_local_file(file_path, self.api_client, filename=filename)

    def download_file(self, url: str, output_path: Optional[str] = None) -> str:
        """Download a processed file from the given URL."""
        try:
            return download_file(url, output_path)
        except FileValidationError as error:
            message = str(error)
            if message.startswith("Failed to download file: "):
                message = message.replace("Failed to download file: ", "", 1)
            raise ApiError(f"File download failed: {message}")

    def process_and_download(
        self,
        file_input: MediaInput,
        output_path: Optional[str] = None,
        config: ConfigInput = None,
        progress_callback: ProgressCallback = None,
        *,
        template_id: Optional[int] = None,
        upload_type: Optional[str] = None,
        **config_kwargs: Any,
    ) -> Tuple[ProcessResult, str]:
        """Process a file and return the local downloaded output path."""
        result = self.process(
            file_input,
            config=config,
            progress_callback=progress_callback,
            output_path=output_path,
            download=True,
            template_id=template_id,
            upload_type=upload_type,
            **config_kwargs,
        )
        if isinstance(result.audio.local_path, str):
            return result, result.audio.local_path
        return result, result.audio.download(output_path)

    def check_auth(self) -> AccountInfo:
        """Check if authentication is working."""
        try:
            return self.api_client.check_auth()
        except Exception as error:
            if isinstance(error, ApiError):
                raise error
            raise ApiError(f"Authentication check failed: {error}")

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self.api_client.close()

    def _poll_for_completion(
        self,
        edit_id: str,
        max_attempts: int = 60,
        initial_delay: float = 2.0,
        progress_callback: ProgressCallback = None,
        success_result_grace_attempts: int = 5,
        max_transient_errors: int = 5,
    ) -> RetrieveEditResponse:
        """Poll for completion with exponential backoff."""
        attempts = 0
        delay = initial_delay
        missing_success_result_attempts = 0
        transient_errors = 0

        while attempts < max_attempts:
            try:
                response = self.api_client.retrieve_edit(edit_id)
                transient_errors = 0
            except ApiError as error:
                if not is_transient_api_error(error):
                    raise

                transient_errors += 1
                if transient_errors >= max_transient_errors:
                    raise ApiError(
                        f"Polling failed after {transient_errors} transient transport errors: {error}",
                        status_code=error.status_code,
                        error_code=error.error_code,
                    )

                time.sleep(min(delay, 5.0))
                continue

            self._emit_progress(progress_callback, response, edit_id, attempts + 1)

            if response.status == "SUCCESS":
                if response.result is None:
                    missing_success_result_attempts += 1
                    if missing_success_result_attempts >= success_result_grace_attempts:
                        raise ApiError(
                            "Edit completed but the result payload never became available"
                        )
                    time.sleep(min(delay, 5.0))
                    attempts += 1
                    continue
                return response

            if response.status == "FAILURE":
                raise ApiError(self._failure_message(edit_id, response))

            time.sleep(delay)
            attempts += 1
            delay = min(delay * 1.5, 30.0)

        raise ApiError("Edit processing timeout - maximum polling attempts reached")


class AsyncCleanvoice(_CleanvoiceBase):
    """Asynchronous Cleanvoice SDK client."""

    def __init__(
        self,
        config: Optional[Union[CleanvoiceConfig, Dict[str, Any]]] = None,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        resolved_config = self._coerce_client_config(
            config, api_key=api_key, base_url=base_url, timeout=timeout
        )
        super().__init__(resolved_config)
        self.api_client = AsyncApiClient(resolved_config)

    async def __aenter__(self) -> "AsyncCleanvoice":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.aclose()

    async def process(
        self,
        file_input: MediaInput,
        config: ConfigInput = None,
        progress_callback: ProgressCallback = None,
        *,
        output_path: Optional[str] = None,
        download: bool = False,
        template_id: Optional[int] = None,
        upload_type: Optional[str] = None,
        **config_kwargs: Any,
    ) -> ProcessResult:
        """Process a file asynchronously and optionally download the result."""
        processing_config = self._build_processing_config(
            file_input, config, config_kwargs
        )

        try:
            file_url = await normalize_file_input_async(file_input, self.api_client)
            edit_request = self._build_edit_request(
                file_url,
                processing_config,
                template_id=template_id,
                upload_type=upload_type,
            )
            edit_response = await self.api_client.create_edit(edit_request)
            response = await self._poll_for_completion(
                edit_response.id, progress_callback=progress_callback
            )
            result = self._transform_result(response)

            if self._should_download(output_path, download):
                await result.download_audio_async(output_path)

            return result
        except Exception as error:
            if isinstance(error, (ApiError, FileValidationError, ValueError)):
                raise error
            raise ApiError(f"An unknown error occurred during processing: {error}")

    async def create_edit(
        self,
        file_input: MediaInput,
        config: ConfigInput = None,
        *,
        template_id: Optional[int] = None,
        upload_type: Optional[str] = None,
        **config_kwargs: Any,
    ) -> str:
        """Create an edit job asynchronously and return its task id."""
        processing_config = self._build_processing_config(
            file_input, config, config_kwargs
        )

        try:
            file_url = await normalize_file_input_async(file_input, self.api_client)
            edit_request = self._build_edit_request(
                file_url,
                processing_config,
                template_id=template_id,
                upload_type=upload_type,
            )
            response = await self.api_client.create_edit(edit_request)
            return response.id
        except Exception as error:
            if isinstance(error, (ApiError, FileValidationError, ValueError)):
                raise error
            raise ApiError(
                f"An unknown error occurred while creating edit: {error}"
            )

    async def get_edit(self, edit_id: str) -> RetrieveEditResponse:
        """Get the status and results of an edit job."""
        try:
            return await self.api_client.retrieve_edit(edit_id)
        except Exception as error:
            if isinstance(error, ApiError):
                raise error
            raise ApiError(
                f"An unknown error occurred while retrieving edit: {error}"
            )

    async def upload_file(
        self, file_path: MediaInput, filename: Optional[str] = None
    ) -> str:
        """Upload a local file and return the resulting public URL."""
        return await upload_local_file_async(
            file_path, self.api_client, filename=filename
        )

    async def download_file(self, url: str, output_path: Optional[str] = None) -> str:
        """Download a processed file from the given URL."""
        try:
            return await download_file_async(url, output_path)
        except FileValidationError as error:
            message = str(error)
            if message.startswith("Failed to download file: "):
                message = message.replace("Failed to download file: ", "", 1)
            raise ApiError(f"File download failed: {message}")

    async def process_and_download(
        self,
        file_input: MediaInput,
        output_path: Optional[str] = None,
        config: ConfigInput = None,
        progress_callback: ProgressCallback = None,
        *,
        template_id: Optional[int] = None,
        upload_type: Optional[str] = None,
        **config_kwargs: Any,
    ) -> Tuple[ProcessResult, str]:
        """Process a file and return the local downloaded output path."""
        result = await self.process(
            file_input,
            config=config,
            progress_callback=progress_callback,
            output_path=output_path,
            download=True,
            template_id=template_id,
            upload_type=upload_type,
            **config_kwargs,
        )
        if isinstance(result.audio.local_path, str):
            return result, result.audio.local_path

        downloaded_path = await result.audio.download_async(output_path)
        return result, downloaded_path

    async def check_auth(self) -> AccountInfo:
        """Check if authentication is working."""
        try:
            return await self.api_client.check_auth()
        except Exception as error:
            if isinstance(error, ApiError):
                raise error
            raise ApiError(f"Authentication check failed: {error}")

    async def aclose(self) -> None:
        """Close the underlying async HTTP session."""
        await self.api_client.aclose()

    async def _poll_for_completion(
        self,
        edit_id: str,
        max_attempts: int = 60,
        initial_delay: float = 2.0,
        progress_callback: ProgressCallback = None,
        success_result_grace_attempts: int = 5,
        max_transient_errors: int = 5,
    ) -> RetrieveEditResponse:
        """Poll for completion asynchronously with exponential backoff."""
        attempts = 0
        delay = initial_delay
        missing_success_result_attempts = 0
        transient_errors = 0

        while attempts < max_attempts:
            try:
                response = await self.api_client.retrieve_edit(edit_id)
                transient_errors = 0
            except ApiError as error:
                if not is_transient_api_error(error):
                    raise

                transient_errors += 1
                if transient_errors >= max_transient_errors:
                    raise ApiError(
                        f"Polling failed after {transient_errors} transient transport errors: {error}",
                        status_code=error.status_code,
                        error_code=error.error_code,
                    )

                await asyncio.sleep(min(delay, 5.0))
                continue

            self._emit_progress(progress_callback, response, edit_id, attempts + 1)

            if response.status == "SUCCESS":
                if response.result is None:
                    missing_success_result_attempts += 1
                    if missing_success_result_attempts >= success_result_grace_attempts:
                        raise ApiError(
                            "Edit completed but the result payload never became available"
                        )
                    await asyncio.sleep(min(delay, 5.0))
                    attempts += 1
                    continue
                return response

            if response.status == "FAILURE":
                raise ApiError(self._failure_message(edit_id, response))

            await asyncio.sleep(delay)
            attempts += 1
            delay = min(delay * 1.5, 30.0)

        raise ApiError("Edit processing timeout - maximum polling attempts reached")
