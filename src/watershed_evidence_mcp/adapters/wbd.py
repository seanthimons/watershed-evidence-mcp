"""USGS Watershed Boundary Dataset adapter: bounding box to intersecting HUC8/HUC12 units."""

from __future__ import annotations

from urllib.parse import urlencode

from watershed_evidence_mcp.http import JsonHttpClient
from watershed_evidence_mcp.models import BoundingBox, HucLevel, WatershedCandidate

WBD_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer"
WBD_LAYERS: dict[HucLevel, int] = {"huc8": 4, "huc12": 6}
MAX_WATERSHEDS = 50


class WbdAdapter:
    def __init__(self, client: JsonHttpClient | None = None) -> None:
        self.client = client or JsonHttpClient()

    async def resolve_box(
        self, box: BoundingBox, level: HucLevel
    ) -> tuple[list[WatershedCandidate], bool, str]:
        url = f"{WBD_URL}/{WBD_LAYERS[level]}/query"
        params = {
            "f": "json",
            "geometry": box.wqp_value(),
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": f"{level},name,areasqkm,states",
            "returnGeometry": "false",
            "orderByFields": level,  # stable order so truncation is deterministic
            "resultRecordCount": str(MAX_WATERSHEDS),
        }
        payload = await self.client.get_json(url, params)
        candidates = [
            WatershedCandidate(
                huc=attrs[level],
                name=attrs.get("name"),
                area_sq_km=attrs.get("areasqkm"),
                states=attrs.get("states"),
            )
            for feature in payload.get("features", [])
            if (attrs := feature.get("attributes", {})).get(level)
        ]
        return candidates, bool(payload.get("exceededTransferLimit")), f"{url}?{urlencode(params)}"
