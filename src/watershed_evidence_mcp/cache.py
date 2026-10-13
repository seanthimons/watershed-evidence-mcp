"""Small deterministic DuckDB cache for bounded public-source responses."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

DEFAULT_CACHE_TTL_SECONDS = 3_600


@dataclass(frozen=True)
class CacheEntry:
    """A valid cached response and its original retrieval timestamp."""

    payload: dict[str, Any]
    retrieved_at: datetime


class DuckDbCache:
    """Persist JSON responses by normalized source/version/query identity.

    Entries expire after the configured TTL. Changing source version changes the
    key, so a service-version change cannot reuse a prior response.
    """

    def __init__(self, path: Path, ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS) -> None:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be at least 1")
        self.path = path
        self.ttl_seconds = ttl_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS wqp_cache (
                    cache_key VARCHAR PRIMARY KEY,
                    payload_json VARCHAR NOT NULL,
                    retrieved_at VARCHAR NOT NULL,
                    expires_at VARCHAR NOT NULL
                )
                """
            )

    def _connection(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.path))

    @staticmethod
    def key_for(
        *, source: str, source_version: str, endpoint: str, parameters: dict[str, str]
    ) -> str:
        identity = {
            "endpoint": endpoint,
            "parameters": dict(sorted(parameters.items())),
            "source": source,
            "source_version": source_version,
        }
        canonical = json.dumps(identity, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> CacheEntry | None:
        now = datetime.now(UTC)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json, retrieved_at, expires_at FROM wqp_cache WHERE cache_key = ?",
                [cache_key],
            ).fetchone()
            if row is None:
                return None
            payload_json, retrieved_at, expires_at = row
            expires = datetime.fromisoformat(expires_at)
            if expires <= now:
                connection.execute("DELETE FROM wqp_cache WHERE cache_key = ?", [cache_key])
                return None
        payload = json.loads(payload_json)
        if not isinstance(payload, dict):
            raise RuntimeError("cached WQP response was not a JSON object")
        return CacheEntry(payload=payload, retrieved_at=datetime.fromisoformat(retrieved_at))

    def set(self, cache_key: str, payload: dict[str, Any]) -> CacheEntry:
        retrieved_at = datetime.now(UTC)
        expires_at = retrieved_at + timedelta(seconds=self.ttl_seconds)
        with self._connection() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO wqp_cache (cache_key, payload_json, retrieved_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                [
                    cache_key,
                    json.dumps(payload, separators=(",", ":"), sort_keys=True),
                    retrieved_at.isoformat(),
                    expires_at.isoformat(),
                ],
            )
        return CacheEntry(payload=payload, retrieved_at=retrieved_at)

    def clear(self) -> None:
        """Explicitly invalidate all entries in this cache database."""
        with self._connection() as connection:
            connection.execute("DELETE FROM wqp_cache")
