"""Read-only adapter for Water Quality Portal public web services."""

from __future__ import annotations

import csv
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from urllib.parse import urlencode

from watershed_evidence_mcp.cache import DuckDbCache
from watershed_evidence_mcp.http import JsonHttpClient, UpstreamServiceError
from watershed_evidence_mcp.models import QueryScope, WqpQuery

WQP_BASE_URL = "https://www.waterqualitydata.us/data"
WQP_SOURCE = "Water Quality Portal"
WQX2_VERSION = "WQX 2 public web services"
REQUIRED_RESULT_COLUMNS = {"MonitoringLocationIdentifier", "CharacteristicName"}
CACHE_PATH = (
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    / "watershed-evidence-mcp"
    / "wqp.duckdb"
)


@dataclass(frozen=True)
class MeasurementResult:
    records: list[dict[str, str | None]]
    query_url: str
    source_version: str
    retrieved_at: datetime
    cache_hit: bool
    truncated: bool
    continuation: str | None


class WqpAdapter:
    """Build bounded WQP requests and retain transparent provenance metadata."""

    def __init__(
        self, client: JsonHttpClient | None = None, cache: DuckDbCache | None = None
    ) -> None:
        self.client = client or JsonHttpClient()
        self._cache = cache

    @property
    def cache(self) -> DuckDbCache:
        """Create persistent state only for a measurement retrieval."""
        if self._cache is None:
            self._cache = DuckDbCache(CACHE_PATH)
        return self._cache

    @staticmethod
    def _scope_parameters(scope: QueryScope) -> dict[str, str]:
        if scope.station_ids is not None:
            return {"siteid": ";".join(scope.station_ids)}
        if scope.bounding_box is not None:
            return {"bBox": scope.bounding_box.wqp_value()}
        if scope.point_radius is not None:
            return {
                "lat": str(scope.point_radius.latitude),
                "long": str(scope.point_radius.longitude),
                "within": str(scope.point_radius.within_miles),
            }
        if scope.huc8 is not None:
            return {"huc": scope.huc8}
        raise ValueError("validated QueryScope had no selector")

    @classmethod
    def result_parameters(cls, query: WqpQuery) -> dict[str, str]:
        parameters = cls._scope_parameters(query.scope)
        parameters.update(
            {
                "characteristicName": ";".join(query.characteristic_names),
                "startDateLo": query.start_date.strftime("%m-%d-%Y"),
                "startDateHi": query.end_date.strftime("%m-%d-%Y"),
                "sampleMedia": query.sample_media,
                "mimeType": "csv",
                "zip": "no",
                "sorted": "no",
                "resultLimit": str(query.result_limit),
            }
        )
        return parameters

    @classmethod
    def site_parameters(cls, scope: QueryScope) -> dict[str, str]:
        parameters = cls._scope_parameters(scope)
        parameters.update({"mimeType": "geojson", "zip": "no"})
        return parameters

    @classmethod
    def summary_parameters(cls, scope: QueryScope) -> dict[str, str]:
        parameters = cls._scope_parameters(scope)
        parameters.update({"mimeType": "geojson", "dataProfile": "summaryMonitoringLocation"})
        return parameters

    @staticmethod
    def url(path: str, params: Mapping[str, str]) -> str:
        return f"{WQP_BASE_URL}/{path}?{urlencode(params)}"

    @staticmethod
    def _version_for(query: WqpQuery) -> str:
        if query.compatibility_mode == "wqx2":
            return WQX2_VERSION
        raise UpstreamServiceError(
            "WQX 3 compatibility mode is not enabled: its result schema has not been validated "
            "against this provenance-preserving adapter. Use compatibility_mode='wqx2'."
        )

    async def available_data(self, scope: QueryScope) -> tuple[dict, str]:
        params = self.summary_parameters(scope)
        url = f"{WQP_BASE_URL}/summary/monitoringLocation/search"
        query_url = self.url("summary/monitoringLocation/search", params)
        return await self.client.get_json(url, params), query_url

    async def monitoring_sites(self, scope: QueryScope) -> tuple[dict, str]:
        params = self.site_parameters(scope)
        url = f"{WQP_BASE_URL}/Station/search"
        return await self.client.get_json(url, params), self.url("Station/search", params)

    async def measurements(self, query: WqpQuery) -> MeasurementResult:
        source_version = self._version_for(query)
        params = self.result_parameters(query)
        endpoint = "Result/search"
        query_url = self.url(endpoint, params)
        cache_key = self.cache.key_for(
            source=WQP_SOURCE,
            source_version=source_version,
            endpoint=endpoint,
            parameters=params,
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return self._measurement_result(
                cached.payload, query_url, source_version, cached.retrieved_at, cache_hit=True
            )

        url = f"{WQP_BASE_URL}/{endpoint}"
        text = await self.client.get_text(
            url,
            params,
            expected_content_types=("text/csv", "application/csv", "text/plain"),
        )
        reader = csv.DictReader(StringIO(text))
        if reader.fieldnames is None or not REQUIRED_RESULT_COLUMNS.issubset(reader.fieldnames):
            raise UpstreamServiceError(
                "WQP returned CSV without required identifier/characteristic columns; retry later"
            )
        rows = list(reader)
        if any(
            not row.get("MonitoringLocationIdentifier") or not row.get("CharacteristicName")
            for row in rows
        ):
            raise UpstreamServiceError(
                "WQP returned a CSV row without a monitoring-location identifier or "
                "characteristic; retry later"
            )
        normalized = [normalize_result_row(row) for row in rows[: query.result_limit]]
        payload = {
            "records": normalized,
            "truncated": len(rows) >= query.result_limit,
        }
        entry = self.cache.set(cache_key, payload)
        return self._measurement_result(
            payload, query_url, source_version, entry.retrieved_at, cache_hit=False
        )

    @staticmethod
    def _measurement_result(
        payload: dict,
        query_url: str,
        source_version: str,
        retrieved_at: datetime,
        *,
        cache_hit: bool,
    ) -> MeasurementResult:
        truncated = bool(payload["truncated"])
        continuation = None
        if truncated:
            continuation = (
                "This response reached the requested result_limit and may be incomplete. WQX 2 "
                "does not provide a stable result cursor here; narrow the date range, station IDs, "
                "or characteristic selection before requesting the next bounded slice."
            )
        return MeasurementResult(
            records=payload["records"],
            query_url=query_url,
            source_version=source_version,
            retrieved_at=retrieved_at,
            cache_hit=cache_hit,
            truncated=truncated,
            continuation=continuation,
        )


def normalize_result_row(row: Mapping[str, str]) -> dict[str, str | None]:
    """Keep WQP’s evidence-bearing fields; do not infer or harmonize units."""

    def value(*names: str) -> str | None:
        return next((row.get(name) for name in names if row.get(name) not in (None, "")), None)

    return {
        "organization_id": value("OrganizationIdentifier"),
        "station_id": value("MonitoringLocationIdentifier"),
        "activity_date": value("ActivityStartDate"),
        "activity_time": value("ActivityStartTime/Time", "ActivityStartTime"),
        "characteristic_name": value("CharacteristicName"),
        "value": value("ResultMeasureValue", "ResultValue"),
        "unit": value("ResultMeasure/MeasureUnitCode", "ResultMeasure.MeasureUnitCode"),
        "value_type": value("ResultValueTypeName"),
        "qualifier": value("MeasureQualifierCode", "ResultQualifier"),
        "detection_condition": value("ResultDetectionConditionText"),
        "detection_limit_value": value("DetectionQuantitationLimitMeasure/MeasureValue"),
        "detection_limit_unit": value("DetectionQuantitationLimitMeasure/MeasureUnitCode"),
        "method_identifier": value(
            "ResultAnalyticalMethod/MethodIdentifier", "AnalyticalMethod/MethodIdentifier"
        ),
        "laboratory_name": value("LaboratoryName"),
    }
