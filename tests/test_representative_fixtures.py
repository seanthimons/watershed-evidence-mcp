"""Representative, redacted public-source fixtures remain fully offline."""

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from watershed_evidence_mcp.adapters.attains import normalize_assessment
from watershed_evidence_mcp.adapters.freshwater import FreshwaterAdapter
from watershed_evidence_mcp.adapters.waters import WatersAdapter
from watershed_evidence_mcp.adapters.wqp import WqpAdapter
from watershed_evidence_mcp.cache import DuckDbCache
from watershed_evidence_mcp.http import JsonHttpClient
from watershed_evidence_mcp.models import BoundingBox, QueryScope, WqpQuery

FIXTURES = Path(__file__).parent / "fixtures"


def load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_waters_fixture_exercises_candidate_retrieval_without_network() -> None:
    payload = load_json("waters_geoviewer_feature.json")
    adapter = WatersAdapter(
        JsonHttpClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
        )
    )

    candidates, query_url = await adapter.resolve_name("Little Miami River", max_candidates=5)

    assert candidates[0].reachcode == "05090202000010"
    assert "resultRecordCount=5" in query_url


@pytest.mark.asyncio
async def test_freshwater_fixture_exercises_bounded_adapter_without_network() -> None:
    payload = load_json("freshwater_predicted_conductivity.json")
    adapter = FreshwaterAdapter(
        JsonHttpClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
        )
    )

    records, query_url, truncated = await adapter.predicted_conductivity(
        BoundingBox(west=-84.1, south=39.1, east=-84.0, north=39.2), max_records=10
    )

    assert records[0]["properties"] == payload["features"][0]["attributes"]
    assert records[0]["id"] == 123456
    assert records[0]["geometry"] == {
        "type": "LineString",
        "coordinates": [[-84.05, 39.15], [-84.04, 39.16]],
    }
    assert "outSR=4326" in query_url and "returnGeometry=true" in query_url
    assert truncated is False
    assert "resultRecordCount=11" in query_url


@pytest.mark.asyncio
async def test_wqp_fixture_preserves_raw_evidence_fields_without_network(tmp_path) -> None:
    response = (FIXTURES / "wqp_result.csv").read_text(encoding="utf-8")

    class FixtureClient:
        async def get_text(self, *args, **kwargs) -> str:
            return response

    adapter = WqpAdapter(client=FixtureClient(), cache=DuckDbCache(tmp_path / "fixture.duckdb"))
    result = await adapter.measurements(
        WqpQuery(
            scope=QueryScope(station_ids=["USGS-03246200"]),
            characteristic_names=["Specific conductance"],
            start_date=date(1970, 1, 1),
            end_date=date(1980, 1, 1),
            result_limit=25,
        )
    )

    assert result.records[0]["unit"] == "uS/cm @25C"
    assert result.records[0]["method_identifier"] == "USGS I-1750"


def test_attains_fixture_preserves_reporting_context_without_network() -> None:
    fixture = load_json("attains_assessment.json")

    normalized = normalize_assessment(fixture["assessment"], fixture["report"])

    assert normalized["source_identifiers"] == {
        "assessment_unit_id": "DCTFD01R_00",
        "organization_id": "DOEE",
    }
    assert normalized["assessment_status"] == "Not Supporting"
