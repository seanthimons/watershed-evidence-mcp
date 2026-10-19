"""Tool: EPA Freshwater Explorer screening baseline."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from watershed_evidence_mcp.adapters.freshwater import FreshwaterAdapter
from watershed_evidence_mcp.models import BoundingBox
from watershed_evidence_mcp.provenance import FRESHWATER_CAVEAT
from watershed_evidence_mcp.provenance import provenance as _provenance

FRESHWATER_SCREENING_BASELINE_DESCRIPTION = (
    "Retrieve EPA Freshwater Explorer predicted-background conductivity for a bounded area, "
    "with stream-reach geometry as a GeoJSON FeatureCollection (EPSG:4326) keyed by COMID. "
    "This is a screening baseline, not a raw observation set or regulatory determination."
)


async def freshwater_screening_baseline(bounding_box: BoundingBox, max_records: int = 100) -> dict:
    """Retrieve the Explorer's predicted-background conductivity layer for a bounded area."""
    features, query_url, truncated = await FreshwaterAdapter().predicted_conductivity(
        bounding_box, max_records
    )
    return {
        "evidence_type": "screening_baseline",
        "parameter": "predicted background conductivity",
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
            "U.S. EPA Freshwater Explorer 2.0",
            "Predicted Background Conductivity ArcGIS FeatureServer layer 0",
            query_url,
            FRESHWATER_CAVEAT,
        ),
    }


def register(mcp: FastMCP) -> None:
    mcp.tool(description=FRESHWATER_SCREENING_BASELINE_DESCRIPTION)(freshwater_screening_baseline)
