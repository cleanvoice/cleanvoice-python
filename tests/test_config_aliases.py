"""Regression tests for SDK config field aliases."""

from unittest.mock import Mock, patch

from cleanvoice import Cleanvoice
from cleanvoice.client import ApiClient
from cleanvoice.types import (
    CleanvoiceConfig,
    CreateEditRequest,
    CreateEditResponse,
    EditInput,
    ProcessingConfig,
)


def test_processing_config_accepts_studio_sound_alias():
    """The public SDK should accept the API-facing studio_sound key."""
    config = ProcessingConfig(studio_sound=True, normalize=True)

    assert config.sound_studio is True
    assert config.model_dump(by_alias=True, exclude_none=True)["studio_sound"] is True


def test_cleanvoice_process_accepts_studio_sound_dict():
    """Dict-based process config should preserve studio_sound."""
    client = Cleanvoice({"api_key": "test-key"})

    with patch("cleanvoice.cleanvoice.normalize_file_input", return_value="https://example.com/audio.mp3"), patch.object(
        client.api_client,
        "create_edit",
        return_value=CreateEditResponse(id="edit-123"),
    ) as mock_create, patch.object(client, "_poll_for_completion", return_value=Mock()), patch.object(
        client,
        "_transform_result",
        return_value=Mock(),
    ):
        client.process(
            "https://example.com/audio.mp3",
            {"studio_sound": True, "normalize": True},
        )

    sent_request = mock_create.call_args.args[0]
    assert sent_request.input.config.sound_studio is True


def test_api_client_serializes_studio_sound_for_backend():
    """Serialized payload should use the backend's expected field name."""
    client = ApiClient(CleanvoiceConfig(api_key="test-key"))
    request = CreateEditRequest(
        input=EditInput(
            files=["https://example.com/audio.mp3"],
            config=ProcessingConfig(sound_studio=True, normalize=True),
        )
    )

    with patch.object(client, "_make_request", return_value={"id": "edit-123"}) as mock_request:
        client.create_edit(request)

    payload = mock_request.call_args.kwargs["data"]
    assert payload["input"]["config"]["studio_sound"] is True
    assert "sound_studio" not in payload["input"]["config"]
