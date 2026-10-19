"""MCP server entry point: builds the app and picks stdio or streamable-HTTP."""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from watershed_evidence_mcp.prompts import register_prompts
from watershed_evidence_mcp.resources import register_resources
from watershed_evidence_mcp.routes import register_routes
from watershed_evidence_mcp.tools import register_tools

# A platform-injected PORT (container hosts bind 0.0.0.0) or MCP_TRANSPORT=streamable-http
# selects HTTP; otherwise stdio.
# Host/port must be set at construction: a localhost default enables DNS-rebinding protection
# that rejects requests from a container host.
HTTP_MODE = bool(os.getenv("PORT")) or os.getenv("MCP_TRANSPORT") == "streamable-http"

mcp = FastMCP(
    name="Watershed Evidence",
    instructions=(
        "Use this read-only server to retrieve public U.S. water-quality evidence. "
        "Resolve a named river before creating a geographic query. Use wqp_available_data "
        "before wqp_measurements. Never present Freshwater Explorer screening context or "
        "WQP observations as a regulatory determination."
    ),
    host=os.getenv("MCP_HOST", "0.0.0.0" if os.getenv("PORT") else "127.0.0.1"),
    port=int(os.getenv("PORT") or os.getenv("MCP_PORT") or 8080),
    stateless_http=HTTP_MODE,  # continuation tokens are self-contained; no session state
)

register_tools(mcp)
register_prompts(mcp)
register_resources(mcp)
register_routes(mcp)


def main() -> None:
    mcp.run(transport="streamable-http" if HTTP_MODE else "stdio")


if __name__ == "__main__":
    main()
