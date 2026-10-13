"""Small, injectable HTTP boundary for public APIs."""

from __future__ import annotations

from collections.abc import Mapping

import httpx


class UpstreamServiceError(RuntimeError):
    """A public upstream service failed or returned unusable data."""


class JsonHttpClient:
    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

    async def get_json(self, url: str, params: Mapping[str, str] | None = None) -> dict:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, follow_redirects=True
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamServiceError(f"upstream request failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise UpstreamServiceError("upstream response was not a JSON object")
        if "error" in payload:
            error = payload["error"]
            message = (
                error.get("message", "unknown upstream error") if isinstance(error, dict) else error
            )
            raise UpstreamServiceError(f"upstream service error: {message}")
        return payload

    async def get_text(self, url: str, params: Mapping[str, str] | None = None) -> str:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, follow_redirects=True
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.text
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(f"upstream request failed: {exc}") from exc
