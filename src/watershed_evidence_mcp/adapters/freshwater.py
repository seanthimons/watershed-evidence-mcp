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
    ) -> tuple[list[dict], str, bool]:
        """Return GeoJSON Features (EPSG:4326), the query URL, and the truncation state."""
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
            "returnGeometry": "true",
            "outSR": "4326",
            # One extra row distinguishes "exactly at cap" from "truncated".
            "resultRecordCount": str(max_records + 1),
        }
        payload = await self.client.get_json(PREDICTED_CONDUCTIVITY_URL, params)
        records = [_to_geojson_feature(f) for f in payload.get("features", [])]
        truncated = len(records) > max_records or bool(payload.get("exceededTransferLimit"))
        return records[:max_records], f"{PREDICTED_CONDUCTIVITY_URL}?{urlencode(params)}", truncated


def _to_geojson_feature(feature: dict) -> dict:
    """Convert an Esri polyline feature to GeoJSON; geometry is None when absent or empty."""
    attributes = feature.get("attributes", {})
    paths = [p for p in (feature.get("geometry") or {}).get("paths", []) if len(p) >= 2]
    geometry = None
    if len(paths) == 1:
        geometry = {"type": "LineString", "coordinates": paths[0]}
    elif paths:
        geometry = {"type": "MultiLineString", "coordinates": paths}
    return {
        "type": "Feature",
        "id": attributes.get("COMID"),
        "geometry": geometry,
        "properties": attributes,
    }
