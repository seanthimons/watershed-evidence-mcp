"""Small, injectable HTTP boundary for public APIs."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import httpx

DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_RESPONSE_BYTES = 10_000_000


class UpstreamServiceError(RuntimeError):
    """A public upstream service failed or returned unusable data."""


@dataclass(frozen=True)
class HttpResponse:
    content: bytes
    content_type: str


class JsonHttpClient:
    def __init__(
        self,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_response_bytes < 1:
            raise ValueError("max_response_bytes must be at least 1")
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.transport = transport

    async def _get(
        self, url: str, params: Mapping[str, str] | None, expected_content_types: Sequence[str]
    ) -> HttpResponse:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, follow_redirects=True, transport=self.transport
            ) as client:
                async with client.stream("GET", url, params=params) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                    if not any(
                        content_type == expected.lower() for expected in expected_content_types
                    ):
                        expected = ", ".join(expected_content_types)
                        raise UpstreamServiceError(
                            f"upstream response content type {content_type or 'missing'} "
                            f"was not one of: {expected}"
                        )
                    content_length = response.headers.get("content-length")
                    if content_length is not None and int(content_length) > self.max_response_bytes:
                        raise UpstreamServiceError(
                            "upstream response exceeded the "
                            f"{self.max_response_bytes:,}-byte safety limit; narrow the query"
                        )
                    chunks: list[bytes] = []
                    total_bytes = 0
                    async for chunk in response.aiter_bytes():
                        total_bytes += len(chunk)
                        if total_bytes > self.max_response_bytes:
                            raise UpstreamServiceError(
                                "upstream response exceeded the "
                                f"{self.max_response_bytes:,}-byte safety limit; narrow the query"
                            )
                        chunks.append(chunk)
        except httpx.TimeoutException as exc:
            raise UpstreamServiceError(
                f"upstream request timed out after {self.timeout_seconds:g} seconds; "
                "narrow the query and retry"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise UpstreamServiceError(
                f"upstream service returned HTTP {exc.response.status_code}; "
                "retry later or narrow the query"
            ) from exc
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(f"upstream request failed: {exc}") from exc
        return HttpResponse(content=b"".join(chunks), content_type=content_type)

    async def get_json(self, url: str, params: Mapping[str, str] | None = None) -> dict:
        response = await self._get(
            url, params, ("application/json", "application/geo+json", "application/vnd.geo+json")
        )
        try:
            payload = json.loads(response.content)
        except (UnicodeDecodeError, ValueError) as exc:
            raise UpstreamServiceError("upstream response was not valid JSON") from exc
        if not isinstance(payload, dict):
            raise UpstreamServiceError("upstream response was not a JSON object")
        if "error" in payload:
            error = payload["error"]
            message = (
                error.get("message", "unknown upstream error") if isinstance(error, dict) else error
            )
            raise UpstreamServiceError(f"upstream service error: {message}")
        return payload

    async def get_text(
        self,
        url: str,
        params: Mapping[str, str] | None = None,
        *,
        expected_content_types: Sequence[str] = ("text/plain",),
    ) -> str:
        response = await self._get(url, params, expected_content_types)
        try:
            return response.content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UpstreamServiceError("upstream response was not UTF-8 text") from exc
