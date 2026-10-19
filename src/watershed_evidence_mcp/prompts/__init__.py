"""Reusable workflow prompts."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from watershed_evidence_mcp.prompts import investigate


def register_prompts(mcp: FastMCP) -> None:
    investigate.register(mcp)
