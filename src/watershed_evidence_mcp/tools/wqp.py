"""Tools: Water Quality Portal coverage, stations, observations, and vocabulary."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from watershed_evidence_mcp.adapters.wqp import WqpAdapter
from watershed_evidence_mcp.models import CompatibilityMode, QueryScope, WqpQuery
from watershed_evidence_mcp.provenance import VOCAB_CAVEAT, WQP_CAVEAT
from watershed_evidence_mcp.provenance import provenance as _provenance

WQP_AVAILABLE_DATA_DESCRIPTION = (
    "Preflight a bounded WQP geographic/station query. Returns station geometry and counts of "
    "reported activities/results before any raw measurement retrieval. Counts come from the "
    "WQX 2 summary service (WQX 3 has none), which excludes USGS data added after early 2024: "
    "a USGS station can show few or no recent results here yet have many in wqp_measurements. "
    "Treat counts as a lower bound, not as evidence that recent data are absent."
)

WQX2_SUMMARY_NOTE = (
    "WQX 2 summary counts exclude USGS data added after early 2024; treat them as a lower bound. "
    "Use wqp_measurements (WQX 3) to check recent USGS observations."
)


async def wqp_available_data(scope: QueryScope) -> dict:
    """Retrieve WQP monitoring-location availability summary for one bounded scope."""
    payload, query_url = await WqpAdapter().available_data(scope)
    features = payload.get("features", [])
    return {
        "evidence_type": "coverage_summary",
        "feature_count": len(features),
        "features": features,
        "coverage_note": WQX2_SUMMARY_NOTE,
        "provenance": _provenance(
            "Water Quality Portal", "WQX 2 public web services", query_url, WQP_CAVEAT
        ),
    }


WQX_MODE_RULE = (
    "Choose compatibility_mode deliberately; the server never switches or falls back. "
    "Use 'wqx3' (default) for new analysis and for any USGS data from 2024 onward. Use 'wqx2' "
    "only to reproduce an earlier WQX 2 result, to compare with prior work that used WQX 2 "
    "vocabulary, or (measurements) when laboratory_name is required. If one mode fails, report "
    "the failure; a retry in the other mode returns different vocabulary and must be labelled. "
)

WQP_MONITORING_SITES_DESCRIPTION = (
    "List WQP monitoring stations in one bounded scope from the WQX 3 Station service. Use it "
    "after availability preflight when the agent needs station identifiers for a focused "
    "results query. Properties keep the WQX 3 column names (Location_Identifier, "
    "Location_Type, Location_HUCEightDigitCode, Location_HUCTwelveDigitCode, ...); geometry "
    "uses WQP's standardized NAD83 coordinates and is null when they are missing. Station "
    "records carry no activity/result counts; use wqp_available_data for those. "
    "compatibility_mode='wqx2' returns the legacy WQX 2 GeoJSON instead (MonitoringLocation* "
    "property names, per-station counts, no USGS stations added after early 2024). " + WQX_MODE_RULE
)


async def wqp_monitoring_sites(
    scope: QueryScope, compatibility_mode: CompatibilityMode = "wqx3"
) -> dict:
    """Retrieve WQP station inventory as GeoJSON for one bounded scope."""
    payload, query_url = await WqpAdapter().monitoring_sites(scope, compatibility_mode)
    features = payload.get("features", [])
    wqx3 = compatibility_mode == "wqx3"
    return {
        "evidence_type": "station_inventory",
        "compatibility_mode": compatibility_mode,
        "feature_count": len(features),
        "features": features,
        "coordinate_datum": "NAD83 (WQP standardized)" if wqx3 else "as served by WQP WQX 2",
        "records_without_geometry": sum(f.get("geometry") is None for f in features),
        "provenance": _provenance(
            "Water Quality Portal",
            "WQX 3 public web services (Station)" if wqx3 else "WQX 2 public web services",
            query_url,
            WQP_CAVEAT,
        ),
    }


WQP_MEASUREMENTS_DESCRIPTION = (
    "Retrieve a bounded set of raw WQP water-quality observations. Requires one exact "
    "spatial/station selector, exact WQP characteristic name(s), a date range, and "
    "a result cap. "
    "Preserves "
    "units, qualifiers, detection limits, sample fraction, result status, and method fields "
    "without harmonizing them. compatibility_mode='wqx3' is the default; "
    "'wqx2' (legacy) lacks USGS data added after early 2024. WQX 2 and WQX 3 vocabularies differ "
    "(e.g. sample fraction 'Total' vs 'Unfiltered'); do not merge them as equivalent. "
    + WQX_MODE_RULE
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


WQP_MEASUREMENTS_PAGE_DESCRIPTION = (
    "Retrieve a COMPLETE, explicitly defined WQP observation collection one date window at a "
    "time. Call with no continuation_token first, then pass each response's "
    "collection.continuation_token until it is null. The collection is complete only when "
    "every page from the first to the final one was retrieved. Use wqp_measurements for a "
    "bounded exploratory sample instead. Keep one compatibility_mode for every page. "
    + WQX_MODE_RULE
)


async def wqp_measurements_page(query: WqpQuery, continuation_token: str | None = None) -> dict:
    """Retrieve one complete date window; windows tile the query range without gaps."""
    page = await WqpAdapter().collection_page(query, continuation_token)
    result = page.result
    return {
        "evidence_type": "observation",
        "returned_records": len(result.records),
        "result_limit": query.result_limit,
        "collection": {
            "query_id": page.query_id,
            "window": {"start": page.window_start.isoformat(), "end": page.window_end.isoformat()},
            "window_complete": True,
            "declared_range": {
                "start": query.start_date.isoformat(),
                "end": query.end_date.isoformat(),
            },
            "final_page": page.continuation_token is None,
            "continuation_token": page.continuation_token,
        },
        "cache": {
            "hit": result.cache_hit,
            "retrieved_at": result.retrieved_at.isoformat(),
            "ttl_seconds": 3_600,
        },
        "records": result.records,
        "provenance": _provenance(
            "Water Quality Portal", result.source_version, result.query_url, WQP_CAVEAT
        ),
    }


WQP_VOCAB_SEARCH_DESCRIPTION = (
    "Search an official WQP controlled vocabulary, such as CharacteristicName, Organization, "
    "Characteristictype, or Sitetype. Use this to translate user wording into exact WQP values."
)


async def wqp_vocab_search(
    vocabulary: str, text: str, page_size: int = 20, page_number: int = 1
) -> dict:
    """Discover exact, permissible WQP query values without silent fuzzy matching."""
    if not vocabulary.replace("_", "").isalnum():
        raise ValueError("vocabulary must contain only letters, digits, and underscores")
    if not text.strip() or len(text) > 200:
        raise ValueError("text must be nonblank and no longer than 200 characters")
    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be between 1 and 100")
    if page_number < 1:
        raise ValueError("page_number must be at least 1")

    payload, query_url = await WqpAdapter().vocabulary_search(
        vocabulary, text, page_size=page_size, page_number=page_number
    )
    return {
        "vocabulary": vocabulary,
        "results": payload,
        "no_matches": payload.get("recordCount", 0) == 0,
        "provenance": _provenance(
            "Water Quality Portal",
            "controlled vocabulary service",
            query_url,
            VOCAB_CAVEAT,
        ),
    }


def register(mcp: FastMCP) -> None:
    mcp.tool(description=WQP_AVAILABLE_DATA_DESCRIPTION)(wqp_available_data)
    mcp.tool(description=WQP_MONITORING_SITES_DESCRIPTION)(wqp_monitoring_sites)
    mcp.tool(description=WQP_MEASUREMENTS_DESCRIPTION)(wqp_measurements)
    mcp.tool(description=WQP_MEASUREMENTS_PAGE_DESCRIPTION)(wqp_measurements_page)
    mcp.tool(description=WQP_VOCAB_SEARCH_DESCRIPTION)(wqp_vocab_search)
