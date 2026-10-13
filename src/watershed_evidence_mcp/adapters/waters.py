"""EPA WATERS GeoViewer adapter used only to resolve river-name candidates."""

from __future__ import annotations

from urllib.parse import urlencode

from watershed_evidence_mcp.http import JsonHttpClient
from watershed_evidence_mcp.models import BoundingBox, WaterbodyCandidate

GEOVIEWER_STREAM_URL = (
    "https://watersgeo.epa.gov/arcgis/rest/services/OWOTHER/"
    "WATERS_GeoViewer_SurfaceWater/MapServer/1/query"
)


def feature_to_candidate(feature: dict) -> WaterbodyCandidate:
    attributes = feature.get("attributes", {})
    geometry = feature.get("geometry", {})
    points = [point for path in geometry.get("paths", []) for point in path]
    bounding_box = None
    if points:
        longitudes = [point[0] for point in points]
        latitudes = [point[1] for point in points]
        bounding_box = BoundingBox(
            west=min(longitudes), south=min(latitudes), east=max(longitudes), north=max(latitudes)
        )
    return WaterbodyCandidate(
        name=(
            attributes.get("GNIS_NAME")
            or attributes.get("gnis_name")
            or attributes.get("GNISName")
            or "Unnamed waterbody"
        ),
        reachcode=str(attributes.get("REACHCODE") or attributes.get("reachcode"))
        if attributes.get("REACHCODE") or attributes.get("reachcode")
        else None,
        nhdplusid=str(attributes.get("NHDPLUSID") or attributes.get("nhdplusid"))
        if attributes.get("NHDPLUSID") or attributes.get("nhdplusid")
        else None,
        geometry_type=geometry.get("type") or ("polyline" if points else None),
        bounding_box=bounding_box,
        state=attributes.get("STATE") or attributes.get("state") or attributes.get("State"),
    )


class WatersAdapter:
    def __init__(self, client: JsonHttpClient | None = None) -> None:
        self.client = client or JsonHttpClient()

    async def resolve_name(
        self, river_name: str, max_candidates: int = 10
    ) -> tuple[list[WaterbodyCandidate], str]:
        escaped_name = river_name.replace("'", "''")
        params = {
            "f": "json",
            "where": f"UPPER(gnis_name) = UPPER('{escaped_name}')",
            "outFields": "gnis_name,reachcode,nhdplusid",
            "returnGeometry": "true",
            "outSR": "4326",
            "resultRecordCount": str(max_candidates),
        }
        payload = await self.client.get_json(GEOVIEWER_STREAM_URL, params)
        candidates = [feature_to_candidate(feature) for feature in payload.get("features", [])]
        return candidates, f"{GEOVIEWER_STREAM_URL}?{urlencode(params)}"
