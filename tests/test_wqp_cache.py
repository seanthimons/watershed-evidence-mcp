from datetime import date

import pytest

from watershed_evidence_mcp.adapters.wqp import WqpAdapter
from watershed_evidence_mcp.cache import DuckDbCache
from watershed_evidence_mcp.http import UpstreamServiceError
from watershed_evidence_mcp.models import BoundingBox, QueryScope, WqpQuery


class RecordingClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    async def get_text(
        self, url: str, params: dict[str, str] | None = None, **kwargs: object
    ) -> str:
        self.calls += 1
        return self.response


def valid_query(result_limit: int = 1) -> WqpQuery:
    return WqpQuery(
        scope=QueryScope(bounding_box=BoundingBox(west=-84.0, south=39.0, east=-83.9, north=39.1)),
        characteristic_names=["Specific conductance"],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        result_limit=result_limit,
    )


def test_cache_key_is_stable_for_equivalent_parameter_order(tmp_path) -> None:
    cache = DuckDbCache(tmp_path / "wqp-cache.duckdb")

    first = cache.key_for(
        source="Water Quality Portal",
        source_version="WQX 2 public web services",
        endpoint="Result/search",
        parameters={"b": "two", "a": "one"},
    )
    second = cache.key_for(
        source="Water Quality Portal",
        source_version="WQX 2 public web services",
        endpoint="Result/search",
        parameters={"a": "one", "b": "two"},
    )

    assert first == second


@pytest.mark.asyncio
async def test_identical_measurement_request_uses_cache_and_preserves_retrieval_metadata(
    tmp_path,
) -> None:
    client = RecordingClient(
        "OrganizationIdentifier,MonitoringLocationIdentifier,CharacteristicName,ResultMeasureValue\n"
        "USGS-OH,USGS-1,Specific conductance,100\n"
    )
    adapter = WqpAdapter(client=client, cache=DuckDbCache(tmp_path / "wqp-cache.duckdb"))

    first = await adapter.measurements(valid_query())
    second = await adapter.measurements(valid_query())

    assert client.calls == 1
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.retrieved_at == first.retrieved_at
    assert second.query_url == first.query_url
    assert second.source_version == "WQX 2 public web services"


@pytest.mark.asyncio
async def test_capped_measurements_declare_truncation_and_safe_continuation(tmp_path) -> None:
    client = RecordingClient(
        "OrganizationIdentifier,MonitoringLocationIdentifier,CharacteristicName,ResultMeasureValue\n"
        "USGS-OH,USGS-1,Specific conductance,100\n"
        "USGS-OH,USGS-1,Specific conductance,101\n"
    )
    adapter = WqpAdapter(client=client, cache=DuckDbCache(tmp_path / "wqp-cache.duckdb"))

    result = await adapter.measurements(valid_query(result_limit=1))

    assert len(result.records) == 1
    assert result.truncated is True
    assert "narrow" in result.continuation.lower()


@pytest.mark.asyncio
async def test_malformed_wqp_csv_fails_informatively(tmp_path) -> None:
    client = RecordingClient("UnexpectedColumn\nvalue\n")
    adapter = WqpAdapter(client=client, cache=DuckDbCache(tmp_path / "wqp-cache.duckdb"))

    with pytest.raises(UpstreamServiceError, match="required identifier/characteristic"):
        await adapter.measurements(valid_query())


@pytest.mark.asyncio
async def test_header_only_wqp_csv_is_a_valid_empty_result(tmp_path) -> None:
    client = RecordingClient("MonitoringLocationIdentifier,CharacteristicName\n")
    adapter = WqpAdapter(client=client, cache=DuckDbCache(tmp_path / "wqp-cache.duckdb"))

    result = await adapter.measurements(valid_query())

    assert result.records == []
    assert result.truncated is False


@pytest.mark.asyncio
async def test_wqp_csv_row_missing_required_value_fails_informatively(tmp_path) -> None:
    client = RecordingClient("MonitoringLocationIdentifier,CharacteristicName\nUSGS-1,\n")
    adapter = WqpAdapter(client=client, cache=DuckDbCache(tmp_path / "wqp-cache.duckdb"))

    with pytest.raises(UpstreamServiceError, match="without a monitoring-location identifier"):
        await adapter.measurements(valid_query())
