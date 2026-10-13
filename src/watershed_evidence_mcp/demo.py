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


def validate_selected_candidate(
    selection: DemoSelection, resolution: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Confirm an explicitly selected river candidate before any downstream retrieval."""
    candidates = resolution.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("river resolution did not return candidates")
    for candidate in candidates:
        if isinstance(candidate, Mapping) and candidate.get("reachcode") == selection.reachcode:
            return candidate
    raise ValueError(f"selected reachcode {selection.reachcode} was not returned by resolution")


def _provenance_lines(label: str, response: Mapping[str, Any]) -> list[str]:
    provenance = response.get("provenance")
    required = ("source", "source_version", "retrieved_at", "query_url", "caveat")
    if not isinstance(provenance, Mapping) or any(
        not isinstance(provenance.get(key), str) for key in required
    ):
        raise ValueError(f"{label} response did not include complete provenance")
    return [
        f"### {label}",
        f"- Source: {provenance['source']} ({provenance['source_version']})",
        f"- Retrieved: {provenance['retrieved_at']}",
        f"- Query: {provenance['query_url']}",
        f"- Caveat: {provenance['caveat']}",
    ]


def _display(value: object) -> str:
    if value in (None, ""):
        return "—"
    return str(value).replace("|", "\\|")


def _matching_baseline(records: object, nhdplusid: str) -> Mapping[str, Any] | None:
    if not isinstance(records, list):
        return None
    for record in records:
        if isinstance(record, Mapping) and str(record.get("COMID")) == nhdplusid:
            return record
    return None


def _comparable_observation_summary(records: object) -> str:
    if not isinstance(records, list) or not records:
        return "No observation records returned."

    values: list[Decimal] = []
    units: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping):
            return "No comparable numeric range is displayed; an observation record is malformed."
        if record.get("qualifier") not in (None, "") or record.get("value_type") != "Actual":
            return "No comparable numeric range is displayed; qualifiers or value types differ."
        unit = record.get("unit")
        if not isinstance(unit, str) or not unit:
            return "No comparable numeric range is displayed; a unit is missing."
        try:
            values.append(Decimal(str(record.get("value"))))
        except (InvalidOperation, ValueError):
            return "No comparable numeric range is displayed; a value is not numeric."
        units.add(unit)

    if len(units) != 1:
        return "No comparable numeric range is displayed; units differ across returned records."
    return f"Comparable bounded-observation range: {min(values)}–{max(values)} {units.pop()}."


def _observation_lines(observations: Mapping[str, Any]) -> list[str]:
    records = observations.get("records")
    if not isinstance(records, list):
        raise ValueError("observation response did not include records")
    lines = [
        "### Observation",
        _comparable_observation_summary(records),
        f"- Returned records: {observations.get('returned_records', len(records))}",
        f"- Result set truncated: {'yes' if observations.get('truncated') else 'no'}",
        "",
        "| Station | Date/time | Value | Unit | Value type | Qualifier | Detection limit | "
        "Method | Laboratory |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("observation response contained a malformed record")
        date_fields = (
            _display(record.get("activity_date")),
            _display(record.get("activity_time")),
        )
        date_time = " ".join(part for part in date_fields if part != "—") or "—"
        detection_limit = (
            " ".join(
                part
                for part in (
                    _display(record.get("detection_limit_value")),
                    _display(record.get("detection_limit_unit")),
                )
                if part != "—"
            )
            or "—"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    _display(record.get("station_id")),
                    date_time,
                    _display(record.get("value")),
                    _display(record.get("unit")),
                    _display(record.get("value_type")),
                    _display(record.get("qualifier")),
                    detection_limit,
                    _display(record.get("method_identifier")),
                    _display(record.get("laboratory_name")),
                ]
            )
            + " |"
        )
    return lines


def render_evidence_packet(
    selection: DemoSelection,
    resolution: Mapping[str, Any],
    coverage: Mapping[str, Any],
    stations: Mapping[str, Any],
    observations: Mapping[str, Any],
    baseline: Mapping[str, Any],
) -> str:
    """Render fully labelled evidence without a regulatory conclusion."""
    candidate = validate_selected_candidate(selection, resolution)
    scope = selection.bounding_box
    if observations.get("evidence_type") != "observation":
        raise ValueError("expected observation evidence from wqp_measurements")
    if coverage.get("evidence_type") != "coverage_summary":
        raise ValueError("expected coverage_summary evidence from wqp_available_data")
    if stations.get("evidence_type") != "station_inventory":
        raise ValueError("expected station_inventory evidence from wqp_monitoring_sites")
    if baseline.get("evidence_type") != "screening_baseline":
        raise ValueError("expected screening_baseline evidence from freshwater_screening_baseline")

    matched_baseline = _matching_baseline(baseline.get("records"), selection.nhdplusid)
    baseline_summary = "No Freshwater Explorer record matched the selected NHDPlusID."
    if matched_baseline is not None:
        baseline_summary = (
            f"COMID {matched_baseline.get('COMID')} (`{matched_baseline.get('StreamName')}`): "
            f"AvgPredEC={matched_baseline.get('AvgPredEC')} (raw Explorer attribute)."
        )

    lines = [
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
        "",
        "## Evidence",
        f"- **Coverage summary** — {coverage.get('feature_count', 0)} WQP summary features in the "
        "selected bounding box.",
        f"- **Station inventory** — {stations.get('feature_count', 0)} WQP station features in the "
        "selected bounding box.",
        "- **Screening baseline** — Freshwater Explorer modelled context, not an observation.",
        "- **Assessment context — not retrieved** — this demo does not call ATTAINS because its "
        "public service requires a runtime API key. It makes no assessment finding.",
        "",
    ]
    lines.extend(_observation_lines(observations))
    lines.extend(["", "### Screening baseline", baseline_summary, ""])
    for label, response in [
        ("River-name resolution provenance", resolution),
        ("WQP coverage provenance", coverage),
        ("WQP station inventory provenance", stations),
        ("WQP observation provenance", observations),
        ("Freshwater Explorer baseline provenance", baseline),
    ]:
        lines.extend(_provenance_lines(label, response))
        lines.append("")
    lines.extend(
        [
            "## Interpretation boundary",
            "Screening comparison only — not a regulatory determination. The observation table "
            "retains returned identifiers, dates, units, qualifiers, detection limits, methods, "
            "and laboratory fields. Confirm temporal alignment and local assessment criteria "
            "before making an elevation or impairment claim.",
        ]
    )
    return "\n".join(lines)
