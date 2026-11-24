"""Tool: EPA Freshwater Explorer screening baseline."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from watershed_evidence_mcp.adapters.freshwater import LAYERS, FreshwaterAdapter, FreshwaterLayer
from watershed_evidence_mcp.models import BoundingBox
from watershed_evidence_mcp.provenance import provenance as _provenance

FRESHWATER_SCREENING_BASELINE_DESCRIPTION = (
    "Retrieve one EPA Freshwater Explorer screening layer for a bounded area as a GeoJSON "
    "FeatureCollection (EPSG:4326). layer='predicted_conductivity' (default): modelled "
    "background conductivity on stream reaches keyed by COMID. Station layers keyed by WQP "
    "station ID: 'station_water_chemistry_10th_percentile' (pH, DOC, hardness), "
    "'station_aluminum_criteria' and 'station_cadmium_criteria' (calculated acute/chronic "
    "criteria values). This is screening context, not raw observations, adopted standards, "
    "exceedances, or a regulatory determination."
)


async def freshwater_screening_baseline(
    bounding_box: BoundingBox,
    max_records: int = 100,
    layer: FreshwaterLayer = "predicted_conductivity",
) -> dict:
    """Retrieve one Freshwater Explorer screening layer for a bounded area."""
    spec = LAYERS[layer]
    features, query_url, truncated = await FreshwaterAdapter().layer_features(
        layer, bounding_box, max_records
    )
    return {
        "evidence_type": "screening_baseline",
        "layer": layer,
        "parameter": spec.parameter,
        "returned_records": len(features),
        "requested_max_records": max_records,
        "truncated": truncated,
        "bounding_box": bounding_box.model_dump(mode="json"),
        "crs": "EPSG:4326",
        "records_without_geometry": sum(f["geometry"] is None for f in features),
        "records": [f["properties"] for f in features],
        "feature_collection": {"type": "FeatureCollection", "features": features},
        "screening_only": True,
        "provenance": _provenance(
            "U.S. EPA Freshwater Explorer 2.0", spec.source_version, query_url, spec.caveat
        ),
    }


def register(mcp: FastMCP) -> None:
    mcp.tool(description=FRESHWATER_SCREENING_BASELINE_DESCRIPTION)(freshwater_screening_baseline)
