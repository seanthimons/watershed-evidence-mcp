import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from watershed_evidence_mcp.server import mcp

EXPECTED_TOOLS = {
    "resolve_waterbody",
    "wqp_available_data",
    "wqp_monitoring_sites",
    "wqp_measurements",
    "wqp_measurements_page",
    "wqp_vocab_search",
    "get_assessment_context",
    "freshwater_screening_baseline",
}


@pytest.mark.asyncio
async def test_registered_surface() -> None:
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        tools = (await client.list_tools()).tools
        assert {t.name for t in tools} == EXPECTED_TOOLS
        assert all(t.description for t in tools)
        prompts = (await client.list_prompts()).prompts
        assert [p.name for p in prompts] == ["investigate_waterbody"]
        resources = {str(r.uri) for r in (await client.list_resources()).resources}
        assert resources == {"watershed://evidence-types", "watershed://caveats"}
        caveats = await client.read_resource("watershed://caveats")
        assert "regulatory" in json.loads(caveats.contents[0].text)["freshwater"]
