"""Prompt: the evidence workflow for a named river."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def investigate_waterbody(river_name: str) -> str:
    """Step-by-step, caveat-preserving plan for gathering evidence on one river."""
    return f"""Investigate public water-quality evidence for "{river_name}".

1. resolve_waterbody: list candidates. If more than one, ask the user to choose; never guess.
2. Agree an explicit spatial scope (bounding box, point/radius, or station IDs) and date range.
3. wqp_available_data, then wqp_monitoring_sites: report what exists before fetching values.
4. wqp_vocab_search: translate the user's parameter wording into an exact WQP characteristic.
5. wqp_measurements for a sample; wqp_measurements_page only when a complete collection is
   needed (follow continuation tokens to final_page, or say the collection is incomplete).
6. Optionally add freshwater_screening_baseline and get_assessment_context, each labelled
   as its own evidence type.

Finish with: what was retrieved (counts, truncation, date range), what is missing
(coverage gaps, non-detects, unit/method differences left unharmonized), and the source
caveats. Do not state or imply a regulatory determination, impairment, or cause.
Cite each response's provenance.query_url."""


def register(mcp: FastMCP) -> None:
    mcp.prompt(name="investigate_waterbody")(investigate_waterbody)
