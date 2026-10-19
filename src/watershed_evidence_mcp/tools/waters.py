"""Tool: resolve a river name to EPA WATERS candidates."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from watershed_evidence_mcp.adapters.waters import WatersAdapter
from watershed_evidence_mcp.models import Provenance, WaterbodyResolution
from watershed_evidence_mcp.provenance import WATERS_CAVEAT

RESOLVE_WATERBODY_DESCRIPTION = (
    "Resolve an exact river or stream name into EPA surface-water feature candidates. "
    "Returns ambiguity explicitly; select a candidate before querying observations."
)


async def resolve_waterbody(river_name: str, max_candidates: int = 10) -> dict:
    """Find candidate named surface-water features using the EPA WATERS GeoViewer."""
    if not river_name.strip():
        raise ValueError("river_name must not be empty")
    if not 1 <= max_candidates <= 25:
        raise ValueError("max_candidates must be between 1 and 25")

    candidates, query_url = await WatersAdapter().resolve_name(river_name.strip(), max_candidates)
    resolution = WaterbodyResolution(
        query=river_name,
        candidates=candidates,
        ambiguity_warning=(
            "Select a candidate and supply an explicit spatial scope before querying WQP."
            if candidates
            else (
                "No exact GNIS-name candidate was returned; try another name or a spatial selector."
            )
        ),
        provenance=Provenance(
            source="U.S. EPA WATERS GeoViewer Surface Water",
            source_version="ArcGIS MapServer layer 1",
            query_url=query_url,
            caveat=WATERS_CAVEAT,
        ),
    )
    return resolution.model_dump(mode="json")


def register(mcp: FastMCP) -> None:
    mcp.tool(description=RESOLVE_WATERBODY_DESCRIPTION)(resolve_waterbody)
