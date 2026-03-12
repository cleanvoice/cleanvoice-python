"""Tests for async client support."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, mock_open, patch

import pytest

from cleanvoice import AsyncCleanvoice
from cleanvoice.client import AsyncApiClient
from cleanvoice.types import (
    ApiError,
    CleanvoiceConfig,
    CreateEditRequest,
    CreateEditResponse,
    EditInput,
    ProcessingConfig,
    RetrieveEditResponse,
)


def test_async_api_client_create_edit():
    """AsyncApiClient should serialize edits like the sync client."""

    async def run_test():
        client = AsyncApiClient(CleanvoiceConfig(api_key="test-key"))
        request = CreateEditRequest(
            input=EditInput(
                files=["https://example.com/audio.mp3"],
                config=ProcessingConfig(studio_sound=True, normalize=True),
            )
        )

        with patch.object(client, "_make_request", new=AsyncMock(return_value={"id": "edit-123"})) as mock_request:
            response = await client.create_edit(request)

        assert response.id == "edit-123"
        mock_request.assert_awaited_once_with(
            method="POST",
            endpoint="/edits",
            data=request.model_dump(by_alias=True, exclude_none=True),
        )
        await client.aclose()

    asyncio.run(run_test())


def test_async_cleanvoice_process_downloads_output():
    """AsyncCleanvoice.process should auto-download when output_path is provided."""

    async def run_test():
        client = AsyncCleanvoice(api_key="test-key")

        with patch(
            "cleanvoice.cleanvoice.normalize_file_input_async",
            new=AsyncMock(return_value="https://example.com/audio.mp3"),
        ), patch.object(
            client.api_client,
            "create_edit",
            new=AsyncMock(return_value=CreateEditResponse(id="edit-123")),
        ), patch.object(
            client,
            "_poll_for_completion",
            new=AsyncMock(
                return_value=RetrieveEditResponse(
                    status="SUCCESS",
                    task_id="edit-123",
                    result={
                        "video": False,
                        "filename": "processed.wav",
                        "statistics": {"FILLER_SOUND": 1},
                        "download_url": "https://example.com/processed.wav",
                        "social_content": [],
                        "merged_audio_url": [],
                        "timestamps_markers_urls": None,
                        "waveform_result": None,
                    },
                )
            ),
        ), patch(
            "cleanvoice.file_handler.download_file_async",
            new=AsyncMock(return_value="processed.wav"),
        ):
            result = await client.process(
                "input.wav",
                normalize=True,
                studio_sound=True,
                output_path="processed.wav",
            )

        assert result.audio.local_path == "processed.wav"
        await client.aclose()

    asyncio.run(run_test())


def test_async_cleanvoice_from_env():
    """AsyncCleanvoice.from_env should read environment variables."""

    async def run_test():
        with patch.dict(
            "os.environ",
            {
                "CLEANVOICE_API_KEY": "env-key",
                "CLEANVOICE_BASE_URL": "https://custom.cleanvoice.ai/v2",
                "CLEANVOICE_TIMEOUT": "90",
            },
            clear=False,
        ):
            client = AsyncCleanvoice.from_env()

        assert client.config.api_key == "env-key"
        assert client.config.base_url == "https://custom.cleanvoice.ai/v2"
        assert client.config.timeout == 90
        await client.aclose()

    asyncio.run(run_test())


def test_async_download_audio_as_numpy():
    """Async audio downloads should optionally return array data and sample rate."""

    async def run_test():
        client = AsyncCleanvoice(api_key="test-key")

        with patch(
            "cleanvoice.cleanvoice.normalize_file_input_async",
            new=AsyncMock(return_value="https://example.com/audio.mp3"),
        ), patch.object(
            client.api_client,
            "create_edit",
            new=AsyncMock(return_value=CreateEditResponse(id="edit-123")),
        ), patch.object(
            client,
            "_poll_for_completion",
            new=AsyncMock(
                return_value=RetrieveEditResponse(
                    status="SUCCESS",
                    task_id="edit-123",
                    result={
                        "video": False,
                        "filename": "processed.wav",
                        "statistics": {"FILLER_SOUND": 1},
                        "download_url": "https://example.com/processed.wav",
                        "social_content": [],
                        "merged_audio_url": [],
                        "timestamps_markers_urls": None,
                        "waveform_result": None,
                    },
                )
            ),
        ), patch(
            "cleanvoice.file_handler.download_file_async",
            new=AsyncMock(return_value="processed.wav"),
        ) as mock_download, patch(
            "cleanvoice.file_handler.load_audio_array_async",
            new=AsyncMock(return_value=("array-data", 48000)),
        ) as mock_load:
            result = await client.process("input.wav", normalize=True)
            audio_array, sample_rate = await result.download_audio_async(as_numpy=True)

        assert audio_array == "array-data"
        assert sample_rate == 48000
        mock_download.assert_awaited_once_with("https://example.com/processed.wav", None)
        mock_load.assert_awaited_once_with("processed.wav")
        await client.aclose()

    asyncio.run(run_test())


def test_async_poll_for_completion_retries_success_without_result():
    """Async polling should retry when SUCCESS arrives before the payload."""

    async def run_test():
        client = AsyncCleanvoice(api_key="test-key")
        responses = [
            RetrieveEditResponse(status="SUCCESS", task_id="task-123", result=None),
            RetrieveEditResponse(
                status="SUCCESS",
                task_id="task-123",
                result={
                    "video": True,
                    "filename": "processed.mp4",
                    "statistics": {"FILLER_SOUND": 0},
                    "download_url": "https://example.com/processed.mp4",
                    "social_content": [],
                    "merged_audio_url": [],
                    "timestamps_markers_urls": None,
                    "waveform_result": None,
                },
            ),
        ]

        with patch.object(client.api_client, "retrieve_edit", new=AsyncMock(side_effect=responses)) as mock_retrieve, \
             patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            response = await client._poll_for_completion("edit-123")

        assert response.result.filename == "processed.mp4"
        assert mock_retrieve.await_count == 2
        mock_sleep.assert_awaited_once()
        await client.aclose()

    asyncio.run(run_test())


def test_async_api_client_retries_temporary_503_then_success():
    """Async transport should retry temporary service outages."""

    async def run_test():
        client = AsyncApiClient(CleanvoiceConfig(api_key="test-key"))
        unavailable_response = Mock()
        unavailable_response.status_code = 503
        unavailable_response.json.return_value = {"message": "Service unavailable"}
        unavailable_response.text = "Service unavailable"

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"user": "test@example.com"}

        with patch.object(
            client.session,
            "request",
            new=AsyncMock(side_effect=[unavailable_response, success_response]),
        ) as mock_request, patch(
            "cleanvoice.client.asyncio.sleep",
            new=AsyncMock(),
        ) as mock_sleep:
            response = await client.check_auth()

        assert response["user"] == "test@example.com"
        assert mock_request.await_count == 2
        mock_sleep.assert_awaited_once()
        await client.aclose()

    asyncio.run(run_test())


def test_async_api_client_invalid_json_raises_api_error():
    """Async transport should normalize invalid JSON into ApiError."""

    async def run_test():
        client = AsyncApiClient(CleanvoiceConfig(api_key="test-key"))
        invalid_response = Mock()
        invalid_response.status_code = 200
        invalid_response.text = "not-json"
        invalid_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

        with patch.object(
            client.session,
            "request",
            new=AsyncMock(return_value=invalid_response),
        ):
            with pytest.raises(ApiError, match="Invalid JSON response from API"):
                await client._make_request("GET", "/test")

        await client.aclose()

    asyncio.run(run_test())


def test_async_upload_file_streams_content():
    """Async uploads should stream file content instead of buffering the whole file."""

    async def run_test():
        client = AsyncApiClient(CleanvoiceConfig(api_key="test-key"))
        upload_response = Mock()
        upload_response.raise_for_status.return_value = None

        with patch.object(
            client.session, "put", new=AsyncMock(return_value=upload_response)
        ) as mock_put, patch(
            "builtins.open",
            mock_open(read_data=b"streamed-bytes"),
        ):
            await client.upload_file("test.mp3", "https://signed-url.com/upload")
            content = mock_put.await_args.kwargs["content"]
            streamed = []
            async for chunk in content:
                streamed.append(chunk)

        assert b"".join(streamed) == b"streamed-bytes"
        await client.aclose()

    asyncio.run(run_test())


def test_async_poll_for_completion_retries_transient_api_error():
    """Async polling should survive a transient retrieve failure."""

    async def run_test():
        client = AsyncCleanvoice(api_key="test-key")
        success_response = RetrieveEditResponse(
            status="SUCCESS",
            task_id="task-123",
            result={
                "video": False,
                "filename": "processed.wav",
                "statistics": {"FILLER_SOUND": 0},
                "download_url": "https://example.com/processed.wav",
                "social_content": [],
                "merged_audio_url": [],
                "timestamps_markers_urls": None,
                "waveform_result": None,
            },
        )

        with patch.object(
            client.api_client,
            "retrieve_edit",
            new=AsyncMock(
                side_effect=[ApiError("Service unavailable", 503), success_response]
            ),
        ) as mock_retrieve, patch(
            "asyncio.sleep",
            new=AsyncMock(),
        ) as mock_sleep:
            response = await client._poll_for_completion("edit-123")

        assert response.status == "SUCCESS"
        assert mock_retrieve.await_count == 2
        mock_sleep.assert_awaited_once()
        await client.aclose()

    asyncio.run(run_test())
