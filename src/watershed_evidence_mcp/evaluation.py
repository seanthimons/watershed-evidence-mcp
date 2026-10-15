"""Opt-in, bounded live evaluation for public-source evidence adapters.

This module is deliberately separate from pytest: deterministic tests always use
mock transports, while this evaluator makes clearly labelled public requests and
records only operational metadata -- never raw response bodies or credentials.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from watershed_evidence_mcp.adapters.attains import AttainsAdapter
from watershed_evidence_mcp.adapters.freshwater import FreshwaterAdapter
from watershed_evidence_mcp.adapters.waters import WatersAdapter
from watershed_evidence_mcp.adapters.wqp import WqpAdapter
from watershed_evidence_mcp.cache import DuckDbCache
from watershed_evidence_mcp.models import AssessmentContextQuery, BoundingBox, QueryScope, WqpQuery

EVALUATION_VERSION = "1"
PUBLIC_STATION_ID = "USGS-03246200"
PUBLIC_BOUNDS = BoundingBox(west=-84.1, south=39.1, east=-84.0, north=39.2)

MAX_EVALUATION_PAGES = 20


@dataclass(frozen=True)
class EvaluationResult:
    """Metadata-only outcome from one bounded live request."""

    scenario: str
    endpoint: str
    query_shape: dict[str, Any]
    outcome: str
    http_outcome: str
    record_count: int | None
    duration_ms: int
    detail: str | None = None


def _safe_error(exc: Exception) -> str:
    """Return one actionable line without retaining a traceback or response body."""
    return str(exc).splitlines()[0][:500]


def _http_outcome_from_error(exc: Exception) -> str:
    match = re.search(r"HTTP (\d{3})", str(exc))
    return f"HTTP {match.group(1)}" if match else "request error"


async def _measure(
    scenario: str,
    endpoint: str,
    query_shape: dict[str, Any],
    request: Callable[[], Awaitable[int]],
) -> EvaluationResult:
    started = time.perf_counter()
    try:
        count = await request()
    except Exception as exc:  # report live-service failures rather than hiding them
        return EvaluationResult(
            scenario=scenario,
            endpoint=endpoint,
            query_shape=query_shape,
            outcome="error",
            http_outcome=_http_outcome_from_error(exc),
            record_count=None,
            duration_ms=round((time.perf_counter() - started) * 1_000),
            detail=_safe_error(exc),
        )
    return EvaluationResult(
        scenario=scenario,
        endpoint=endpoint,
        query_shape=query_shape,
        outcome="success",
        http_outcome="2xx",
        record_count=count,
        duration_ms=round((time.perf_counter() - started) * 1_000),
    )


async def run_live_evaluation() -> tuple[datetime, list[EvaluationResult]]:
    """Run a small, public, read-only evidence evaluation with hard query bounds."""
    scope = QueryScope(station_ids=[PUBLIC_STATION_ID])
    query = WqpQuery(
        scope=scope,
        characteristic_names=["Specific conductance"],
        start_date=datetime(1970, 1, 1).date(),
        end_date=datetime(1980, 1, 1).date(),
        result_limit=25,
    )
    temporary_cache = tempfile.TemporaryDirectory(prefix="watershed-evidence-mcp-evaluation-")
    wqp = WqpAdapter(cache=DuckDbCache(Path(temporary_cache.name) / "wqp.duckdb"))
    waters = WatersAdapter()
    freshwater = FreshwaterAdapter()
    attains = AttainsAdapter()

    async def waters_request() -> int:
        candidates, _ = await waters.resolve_name("Little Miami River", max_candidates=5)
        return len(candidates)

    async def summary_request() -> int:
        payload, _ = await wqp.available_data(scope)
        return len(payload.get("features", []))

    async def sites_request() -> int:
        payload, _ = await wqp.monitoring_sites(scope)
        return len(payload.get("features", []))

    async def vocabulary_request() -> int:
        payload, _ = await wqp.vocabulary_search(
            "CharacteristicName", "Specific conductance", page_size=5, page_number=1
        )
        return int(payload.get("recordCount", 0))

    async def results_request() -> int:
        result = await wqp.measurements(query)
        return len(result.records)

    async def paged_request() -> int:
        paged = query.model_copy(update={"result_limit": 10})
        total, token = 0, None
        for _ in range(MAX_EVALUATION_PAGES):
            page = await wqp.collection_page(paged, token)
            total += len(page.result.records)
            token = page.continuation_token
            if token is None:
                return total
        raise ValueError("paged collection did not finish within the evaluation page bound")

    async def freshwater_request() -> int:
        features, _, _ = await freshwater.predicted_conductivity(PUBLIC_BOUNDS, max_records=10)
        if features and not any(f["geometry"] for f in features):
            raise ValueError("Freshwater Explorer returned no stream-reach geometry")
        return len(features)

    async def attains_request() -> int:
        result = await attains.assessment_context(
            AssessmentContextQuery(assessment_unit_id="DCTFD01R_00", reporting_cycle="2024")
        )
        return len(result.records)

    results = [
        await _measure(
            "WATERS river-name ambiguity",
            "EPA WATERS GeoViewer MapServer/1/query",
            {"river_name": "Little Miami River", "max_candidates": 5},
            waters_request,
        ),
        await _measure(
            "WQP availability summary",
            "Water Quality Portal summary/monitoringLocation/search",
            {"station_ids": [PUBLIC_STATION_ID]},
            summary_request,
        ),
        await _measure(
            "WQP station inventory",
            "Water Quality Portal Station/search",
            {"station_ids": [PUBLIC_STATION_ID]},
            sites_request,
        ),
        await _measure(
            "WQP controlled vocabulary",
            "Water Quality Portal Codes/characteristicname",
            {
                "vocabulary": "CharacteristicName",
                "text": "Specific conductance",
                "page_size": 5,
                "page_number": 1,
            },
            vocabulary_request,
        ),
        await _measure(
            "WQP bounded measurements",
            "Water Quality Portal Result/search",
            {
                "station_ids": [PUBLIC_STATION_ID],
                "characteristic_names": ["Specific conductance"],
                "date_range": "1970-01-01 through 1980-01-01",
                "result_limit": 25,
            },
            results_request,
        ),
        await _measure(
            "WQP paged complete collection",
            "Water Quality Portal Result/search (date-window pages)",
            {
                "station_ids": [PUBLIC_STATION_ID],
                "characteristic_names": ["Specific conductance"],
                "date_range": "1970-01-01 through 1980-01-01",
                "result_limit": 10,
                "max_pages": MAX_EVALUATION_PAGES,
            },
            paged_request,
        ),
        await _measure(
            "Freshwater Explorer screening baseline",
            "EPA Freshwater Explorer PredECHydroline FeatureServer/0/query",
            {"bounding_box": "-84.1,39.1,-84.0,39.2", "max_records": 10},
            freshwater_request,
        ),
    ]
    if os.getenv("ATTAINS_API_KEY"):
        results.append(
            await _measure(
                "ATTAINS assessment context",
                "EPA ATTAINS assessments",
                {"assessment_unit_id": "DCTFD01R_00", "reporting_cycle": "2024"},
                attains_request,
            )
        )
    else:
        results.append(
            EvaluationResult(
                scenario="ATTAINS assessment context",
                endpoint="EPA ATTAINS assessments",
                query_shape={"assessment_unit_id": "DCTFD01R_00", "reporting_cycle": "2024"},
                outcome="skipped",
                http_outcome="not requested",
                record_count=None,
                duration_ms=0,
                detail="ATTAINS_API_KEY is not configured",
            )
        )
    temporary_cache.cleanup()
    return datetime.now(UTC), results


def report_payload(ran_at: datetime, results: list[EvaluationResult]) -> dict[str, Any]:
    """Create the portable, credential-free machine-readable evaluation record."""
    return {
        "evaluation_version": EVALUATION_VERSION,
        "ran_at": ran_at.isoformat(),
        "network": "opt-in live public-service requests; no response payloads retained",
        "results": [asdict(result) for result in results],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    """Render the companion human-readable report from the JSON payload."""
    lines = [
        "# Watershed Evidence MCP live evaluation",
        "",
        f"- Evaluation version: `{payload['evaluation_version']}`",
        f"- Ran at (UTC): `{payload['ran_at']}`",
        f"- Network policy: {payload['network']}",
        "",
        "| Scenario | Endpoint | Query shape | Outcome | HTTP | Records | Duration | Detail |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for result in payload["results"]:
        query_shape = json.dumps(result["query_shape"], sort_keys=True).replace("|", "\\|")
        detail = (result["detail"] or "").replace("|", "\\|")
        records = "" if result["record_count"] is None else str(result["record_count"])
        row_template = (
            "| {scenario} | {endpoint} | `{query_shape}` | {outcome} | {http_outcome} | "
            "{records} | {duration} ms | {detail} |"
        )
        lines.append(
            row_template.format(
                scenario=result["scenario"],
                endpoint=result["endpoint"],
                query_shape=query_shape,
                outcome=result["outcome"],
                http_outcome=result["http_outcome"],
                records=records,
                duration=result["duration_ms"],
                detail=detail,
            )
        )
    lines.extend(
        [
            "",
            "The report intentionally excludes raw response bodies, credentials, and private URLs.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_reports(
    output_dir: Path, ran_at: datetime, results: list[EvaluationResult]
) -> tuple[Path, Path]:
    """Write dated JSON and Markdown reports, returning their exact paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = report_payload(ran_at, results)
    stamp = ran_at.strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"live-evaluation-{stamp}.json"
    markdown_path = output_dir / f"live-evaluation-{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def main(output_dir: Path) -> tuple[Path, Path]:
    """Run the live evaluation synchronously for the command-line wrapper."""
    ran_at, results = asyncio.run(run_live_evaluation())
    return write_reports(output_dir, ran_at, results)
