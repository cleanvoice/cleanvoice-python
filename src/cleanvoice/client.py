"""API client for Cleanvoice SDK."""

import json
from typing import Any, Dict, Optional

import requests

from .types import (
    ApiError,
    CleanvoiceConfig,
    CreateEditRequest,
    CreateEditResponse,
    RetrieveEditResponse,
)


class ApiClient:
    """HTTP client for Cleanvoice API."""

    def __init__(self, config: CleanvoiceConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-API-Key": f"{config.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "cleanvoice-python-sdk/1.0.0",
            }
        )

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to the API."""
        base_url = self.config.base_url or "https://api.cleanvoice.ai/v2"
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                timeout=timeout or self.config.timeout,
            )

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    message = error_data.get("message", f"HTTP {response.status_code}")
                    error_code = error_data.get("code")
                except (json.JSONDecodeError, ValueError):
                    message = f"HTTP {response.status_code}: {response.text}"
                    error_code = None

                raise ApiError(
                    message=message,
                    status_code=response.status_code,
                    error_code=error_code,
                )

            return response.json()

        except requests.exceptions.RequestException as e:
            raise ApiError(f"Request failed: {str(e)}")

    def create_edit(self, request: CreateEditRequest) -> CreateEditResponse:
        """Create a new edit job."""
        response_data = self._make_request(
            method="POST",
            endpoint="/edits",
            data=request.model_dump(exclude_none=True),
        )
        return CreateEditResponse(**response_data)

    def retrieve_edit(self, edit_id: str) -> RetrieveEditResponse:
        """Get the status and results of an edit job."""
        response_data = self._make_request(
            method="GET",
            endpoint=f"/edits/{edit_id}",
        )
        return RetrieveEditResponse(**response_data)

    def check_auth(self) -> Dict[str, Any]:
        """Check if authentication is working."""
        # Use v1 API for account verification
        base_url = self.config.base_url or "https://api.cleanvoice.ai/v1"
        if self.config.base_url is None:
            base_url = "https://api.cleanvoice.ai/v1"
        else:
            # Replace v2 with v1 if present in custom base_url
            base_url = self.config.base_url.replace("/v2", "/v1")
        
        url = f"{base_url.rstrip('/')}/account"
        
        try:
            response = self.session.request(
                method="GET",
                url=url,
                timeout=self.config.timeout,
            )

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    message = error_data.get("message", f"HTTP {response.status_code}")
                    error_code = error_data.get("code")
                except (json.JSONDecodeError, ValueError):
                    message = f"HTTP {response.status_code}: {response.text}"
                    error_code = None

                raise ApiError(
                    message=message,
                    status_code=response.status_code,
                    error_code=error_code,
                )

            return response.json()

        except requests.exceptions.RequestException as e:
            raise ApiError(f"Request failed: {str(e)}")
