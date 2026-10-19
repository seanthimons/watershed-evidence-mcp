"""Tool: EPA ATTAINS assessment reporting context."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from watershed_evidence_mcp.adapters.attains import AttainsAdapter
from watershed_evidence_mcp.models import AssessmentContextQuery
from watershed_evidence_mcp.provenance import ATTAINS_CAVEAT
from watershed_evidence_mcp.provenance import provenance as _provenance

GET_ASSESSMENT_CONTEXT_DESCRIPTION = (
    "Retrieve read-only EPA ATTAINS assessment reporting context for one exact "
    "assessment unit or by a disclosed HUC12-to-assessment-unit resolution. Returns reporting-"
    "cycle status, designated uses, parameter context, source identifiers, and provenance. "
    "An assessment is not proof of a present-day condition or causal finding."
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


def register(mcp: FastMCP) -> None:
    mcp.tool(description=GET_ASSESSMENT_CONTEXT_DESCRIPTION)(get_assessment_context)
