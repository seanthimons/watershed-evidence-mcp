"""Presentation rendering for the bounded Little Miami MCP demo."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True)
class DemoSelection:
    """Explicit geographic and station choices made after river-name resolution."""

    reachcode: str
    nhdplusid: str
    bounding_box: Mapping[str, float]
    station_id: str


def _query_url(response: Mapping[str, Any]) -> str:
    provenance = response.get("provenance")
    if not isinstance(provenance, Mapping) or not isinstance(provenance.get("query_url"), str):
        raise ValueError("MCP response did not include a provenance query_url")
    return provenance["query_url"]


def _numeric_values(records: object) -> list[Decimal]:
    if not isinstance(records, list):
        return []
    values: list[Decimal] = []
    for record in records:
        if not isinstance(record, Mapping) or record.get("value") is None:
            continue
        try:
            values.append(Decimal(str(record["value"])))
        except InvalidOperation:
            continue
    return values


def _selected_candidate(
    selection: DemoSelection, resolution: Mapping[str, Any]
) -> Mapping[str, Any]:
    candidates = resolution.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("river resolution did not return candidates")
    for candidate in candidates:
        if isinstance(candidate, Mapping) and candidate.get("reachcode") == selection.reachcode:
            return candidate
    raise ValueError(f"selected reachcode {selection.reachcode} was not returned by resolution")


def _matching_baseline(records: object, nhdplusid: str) -> Mapping[str, Any] | None:
    if not isinstance(records, list):
        return None
    for record in records:
        if isinstance(record, Mapping) and str(record.get("COMID")) == nhdplusid:
            return record
    return None


def render_evidence_packet(
    selection: DemoSelection,
    resolution: Mapping[str, Any],
    coverage: Mapping[str, Any],
    stations: Mapping[str, Any],
    observations: Mapping[str, Any],
    baseline: Mapping[str, Any],
) -> str:
    """Render explicitly labelled evidence without a regulatory conclusion."""
    candidate = _selected_candidate(selection, resolution)
    observation_values = _numeric_values(observations.get("records"))
    matched_baseline = _matching_baseline(baseline.get("records"), selection.nhdplusid)
    scope = selection.bounding_box

    if observations.get("evidence_type") != "observation":
        raise ValueError("expected observation evidence from wqp_measurements")
    if coverage.get("evidence_type") != "coverage_summary":
        raise ValueError("expected coverage_summary evidence from wqp_available_data")
    if baseline.get("evidence_type") != "screening_baseline":
        raise ValueError("expected screening_baseline evidence from freshwater_screening_baseline")

    observation_summary = "No numeric observations returned."
    if observation_values:
        observation_summary = (
            f"{len(observation_values)} bounded numeric values; range "
            f"{min(observation_values)}–{max(observation_values)}."
        )

    baseline_summary = "No Freshwater Explorer record matched the selected NHDPlusID."
    if matched_baseline is not None:
        predicted = matched_baseline.get("AvgPredEC")
        baseline_summary = (
            f"COMID {matched_baseline.get('COMID')} (`{matched_baseline.get('StreamName')}`): "
            f"AvgPredEC={predicted}."
        )

    truncation = "yes" if observations.get("truncated") else "no"
    return "\n".join(
        [
            "# Little Miami River near Milford — evidence packet",
            "",
            "## Question",
            "Is conductivity elevated near Milford relative to expected background, and "
            "what evidence supports that screening question?",
            "",
            "## Scope selection (not evidence)",
            "`Little Miami River` is ambiguous. The candidate and scope were selected explicitly "
            "before data retrieval.",
            f"- Selected candidate: `{candidate.get('name')}`; reachcode `{selection.reachcode}`; "
            f"NHDPlusID `{selection.nhdplusid}`.",
            f"- Selected WQP bounding box: `{scope['west']},{scope['south']},"
            f"{scope['east']},{scope['north']}`.",
            f"- Selected monitoring station for observations: `{selection.station_id}`.",
            f"- Resolution query: {_query_url(resolution)}",
            "",
            "## Evidence",
            f"- **Coverage summary** — {coverage.get('feature_count', 0)} WQP summary features "
            "in the "
            f"selected bounding box. Source query: {_query_url(coverage)}",
            f"- **Station inventory** — {stations.get('feature_count', 0)} WQP station features "
            "in the "
            f"selected bounding box. Source query: {_query_url(stations)}",
            f"- **Observation** — {observation_summary} Result set truncated: {truncation}. "
            f"Source query: {_query_url(observations)}",
            f"- **Screening baseline** — {baseline_summary} This is Freshwater Explorer modelled "
            f"context, not an observation. Source query: {_query_url(baseline)}",
            "",
            "## Interpretation boundary",
            "Screening comparison only — not a regulatory determination. The displayed WQP values "
            "are bounded public observations and the Freshwater Explorer value is a modelled "
            "background context. Confirm temporal alignment, unit compatibility, methods, "
            "qualifiers, and local "
            "assessment criteria before making an elevation or impairment claim.",
            "",
            "## Provenance",
            f"- River-name resolution: {_query_url(resolution)}",
            f"- WQP coverage: {_query_url(coverage)}",
            f"- WQP station inventory: {_query_url(stations)}",
            f"- WQP observations: {_query_url(observations)}",
            f"- Freshwater Explorer baseline: {_query_url(baseline)}",
        ]
    )
