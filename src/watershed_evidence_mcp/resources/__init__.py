"""Static reference resources."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from watershed_evidence_mcp.provenance import CAVEATS

EVIDENCE_TYPES = {
    "observation": "Raw WQP results with original units, qualifiers, detection limits, methods.",
    "coverage_summary": "WQP counts of activities/results per monitoring location.",
    "station_inventory": "WQP monitoring-location metadata.",
    "screening_baseline": "Freshwater Explorer modelled context; not observations or findings.",
    "assessment_context": "ATTAINS reporting-cycle decisions; not current condition or cause.",
}


def register_resources(mcp: FastMCP) -> None:
    @mcp.resource("watershed://evidence-types", mime_type="application/json")
    def evidence_types() -> str:
        """The evidence_type values tools return and what each does and does not support."""
        return json.dumps(EVIDENCE_TYPES, indent=2)

    @mcp.resource("watershed://caveats", mime_type="application/json")
    def caveats() -> str:
        """Per-source data-use caveats attached to tool provenance."""
        return json.dumps(CAVEATS, indent=2)
