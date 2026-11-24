"""Tool registration, grouped by upstream source."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from watershed_evidence_mcp.tools import attains, freshwater, waters, watersheds, wqp


def register_tools(mcp: FastMCP) -> None:
    waters.register(mcp)
    watersheds.register(mcp)
    wqp.register(mcp)
    freshwater.register(mcp)
    attains.register(mcp)
