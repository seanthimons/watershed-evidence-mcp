"""MCP tool definitions for provenance-first public water-quality retrieval."""

from __future__ import annotations

from urllib.parse import urlencode

from mcp.server.fastmcp import FastMCP

from watershed_evidence_mcp.adapters.attains import AttainsAdapter
from watershed_evidence_mcp.adapters.freshwater import FreshwaterAdapter
from watershed_evidence_mcp.adapters.waters import WatersAdapter
from watershed_evidence_mcp.adapters.wqp import WqpAdapter
from watershed_evidence_mcp.http import JsonHttpClient
from watershed_evidence_mcp.models import (
    AssessmentContextQuery,
    BoundingBox,
    Provenance,
    QueryScope,
    WaterbodyResolution,
    WqpQuery,
)

mcp = FastMCP(
    name="Watershed Evidence",
    instructions=(
        "Use this read-only server to retrieve public U.S. water-quality evidence. "
        "Resolve a named river before creating a geographic query. Use wqp_available_data "
        "before wqp_measurements. Never present Freshwater Explorer screening context or "
        "WQP observations as a regulatory determination."
    ),
)

WQP_CAVEAT = (
    "WQP aggregates public records from many contributors. Preserve source identifiers, units, "
    "qualifiers, and method information; do not treat this retrieval as a regulatory determination."
)
WATERS_CAVEAT = (
    "A river name can match more than one feature. Candidates are not a complete river corridor; "
    "the caller must select a candidate and define an explicit query area."
)
ATTAINS_CAVEAT = (
    "ATTAINS reports assessment decisions for a reporting cycle. It does not establish the "
    "current condition of a waterbody or prove the cause of an observed condition."
)


def _provenance(source: str, version: str, query_url: str, caveat: str) -> dict:
    return Provenance(
        source=source,
        source_version=version,
        query_url=query_url,
        caveat=caveat,
    ).model_dump(mode="json")


@mcp.tool(
    description=(
        "Resolve an exact river or stream name into EPA surface-water feature candidates. "
        "Returns ambiguity explicitly; select a candidate before querying observations."
    )
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


@mcp.tool(
    description=(
        "Preflight a bounded WQP geographic/station query. Returns station geometry and counts of "
        "reported activities/results before any raw measurement retrieval."
    )
)
async def wqp_available_data(scope: QueryScope) -> dict:
    """Retrieve WQP monitoring-location availability summary for one bounded scope."""
    payload, query_url = await WqpAdapter().available_data(scope)
    features = payload.get("features", [])
    return {
        "evidence_type": "coverage_summary",
        "feature_count": len(features),
        "features": features,
        "provenance": _provenance(
            "Water Quality Portal", "WQX 2 public web services", query_url, WQP_CAVEAT
        ),
    }


@mcp.tool(
    description=(
        "List WQP monitoring stations in one bounded scope. Use it after availability preflight "
        "when the agent needs station identifiers for a focused results query."
    )
)
async def wqp_monitoring_sites(scope: QueryScope) -> dict:
    """Retrieve WQP station inventory as GeoJSON for one bounded scope."""
    payload, query_url = await WqpAdapter().monitoring_sites(scope)
    features = payload.get("features", [])
    return {
        "evidence_type": "station_inventory",
        "feature_count": len(features),
        "features": features,
        "provenance": _provenance(
            "Water Quality Portal", "WQX 2 public web services", query_url, WQP_CAVEAT
        ),
    }


@mcp.tool(
    description=(
        "Retrieve a bounded set of raw WQP water-quality observations. Requires one exact "
        "spatial/station selector, exact WQP characteristic name(s), a date range, and "
        "a result cap. "
        "Preserves "
        "units, qualifiers, detection limits, and method fields without harmonizing them."
    )
)
async def wqp_measurements(query: WqpQuery) -> dict:
    """Retrieve and normalize a capped raw WQP result set."""
    result = await WqpAdapter().measurements(query)
    return {
        "evidence_type": "observation",
        "returned_records": len(result.records),
        "result_limit": query.result_limit,
        "truncated": result.truncated,
        "continuation": result.continuation,
        "cache": {
            "hit": result.cache_hit,
            "retrieved_at": result.retrieved_at.isoformat(),
            "ttl_seconds": 3_600,
            "invalidation": (
                "entries expire after TTL; a source-version change uses a new cache key"
            ),
        },
        "records": result.records,
        "provenance": _provenance(
            "Water Quality Portal", result.source_version, result.query_url, WQP_CAVEAT
        ),
    }


@mcp.tool(
    description=(
        "Retrieve read-only EPA ATTAINS assessment reporting context for one exact "
        "assessment unit or by a disclosed HUC12-to-assessment-unit resolution. Returns reporting-"
        "cycle status, designated uses, parameter context, source identifiers, and provenance. "
        "An assessment is not proof of a present-day condition or causal finding."
    )
)
async def get_assessment_context(query: AssessmentContextQuery) -> dict:
    """Retrieve ATTAINS reporting context without turning it into a causal conclusion."""
    result = await AttainsAdapter().assessment_context(query)
    response = {
        "evidence_type": "assessment_context",
        "returned_records": len(result.records),
        "records": result.records,
        "provenance": _provenance(
            "U.S. EPA ATTAINS",
            "ATTAINS public web services",
            result.assessment_query_url,
            ATTAINS_CAVEAT,
        ),
    }
    if len(result.assessment_query_urls) > 1:
        response["provenance"]["query_urls"] = result.assessment_query_urls
    if result.resolution_query_url is not None:
        response["geographic_resolution"] = {
            "input": {"huc12": query.huc12},
            "query_url": result.resolution_query_url,
            "caveat": "The HUC12 resolution lists associated assessment units; it does not "
            "create a river-corridor or causal inference.",
        }
    return response


@mcp.tool(
    description=(
        "Retrieve EPA Freshwater Explorer predicted-background conductivity for a bounded area. "
        "This is a screening baseline, not a raw observation set or regulatory determination."
    )
)
async def freshwater_screening_baseline(bounding_box: BoundingBox, max_records: int = 100) -> dict:
    """Retrieve the Explorer's predicted-background conductivity layer for a bounded area."""
    records, query_url = await FreshwaterAdapter().predicted_conductivity(bounding_box, max_records)
    return {
        "evidence_type": "screening_baseline",
        "parameter": "predicted background conductivity",
        "returned_records": len(records),
        "records": records,
        "screening_only": True,
        "provenance": _provenance(
            "U.S. EPA Freshwater Explorer 2.0",
            "Predicted Background Conductivity ArcGIS FeatureServer layer 0",
            query_url,
            (
                "Explorer layers are curated/modelled screening context and may need local "
                "calibration. Do not represent them as current raw observations or a "
                "regulatory finding."
            ),
        ),
    }


@mcp.tool(
    description=(
        "Search an official WQP controlled vocabulary, such as CharacteristicName, Organization, "
        "Characteristictype, or Sitetype. Use this to translate user wording into exact WQP values."
    )
)
async def wqp_vocab_search(
    vocabulary: str, text: str, page_size: int = 20, page_number: int = 1
) -> dict:
    """Discover exact, permissible WQP query values without silent fuzzy matching."""
    if not vocabulary.replace("_", "").isalnum():
        raise ValueError("vocabulary must contain only letters, digits, and underscores")
    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be between 1 and 100")
    if page_number < 1:
        raise ValueError("page_number must be at least 1")

    params = {
        "text": text,
        "pagesize": str(page_size),
        "pagenumber": str(page_number),
        "mimeType": "json",
    }
    url = f"https://www.waterqualitydata.us/Codes/{vocabulary}"
    payload = await JsonHttpClient().get_json(url, params)
    query_url = f"{url}?{urlencode(params)}"
    return {
        "vocabulary": vocabulary,
        "results": payload,
        "provenance": _provenance(
            "Water Quality Portal",
            "controlled vocabulary service",
            query_url,
            (
                "Vocabulary results are the source of exact query values; do not silently "
                "substitute "
                "near matches."
            ),
        ),
    }


def main() -> None:
    """Run with stdio transport for local MCP clients."""
    mcp.run(transport="stdio")
