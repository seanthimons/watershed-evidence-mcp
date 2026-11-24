import httpx
import pytest

from watershed_evidence_mcp.adapters.wbd import WbdAdapter
from watershed_evidence_mcp.http import JsonHttpClient
from watershed_evidence_mcp.models import GeoPoint
from watershed_evidence_mcp.provenance import WBD_CAVEAT
from watershed_evidence_mcp.tools import watersheds as tool

SW = GeoPoint(latitude=39.1, longitude=-84.4)
NE = GeoPoint(latitude=39.3, longitude=-84.2)


def _features(*hucs: str) -> list[dict]:
    return [
        {"attributes": {"huc12": h, "name": f"W{h}", "areasqkm": 12.5, "states": "OH,IN"}}
        for h in hucs
    ]


def _patch(monkeypatch, payload) -> list[httpx.Request]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload, request=request)

    client = JsonHttpClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(tool, "WbdAdapter", lambda: WbdAdapter(client))
    return requests


@pytest.mark.asyncio
async def test_corner_order_is_irrelevant_and_query_is_an_intersects_envelope(monkeypatch) -> None:
    requests = _patch(monkeypatch, {"features": _features("050902020902")})

    forward = await tool.resolve_watershed(SW, NE)
    reverse = await tool.resolve_watershed(NE, SW)

    assert forward["query_box"] == reverse["query_box"]
    assert forward["query_box"] == {"west": -84.4, "south": 39.1, "east": -84.2, "north": 39.3}
    q = requests[0].url.params
    assert "/MapServer/6/query" in str(requests[0].url)
    assert q["geometry"] == "-84.4,39.1,-84.2,39.3"
    assert q["spatialRel"] == "esriSpatialRelIntersects"
    assert q["returnGeometry"] == "false"
    assert forward["candidates"][0]["huc"] == "050902020902"
    assert forward["warning"] is None
    assert forward["provenance"]["caveat"] == WBD_CAVEAT


@pytest.mark.asyncio
async def test_huc8_uses_layer_4(monkeypatch) -> None:
    payload = {"features": [{"attributes": {"huc8": "05090202", "name": "Little Miami"}}]}
    requests = _patch(monkeypatch, payload)
    result = await tool.resolve_watershed(SW, NE, level="huc8")
    assert "/MapServer/4/query" in str(requests[0].url)
    assert result["candidates"][0]["huc"] == "05090202"


@pytest.mark.asyncio
async def test_multiple_matches_truncation_and_empty_each_warn(monkeypatch) -> None:
    _patch(monkeypatch, {"features": _features("050902020902", "050902021204")})
    assert "straddles" in (await tool.resolve_watershed(SW, NE))["warning"]

    _patch(monkeypatch, {"features": _features("050902020902"), "exceededTransferLimit": True})
    result = await tool.resolve_watershed(SW, NE)
    assert result["truncated"] is True and "More than 50" in result["warning"]

    _patch(monkeypatch, {"features": []})
    result = await tool.resolve_watershed(SW, NE)
    assert result["candidates"] == [] and "No watershed" in result["warning"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("a", "b", "message"),
    [
        (SW, GeoPoint(latitude=39.9, longitude=-84.2), "at most 0.5"),  # too tall
        (SW, GeoPoint(latitude=39.3, longitude=-83.0), "at most 0.5"),  # too wide
        (
            GeoPoint(latitude=39.1, longitude=179.9),
            GeoPoint(latitude=39.3, longitude=-179.9),
            "at most 0.5",
        ),  # antimeridian becomes a ~360 degree box
        (SW, GeoPoint(latitude=39.1, longitude=-84.2), "must differ"),  # a click, no drag
    ],
)
async def test_invalid_boxes_are_rejected_before_any_network_call(monkeypatch, a, b, message):
    requests = _patch(monkeypatch, {"features": []})
    with pytest.raises(ValueError, match=message):
        await tool.resolve_watershed(a, b)
    assert requests == []


@pytest.mark.asyncio
async def test_exactly_half_a_degree_is_accepted_and_mcp_rejects_bad_latitude(monkeypatch) -> None:
    from mcp.shared.memory import create_connected_server_and_client_session

    from watershed_evidence_mcp.server import mcp

    _patch(monkeypatch, {"features": _features("050902020902")})
    result = await tool.resolve_watershed(
        GeoPoint(latitude=39.1, longitude=-84.4), GeoPoint(latitude=39.3, longitude=-83.9)
    )
    assert result["provenance"]["source_version"] == "ArcGIS MapServer layer 6"

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        bad = await client.call_tool(
            "resolve_watershed",
            {"corner_1": {"latitude": 95, "longitude": -84.4}, "corner_2": NE.model_dump()},
        )
    assert bad.isError
