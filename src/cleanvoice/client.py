"""HTTP clients for the Cleanvoice SDK."""

import asyncio
import json
import os
import random
import time
from typing import Any, AsyncIterator, Dict, Optional, Tuple

import httpx
import requests

from .types import (
    AccountInfo,
    ApiError,
    CleanvoiceConfig,
    CreateEditRequest,
    CreateEditResponse,
    RetrieveEditResponse,
)

DEFAULT_V2_BASE_URL = "https://api.cleanvoice.ai/v2"
DEFAULT_V1_BASE_URL = "https://api.cleanvoice.ai/v1"
USER_AGENT = "cleanvoice-python-sdk/2.0.3"
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
NON_IDEMPOTENT_RETRYABLE_STATUS_CODES = frozenset({429, 503, 504})
IDEMPOTENT_METHODS = frozenset({"DELETE", "GET", "HEAD", "OPTIONS"})
DEFAULT_RETRY_BASE_DELAY = 0.5
DEFAULT_RETRY_MAX_DELAY = 2.0
UPLOAD_CHUNK_SIZE = 64 * 1024


def _resolve_v2_base_url(config: CleanvoiceConfig) -> str:
    return (config.base_url or DEFAULT_V2_BASE_URL).rstrip("/")


def _resolve_v1_base_url(config: CleanvoiceConfig) -> str:
    if config.base_url:
        return config.base_url.replace("/v2", "/v1").rstrip("/")
    return DEFAULT_V1_BASE_URL


def _extract_error_details(
    status_code: int, response_body: Any, response_text: str
) -> Tuple[str, Optional[str]]:
    if isinstance(response_body, dict):
        return response_body.get("message", f"HTTP {status_code}"), response_body.get(
            "code"
        )
    return f"HTTP {status_code}: {response_text}", None


def _is_idempotent_method(method: str) -> bool:
    return method.upper() in IDEMPOTENT_METHODS


def _should_retry_status(method: str, status_code: int) -> bool:
    if _is_idempotent_method(method):
        return status_code in DEFAULT_RETRYABLE_STATUS_CODES
    return status_code in NON_IDEMPOTENT_RETRYABLE_STATUS_CODES


def _get_retry_delay(retry_count: int) -> float:
    base_delay = min(
        DEFAULT_RETRY_BASE_DELAY * (2 ** max(retry_count - 1, 0)),
        DEFAULT_RETRY_MAX_DELAY,
    )
    return base_delay + random.uniform(0.0, 0.25)


def _should_retry_requests_exception(method: str, error: requests.exceptions.RequestException) -> bool:
    if _is_idempotent_method(method):
        retryable_errors = (
            requests.exceptions.ConnectionError,
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ReadTimeout,
        )
    else:
        retryable_errors = (
            requests.exceptions.ConnectionError,
            requests.exceptions.ConnectTimeout,
        )
    return isinstance(error, retryable_errors)


def _should_retry_httpx_exception(method: str, error: httpx.RequestError) -> bool:
    if _is_idempotent_method(method):
        retryable_errors = (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.PoolTimeout,
            httpx.ReadTimeout,
            httpx.RemoteProtocolError,
        )
    else:
        retryable_errors = (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.PoolTimeout,
        )
    return isinstance(error, retryable_errors)


def is_transient_api_error(error: ApiError) -> bool:
    """Return True when an ApiError likely came from a transient transport issue."""
    if error.status_code in DEFAULT_RETRYABLE_STATUS_CODES:
        return True
    if error.status_code is not None:
        return False

    normalized_message = error.message.lower()
    return any(
        token in normalized_message
        for token in (
            "connection",
            "network",
            "request failed",
            "temporarily unavailable",
            "timed out",
            "timeout",
        )
    )


async def _iter_file_chunks(file_path: str, chunk_size: int = UPLOAD_CHUNK_SIZE) -> AsyncIterator[bytes]:
    """Yield file content incrementally for async uploads."""
    with open(file_path, "rb") as file_handle:
        while True:
            chunk = await asyncio.to_thread(file_handle.read, chunk_size)
            if not chunk:
                break
            yield chunk


class ApiClient:
    """Synchronous HTTP client for the Cleanvoice API."""

    def __init__(self, config: CleanvoiceConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-API-Key": config.api_key,
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            }
        )

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request to the API."""
        url = f"{(base_url or _resolve_v2_base_url(self.config)).rstrip('/')}/{endpoint.lstrip('/')}"
        retry_count = 0

        while True:
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    timeout=timeout or self.config.timeout,
                )

                if response.status_code >= 400:
                    try:
                        response_body = response.json()
                    except (json.JSONDecodeError, ValueError):
                        response_body = None

                    if (
                        retry_count < DEFAULT_MAX_RETRIES
                        and _should_retry_status(method, response.status_code)
                    ):
                        retry_count += 1
                        time.sleep(_get_retry_delay(retry_count))
                        continue

                    message, error_code = _extract_error_details(
                        response.status_code, response_body, response.text
                    )
                    raise ApiError(
                        message=message,
                        status_code=response.status_code,
                        error_code=error_code,
                    )

                try:
                    return response.json()
                except (json.JSONDecodeError, ValueError) as error:
                    raise ApiError(
                        f"Invalid JSON response from API: {error}",
                        status_code=response.status_code,
                    )
            except requests.exceptions.RequestException as error:
                if (
                    retry_count < DEFAULT_MAX_RETRIES
                    and _should_retry_requests_exception(method, error)
                ):
                    retry_count += 1
                    time.sleep(_get_retry_delay(retry_count))
                    continue
                raise ApiError(f"Request failed: {error}")

    def create_edit(self, request: CreateEditRequest) -> CreateEditResponse:
        """Create a new edit job."""
        response_data = self._make_request(
            method="POST",
            endpoint="/edits",
            data=request.model_dump(by_alias=True, exclude_none=True),
        )
        return CreateEditResponse(**response_data)

    def retrieve_edit(self, edit_id: str) -> RetrieveEditResponse:
        """Get the status and results of an edit job."""
        response_data = self._make_request(method="GET", endpoint=f"/edits/{edit_id}")
        return RetrieveEditResponse(**response_data)

    def get_signed_upload_url(self, filename: str) -> str:
        """Get a signed URL for file upload."""
        response_data = self._make_request(
            method="POST",
            endpoint=f"/upload?filename={filename}",
        )
        return response_data["signedUrl"]

    def upload_file(self, file_path: str, signed_url: str) -> None:
        """Upload file content to the signed URL."""
        try:
            with open(file_path, "rb") as file_handle:
                response = requests.put(signed_url, data=file_handle, timeout=300)
                response.raise_for_status()
        except requests.exceptions.RequestException as error:
            raise ApiError(f"File upload failed: {error}")
        except IOError as error:
            raise ApiError(f"Failed to read file: {error}")

    def check_auth(self) -> AccountInfo:
        """Check if authentication is working."""
        return self._make_request(
            method="GET",
            endpoint="/account",
            base_url=_resolve_v1_base_url(self.config),
        )

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self.session.close()


class AsyncApiClient:
    """Asynchronous HTTP client for the Cleanvoice API."""

    def __init__(self, config: CleanvoiceConfig):
        self.config = config
        self.session = httpx.AsyncClient(
            headers={
                "X-API-Key": config.api_key,
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            }
        )

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make an asynchronous HTTP request to the API."""
        url = f"{(base_url or _resolve_v2_base_url(self.config)).rstrip('/')}/{endpoint.lstrip('/')}"
        retry_count = 0

        while True:
            try:
                response = await self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    timeout=timeout or self.config.timeout,
                )

                if response.status_code >= 400:
                    try:
                        response_body = response.json()
                    except (json.JSONDecodeError, ValueError):
                        response_body = None

                    if (
                        retry_count < DEFAULT_MAX_RETRIES
                        and _should_retry_status(method, response.status_code)
                    ):
                        retry_count += 1
                        await asyncio.sleep(_get_retry_delay(retry_count))
                        continue

                    message, error_code = _extract_error_details(
                        response.status_code, response_body, response.text
                    )
                    raise ApiError(
                        message=message,
                        status_code=response.status_code,
                        error_code=error_code,
                    )

                try:
                    return response.json()
                except (json.JSONDecodeError, ValueError) as error:
                    raise ApiError(
                        f"Invalid JSON response from API: {error}",
                        status_code=response.status_code,
                    )
            except httpx.RequestError as error:
                if retry_count < DEFAULT_MAX_RETRIES and _should_retry_httpx_exception(
                    method, error
                ):
                    retry_count += 1
                    await asyncio.sleep(_get_retry_delay(retry_count))
                    continue
                raise ApiError(f"Request failed: {error}")

    async def create_edit(self, request: CreateEditRequest) -> CreateEditResponse:
        """Create a new edit job."""
        response_data = await self._make_request(
            method="POST",
            endpoint="/edits",
            data=request.model_dump(by_alias=True, exclude_none=True),
        )
        return CreateEditResponse(**response_data)

    async def retrieve_edit(self, edit_id: str) -> RetrieveEditResponse:
        """Get the status and results of an edit job."""
        response_data = await self._make_request(
            method="GET", endpoint=f"/edits/{edit_id}"
        )
        return RetrieveEditResponse(**response_data)

    async def get_signed_upload_url(self, filename: str) -> str:
        """Get a signed URL for file upload."""
        response_data = await self._make_request(
            method="POST",
            endpoint=f"/upload?filename={filename}",
        )
        return response_data["signedUrl"]

    async def upload_file(self, file_path: str, signed_url: str) -> None:
        """Upload file content to the signed URL."""
        try:
            file_size = os.path.getsize(file_path)
            response = await self.session.put(
                signed_url,
                content=_iter_file_chunks(file_path),
                headers={"Content-Length": str(file_size)},
                timeout=300,
            )
            response.raise_for_status()
        except httpx.RequestError as error:
            raise ApiError(f"File upload failed: {error}")
        except IOError as error:
            raise ApiError(f"Failed to read file: {error}")

    async def check_auth(self) -> AccountInfo:
        """Check if authentication is working."""
        return await self._make_request(
            method="GET",
            endpoint="/account",
            base_url=_resolve_v1_base_url(self.config),
        )

    async def aclose(self) -> None:
        """Close the underlying async HTTP session."""
        await self.session.aclose()
