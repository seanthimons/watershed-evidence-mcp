"""Tools: Water Quality Portal coverage, stations, observations, and vocabulary."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from watershed_evidence_mcp.adapters.wqp import WqpAdapter
from watershed_evidence_mcp.models import QueryScope, WqpQuery
from watershed_evidence_mcp.provenance import VOCAB_CAVEAT, WQP_CAVEAT
from watershed_evidence_mcp.provenance import provenance as _provenance

WQP_AVAILABLE_DATA_DESCRIPTION = (
    "Preflight a bounded WQP geographic/station query. Returns station geometry and counts of "
    "reported activities/results before any raw measurement retrieval."
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


WQP_MONITORING_SITES_DESCRIPTION = (
    "List WQP monitoring stations in one bounded scope. Use it after availability preflight "
    "when the agent needs station identifiers for a focused results query."
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


WQP_MEASUREMENTS_DESCRIPTION = (
    "Retrieve a bounded set of raw WQP water-quality observations. Requires one exact "
    "spatial/station selector, exact WQP characteristic name(s), a date range, and "
    "a result cap. "
    "Preserves "
    "units, qualifiers, detection limits, and method fields without harmonizing them."
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
    "bounded exploratory sample instead."
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
