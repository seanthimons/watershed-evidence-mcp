"""Tool: resolve a drawn two-corner box to intersecting HUC8/HUC12 watersheds."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from watershed_evidence_mcp.adapters.wbd import MAX_WATERSHEDS, WBD_LAYERS, WbdAdapter
from watershed_evidence_mcp.models import (
    BoundingBox,
    GeoPoint,
    HucLevel,
    Provenance,
    WatershedResolution,
)
from watershed_evidence_mcp.provenance import WBD_CAVEAT

MAX_SIDE_DEGREES = 0.5  # ~2,500 km2 near mid-latitudes: tens of HUC12s, a few HUC8s

RESOLVE_WATERSHED_DESCRIPTION = (
    "Given two opposite corners of a box (latitude/longitude, any order), return the HUC8 or "
    "HUC12 watersheds that intersect it. A box may straddle several; ask the user to pick one. "
    "Use the huc8 as the wqp_* huc8 scope or the huc12 for get_assessment_context. "
    "Each box side must be at most 0.5 degrees."
)


async def resolve_watershed(
    corner_1: GeoPoint, corner_2: GeoPoint, level: HucLevel = "huc12"
) -> dict:
    """Find USGS WBD watersheds intersecting the box spanned by two corners."""
    box = BoundingBox.from_corners(corner_1, corner_2)
    width, height = round(box.east - box.west, 9), round(box.north - box.south, 9)
    if max(width, height) > MAX_SIDE_DEGREES:
        raise ValueError(
            f"box sides must be at most {MAX_SIDE_DEGREES} degrees; draw a smaller box"
        )

    candidates, skipped, truncated, query_url = await WbdAdapter().resolve_box(box, level)
    warning = None
    if not candidates and not skipped:
        warning = "No watershed intersects this box (outside WBD coverage, e.g. open ocean)."
    elif truncated:
        warning = (
            f"More than {MAX_WATERSHEDS} watersheds intersect; showing the first {MAX_WATERSHEDS} "
            "by code. Draw a smaller box or use level=huc8."
        )
    elif len(candidates) > 1:
        warning = "The box straddles more than one watershed; ask the user to select one."
    if skipped:
        note = f"{skipped} malformed WBD record(s) were skipped; the list may be incomplete."
        warning = f"{warning} {note}" if warning else note
    return WatershedResolution(
        query_box=box,
        level=level,
        candidates=candidates,
        skipped_records=skipped,
        truncated=truncated,
        warning=warning,
        provenance=Provenance(
            source="USGS Watershed Boundary Dataset",
            source_version=f"ArcGIS MapServer layer {WBD_LAYERS[level]}",
            query_url=query_url,
            caveat=WBD_CAVEAT,
        ),
    ).model_dump(mode="json")


def register(mcp: FastMCP) -> None:
    mcp.tool(description=RESOLVE_WATERSHED_DESCRIPTION)(resolve_watershed)
