"""USGS Watershed Boundary Dataset adapter: bounding box to intersecting HUC8/HUC12 units."""

from __future__ import annotations

from urllib.parse import urlencode

from pydantic import ValidationError

from watershed_evidence_mcp.http import JsonHttpClient
from watershed_evidence_mcp.models import BoundingBox, HucLevel, WatershedCandidate

WBD_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer"
WBD_LAYERS: dict[HucLevel, int] = {"huc8": 4, "huc12": 6}
MAX_WATERSHEDS = 50
HUC_DIGITS: dict[HucLevel, int] = {"huc8": 8, "huc12": 12}


class WbdAdapter:
    def __init__(self, client: JsonHttpClient | None = None) -> None:
        self.client = client or JsonHttpClient()

    async def resolve_box(
        self, box: BoundingBox, level: HucLevel
    ) -> tuple[list[WatershedCandidate], int, bool, str]:
        """Return candidates, the count of malformed records skipped, truncation, query URL."""
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
        candidates: list[WatershedCandidate] = []
        skipped = 0
        for feature in payload.get("features", []):
            attrs = feature.get("attributes") or {}
            huc = attrs.get(level)
            # One malformed upstream record is skipped and counted, not fatal to the call.
            if not isinstance(huc, str) or len(huc) != HUC_DIGITS[level]:
                skipped += 1
                continue
            try:
                candidates.append(
                    WatershedCandidate(
                        huc=huc,
                        name=attrs.get("name"),
                        area_sq_km=attrs.get("areasqkm"),
                        states=attrs.get("states"),
                    )
                )
            except ValidationError:
                skipped += 1
        truncated = bool(payload.get("exceededTransferLimit"))
        return candidates, skipped, truncated, f"{url}?{urlencode(params)}"
