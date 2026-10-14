"""Guarantee that the normal pytest suite never reaches a real network socket."""

from typing import Any

import httpx
import pytest


@pytest.fixture(autouse=True)
def block_real_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow only clients with an explicitly injected mock transport in tests."""
    original_client = httpx.AsyncClient

    def guarded_async_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        if kwargs.get("transport") is None:
            raise AssertionError("network access is forbidden in deterministic pytest")
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", guarded_async_client)
