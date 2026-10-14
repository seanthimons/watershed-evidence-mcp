#!/usr/bin/env python3
"""Run the bounded Little Miami evidence demo through the local MCP server."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from watershed_evidence_mcp.demo import (
    DemoSelection,
    render_evidence_packet,
    validate_selected_candidate,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_BOUNDS = {"west": -84.32, "south": 39.15, "east": -84.27, "north": 39.20}
SELECTED_REACHCODE = "05090202002563"
SELECTED_NHDPLUSID = "25243915"
SELECTED_STATION = "USGS-03245500"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the rendered Markdown packet to this path instead of standard output.",
    )
    return parser.parse_args()


def tool_json(result: Any, tool_name: str) -> dict[str, Any]:
    """Get one JSON object from a successful MCP tool result."""
    if result.isError:
        message = "; ".join(content.text for content in result.content if hasattr(content, "text"))
        raise RuntimeError(f"{tool_name} failed: {message}")
    text_parts = [content.text for content in result.content if hasattr(content, "text")]
    if len(text_parts) != 1:
        raise RuntimeError(
            f"{tool_name} returned {len(text_parts)} text payloads; expected one JSON object"
        )
    payload = json.loads(text_parts[0])
    if not isinstance(payload, dict):
        raise RuntimeError(f"{tool_name} returned a non-object JSON payload")
    return payload


async def run_demo() -> str:
    """Execute the documented call sequence through stdio MCP, then render its evidence packet."""
    server = StdioServerParameters(
        command="uv",
        args=["run", "watershed-evidence-mcp"],
        cwd=REPO_ROOT,
    )
    scope = {"bounding_box": DEMO_BOUNDS}
    selection = DemoSelection(
        reachcode=SELECTED_REACHCODE,
        nhdplusid=SELECTED_NHDPLUSID,
        bounding_box=DEMO_BOUNDS,
        station_id=SELECTED_STATION,
    )
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            resolution = tool_json(
                await session.call_tool(
                    "resolve_waterbody", {"river_name": "Little Miami River", "max_candidates": 10}
                ),
                "resolve_waterbody",
            )
            validate_selected_candidate(selection, resolution)
            coverage = tool_json(
                await session.call_tool("wqp_available_data", {"scope": scope}),
                "wqp_available_data",
            )
            stations = tool_json(
                await session.call_tool("wqp_monitoring_sites", {"scope": scope}),
                "wqp_monitoring_sites",
            )
            observations = tool_json(
                await session.call_tool(
                    "wqp_measurements",
                    {
                        "query": {
                            "scope": {"station_ids": [SELECTED_STATION]},
                            "characteristic_names": ["Specific conductance"],
                            "start_date": "2023-01-01",
                            "end_date": "2025-12-31",
                            "result_limit": 25,
                        }
                    },
                ),
                "wqp_measurements",
            )
            baseline = tool_json(
                await session.call_tool(
                    "freshwater_screening_baseline",
                    {"bounding_box": DEMO_BOUNDS, "max_records": 25},
                ),
                "freshwater_screening_baseline",
            )

    return render_evidence_packet(selection, resolution, coverage, stations, observations, baseline)


def main() -> None:
    args = parse_args()
    packet = anyio.run(run_demo)
    if args.output is None:
        print(packet)
        return
    args.output.write_text(packet + "\n", encoding="utf-8")
    print(f"Wrote evidence packet to {args.output}")


if __name__ == "__main__":
    main()
