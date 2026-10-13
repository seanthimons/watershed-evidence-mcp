"""Read-only adapter for Water Quality Portal public web services."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from io import StringIO
from urllib.parse import urlencode

from watershed_evidence_mcp.http import JsonHttpClient
from watershed_evidence_mcp.models import QueryScope, WqpQuery

WQP_BASE_URL = "https://www.waterqualitydata.us/data"


class WqpAdapter:
    """Build bounded WQP requests and retain a transparent query URL."""

    def __init__(self, client: JsonHttpClient | None = None) -> None:
        self.client = client or JsonHttpClient()

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

    async def available_data(self, scope: QueryScope) -> tuple[dict, str]:
        params = self.summary_parameters(scope)
        url = f"{WQP_BASE_URL}/summary/monitoringLocation/search"
        query_url = self.url("summary/monitoringLocation/search", params)
        return await self.client.get_json(url, params), query_url

    async def monitoring_sites(self, scope: QueryScope) -> tuple[dict, str]:
        params = self.site_parameters(scope)
        url = f"{WQP_BASE_URL}/Station/search"
        return await self.client.get_json(url, params), self.url("Station/search", params)

    async def measurements(self, query: WqpQuery) -> tuple[list[dict[str, str | None]], str]:
        params = self.result_parameters(query)
        url = f"{WQP_BASE_URL}/Result/search"
        text = await self.client.get_text(url, params)
        rows = list(csv.DictReader(StringIO(text)))
        if len(rows) > query.result_limit:
            rows = rows[: query.result_limit]
        return [normalize_result_row(row) for row in rows], self.url("Result/search", params)


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
        "qualifier": value("ResultDetectionConditionText", "ResultQualifier"),
        "detection_limit_value": value("DetectionQuantitationLimitMeasure/MeasureValue"),
        "detection_limit_unit": value("DetectionQuantitationLimitMeasure/MeasureUnitCode"),
        "method_identifier": value("AnalyticalMethod/MethodIdentifier"),
        "laboratory_name": value("LaboratoryName"),
    }
