"""Freshwater Explorer screening-only enrichment adapters."""

from __future__ import annotations

from urllib.parse import urlencode

from watershed_evidence_mcp.http import JsonHttpClient
from watershed_evidence_mcp.models import BoundingBox

PREDICTED_CONDUCTIVITY_URL = (
    "https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/"
    "PredECHydroline/FeatureServer/0/query"
)


class FreshwaterAdapter:
    """Access documented EPA Explorer layers without treating them as raw observations."""

    def __init__(self, client: JsonHttpClient | None = None) -> None:
        self.client = client or JsonHttpClient()

    async def predicted_conductivity(
        self, bounding_box: BoundingBox, max_records: int = 100
    ) -> tuple[list[dict], str]:
        if not 1 <= max_records <= 1_000:
            raise ValueError("max_records must be between 1 and 1000")
        params = {
            "f": "json",
            "where": "1=1",
            "geometry": bounding_box.wqp_value(),
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "COMID,StreamName,AvgPredEC,F50Pct_PL,FTYPE,FCODE",
            "returnGeometry": "false",
            "resultRecordCount": str(max_records),
        }
        payload = await self.client.get_json(PREDICTED_CONDUCTIVITY_URL, params)
        records = [feature.get("attributes", {}) for feature in payload.get("features", [])]
        return records, f"{PREDICTED_CONDUCTIVITY_URL}?{urlencode(params)}"
