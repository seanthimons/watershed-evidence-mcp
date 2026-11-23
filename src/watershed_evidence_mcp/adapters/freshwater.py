"""Freshwater Explorer screening-only enrichment adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlencode

from watershed_evidence_mcp.http import JsonHttpClient
from watershed_evidence_mcp.models import BoundingBox
from watershed_evidence_mcp.provenance import FRESHWATER_CAVEAT, FRESHWATER_CRITERIA_CAVEAT

_SERVICES = "https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services"

FreshwaterLayer = Literal[
    "predicted_conductivity",
    "station_water_chemistry_10th_percentile",
    "station_aluminum_criteria",
    "station_cadmium_criteria",
]


@dataclass(frozen=True)
class LayerSpec:
    url: str
    out_fields: str
    id_field: str
    parameter: str
    source_version: str
    caveat: str


def _layer(service: str) -> str:
    return f"{_SERVICES}/{service}/FeatureServer/0/query"


LAYERS: dict[str, LayerSpec] = {
    "predicted_conductivity": LayerSpec(
        _layer("PredECHydroline"),
        "COMID,StreamName,AvgPredEC,F50Pct_PL,FTYPE,FCODE",
        "COMID",
        "predicted background conductivity",
        "Predicted Background Conductivity ArcGIS FeatureServer layer 0",
        FRESHWATER_CAVEAT,
    ),
    # Point layers: Station is a WQP MonitoringLocationIdentifier. "*" because field names
    # differ between layers (e.g. Ecoregion vs Ecoregion_Level_III).
    "station_water_chemistry_10th_percentile": LayerSpec(
        _layer("10th_Percentile_Water_Chemistry_by_Station_Freshwater_Explorer_Data_012925"),
        "*",
        "Station",
        "10th-percentile station water chemistry (pH, DOC, hardness)",
        "10th Percentile Water Chemistry by Station, data release 2025-01-29, layer 0",
        FRESHWATER_CAVEAT,
    ),
    "station_aluminum_criteria": LayerSpec(
        _layer("Aquatic_Life_Criteria_for_Aluminum_by_Station_Freshwater_Explorer_Data_01292025"),
        "*",
        "Station",
        "station-level aquatic life criteria for aluminum (acute/chronic)",
        "Aquatic Life Criteria for Aluminum by Station, data release 2025-01-29, layer 0",
        FRESHWATER_CRITERIA_CAVEAT,
    ),
    "station_cadmium_criteria": LayerSpec(
        _layer("Aquatic_Life_Criteria_for_Cadmium_by_Station_Freshwater_Explorer_Data_012925"),
        "*",
        "Station",
        "station-level aquatic life criteria for cadmium (acute/chronic)",
        "Aquatic Life Criteria for Cadmium by Station, data release 2025-01-29, layer 0",
        FRESHWATER_CRITERIA_CAVEAT,
    ),
}


class FreshwaterAdapter:
    """Access documented EPA Explorer layers without treating them as raw observations."""

    def __init__(self, client: JsonHttpClient | None = None) -> None:
        self.client = client or JsonHttpClient()

    async def layer_features(
        self, layer: FreshwaterLayer, bounding_box: BoundingBox, max_records: int = 100
    ) -> tuple[list[dict], str, bool]:
        """Return GeoJSON Features (EPSG:4326), the query URL, and the truncation state."""
        if not 1 <= max_records <= 1_000:
            raise ValueError("max_records must be between 1 and 1000")
        spec = LAYERS[layer]
        params = {
            "f": "json",
            "where": "1=1",
            "geometry": bounding_box.wqp_value(),
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": spec.out_fields,
            "returnGeometry": "true",
            "outSR": "4326",
            # One extra row distinguishes "exactly at cap" from "truncated".
            "resultRecordCount": str(max_records + 1),
        }
        payload = await self.client.get_json(spec.url, params)
        records = [_to_geojson_feature(f, spec.id_field) for f in payload.get("features", [])]
        truncated = len(records) > max_records or bool(payload.get("exceededTransferLimit"))
        return records[:max_records], f"{spec.url}?{urlencode(params)}", truncated

    async def predicted_conductivity(
        self, bounding_box: BoundingBox, max_records: int = 100
    ) -> tuple[list[dict], str, bool]:
        return await self.layer_features("predicted_conductivity", bounding_box, max_records)


def _to_geojson_feature(feature: dict, id_field: str = "COMID") -> dict:
    """Convert an Esri polyline or point feature to GeoJSON; geometry is None when absent."""
    attributes = feature.get("attributes", {})
    esri = feature.get("geometry") or {}
    paths = [p for p in esri.get("paths", []) if len(p) >= 2]
    geometry = None
    if esri.get("x") is not None and esri.get("y") is not None:
        geometry = {"type": "Point", "coordinates": [esri["x"], esri["y"]]}
    elif len(paths) == 1:
        geometry = {"type": "LineString", "coordinates": paths[0]}
    elif paths:
        geometry = {"type": "MultiLineString", "coordinates": paths}
    return {
        "type": "Feature",
        "id": attributes.get(id_field),
        "geometry": geometry,
        "properties": attributes,
    }
