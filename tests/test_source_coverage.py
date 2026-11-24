"""HUC8 from reachcode, Freshwater layer selection, WQP evidence fields, and WQX 3 retrieval."""

from datetime import date

import httpx
import pytest

from watershed_evidence_mcp.adapters.freshwater import FreshwaterAdapter
from watershed_evidence_mcp.adapters.waters import feature_to_candidate
from watershed_evidence_mcp.adapters.wqp import WqpAdapter, normalize_result_row
from watershed_evidence_mcp.cache import DuckDbCache
from watershed_evidence_mcp.http import JsonHttpClient, UpstreamServiceError
from watershed_evidence_mcp.models import BoundingBox, QueryScope, WqpQuery
from watershed_evidence_mcp.provenance import FRESHWATER_CRITERIA_CAVEAT
from watershed_evidence_mcp.tools import freshwater as freshwater_tool

BOX = BoundingBox(west=-84.4, south=39.1, east=-84.2, north=39.3)


@pytest.mark.parametrize(
    ("reachcode", "huc8"),
    [("05090202002563", "05090202"), (None, None), ("0509020200", None), ("0509020200256X", None)],
)
def test_huc8_is_derived_only_from_a_14_digit_reachcode(reachcode, huc8) -> None:
    attributes = {"gnis_name": "Little Miami River"}
    if reachcode is not None:
        attributes["reachcode"] = reachcode
    assert feature_to_candidate({"attributes": attributes}).huc8 == huc8


@pytest.mark.asyncio
async def test_station_criteria_layer_returns_points_keyed_by_station_with_criteria_caveat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []
    payload = {
        "features": [
            {
                "attributes": {"Station": "21KY-LRW001", "Acute5": 988.1},
                "geometry": {"x": -84.49, "y": 39.06},
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload, request=request)

    client = JsonHttpClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(freshwater_tool, "FreshwaterAdapter", lambda: FreshwaterAdapter(client))

    response = await freshwater_tool.freshwater_screening_baseline(
        BOX, max_records=5, layer="station_aluminum_criteria"
    )

    assert "Aquatic_Life_Criteria_for_Aluminum_by_Station" in str(requests[0].url)
    feature = response["feature_collection"]["features"][0]
    assert feature["id"] == "21KY-LRW001"
    assert feature["geometry"] == {"type": "Point", "coordinates": [-84.49, 39.06]}
    assert response["layer"] == "station_aluminum_criteria"
    assert response["provenance"]["caveat"] == FRESHWATER_CRITERIA_CAVEAT
    assert response["screening_only"] is True


def test_wqx2_normalization_keeps_fraction_status_activity_type_and_pcode() -> None:
    normalized = normalize_result_row(
        {
            "MonitoringLocationIdentifier": "USGS-03245500",
            "CharacteristicName": "Specific conductance",
            "ResultSampleFractionText": "Total",
            "ResultStatusIdentifier": "Accepted",
            "ActivityTypeCode": "Sample-Routine",
            "USGSPCode": "90095",
            "ProviderName": "NWIS",
            "DetectionQuantitationLimitTypeName": "Lower Reporting Limit",
        }
    )
    assert normalized["sample_fraction"] == "Total"
    assert normalized["result_status"] == "Accepted"
    assert normalized["activity_type"] == "Sample-Routine"
    assert normalized["usgs_pcode"] == "90095"
    assert normalized["provider_name"] == "NWIS"
    assert normalized["detection_limit_type"] == "Lower Reporting Limit"
    assert normalized["detection_limit_b_value"] is None


WQX3_CSV = (
    "Org_Identifier,Location_Identifier,Activity_StartDate,Activity_TypeCode,"
    "Result_Characteristic,Result_SampleFraction,Result_Measure,Result_MeasureUnit,"
    "Result_MeasureStatusIdentifier,DetectionLimit_TypeA,DetectionLimit_MeasureA,"
    "DetectionLimit_MeasureUnitA,DetectionLimit_TypeB,DetectionLimit_MeasureB,"
    "DetectionLimit_MeasureUnitB,USGSpcode,ProviderName\n"
    "USGS,USGS-03245500,2024-01-10,Sample-Routine,Specific conductance,Unfiltered,411,uS/cm,"
    "Accepted,,,,Lower Reporting Limit,1,uS/cm,90095,USGS\n"
)


def wqx3_query(**update) -> WqpQuery:
    return WqpQuery(
        scope=QueryScope(station_ids=["USGS-03245500"]),
        characteristic_names=["Specific conductance"],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        **update,
    )


def wqx3_adapter(tmp_path, body: str, requests: list[httpx.Request]) -> WqpAdapter:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200, text=body, headers={"content-type": "text/plain"}, request=request
        )

    return WqpAdapter(
        client=JsonHttpClient(transport=httpx.MockTransport(handler)),
        cache=DuckDbCache(tmp_path / "c.duckdb"),
    )


@pytest.mark.asyncio
async def test_wqx3_uses_wqx3_endpoint_and_preserves_both_detection_limits(tmp_path) -> None:
    requests: list[httpx.Request] = []
    result = await wqx3_adapter(tmp_path, WQX3_CSV, requests).measurements(wqx3_query())

    assert str(requests[0].url).startswith("https://www.waterqualitydata.us/wqx3/Result/search?")
    assert requests[0].url.params["dataProfile"] == "basicPhysChem"
    assert result.query_url == str(requests[0].url)
    assert result.source_version.startswith("WQX 3")
    record = result.records[0]
    assert record["station_id"] == "USGS-03245500"
    assert record["value"] == "411"
    assert record["sample_fraction"] == "Unfiltered"
    assert record["result_status"] == "Accepted"
    assert record["detection_limit_value"] is None
    assert record["detection_limit_b_type"] == "Lower Reporting Limit"
    assert record["detection_limit_b_value"] == "1"
    assert record["usgs_pcode"] == "90095"


def test_wqx3_is_the_default_mode() -> None:
    assert wqx3_query().compatibility_mode == "wqx3"


@pytest.mark.asyncio
async def test_wqx3_rejects_rows_missing_identifier(tmp_path) -> None:
    body = "Location_Identifier,Result_Characteristic\n,Specific conductance\n"
    with pytest.raises(UpstreamServiceError, match="monitoring-location identifier"):
        await wqx3_adapter(tmp_path, body, []).measurements(wqx3_query())


@pytest.mark.asyncio
async def test_wqx2_and_wqx3_do_not_share_cache_entries(tmp_path) -> None:
    requests: list[httpx.Request] = []
    adapter = wqx3_adapter(tmp_path, WQX3_CSV, requests)
    await adapter.measurements(wqx3_query())
    with pytest.raises(UpstreamServiceError, match="required identifier"):
        await adapter.measurements(wqx3_query(compatibility_mode="wqx2"))
    assert len(requests) == 2


STATION_CSV = (
    "Org_Identifier,Location_Identifier,Location_Type,Location_HUCEightDigitCode,"
    "Location_LatitudeStandardized,Location_LongitudeStandardized\n"
    "USGS-OH,USGS-03245500,Stream,05090202,39.1717,-84.2944\n"
    "21OHIO_WQX,21OHIO_WQX-M05P11,River/Stream,05090202,,\n"
)


@pytest.mark.asyncio
async def test_monitoring_sites_reads_wqx3_station_csv_as_geojson(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from watershed_evidence_mcp.tools import wqp as wqp_tool

    requests: list[httpx.Request] = []
    adapter = wqx3_adapter(tmp_path, STATION_CSV, requests)
    monkeypatch.setattr(wqp_tool, "WqpAdapter", lambda: adapter)

    response = await wqp_tool.wqp_monitoring_sites(QueryScope(bounding_box=BOX))

    assert str(requests[0].url).startswith("https://www.waterqualitydata.us/wqx3/Station/search?")
    assert requests[0].url.params["mimeType"] == "csv"
    assert response["provenance"]["source_version"].startswith("WQX 3")
    first, second = response["features"]
    assert first["id"] == "USGS-03245500"
    assert first["geometry"] == {"type": "Point", "coordinates": [-84.2944, 39.1717]}
    assert first["properties"]["Location_HUCEightDigitCode"] == "05090202"
    assert second["geometry"] is None
    assert second["properties"]["Location_LatitudeStandardized"] is None
    assert response["records_without_geometry"] == 1


@pytest.mark.asyncio
async def test_available_data_flags_wqx2_summary_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    from watershed_evidence_mcp.tools import wqp as wqp_tool

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"features": []}, request=request)

    client = JsonHttpClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(wqp_tool, "WqpAdapter", lambda: WqpAdapter(client=client))

    response = await wqp_tool.wqp_available_data(QueryScope(bounding_box=BOX))

    assert "lower bound" in response["coverage_note"]
    assert response["provenance"]["source_version"] == "WQX 2 public web services"


@pytest.mark.asyncio
async def test_monitoring_sites_wqx2_mode_uses_legacy_geojson(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from watershed_evidence_mcp.tools import wqp as wqp_tool

    requests: list[httpx.Request] = []
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-84.29, 39.17]},
        "properties": {"MonitoringLocationIdentifier": "USGS-03245500", "resultCount": "17875"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"features": [feature]}, request=request)

    client = JsonHttpClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(wqp_tool, "WqpAdapter", lambda: WqpAdapter(client=client))

    response = await wqp_tool.wqp_monitoring_sites(
        QueryScope(bounding_box=BOX), compatibility_mode="wqx2"
    )

    assert str(requests[0].url).startswith("https://www.waterqualitydata.us/data/Station/search?")
    assert requests[0].url.params["mimeType"] == "geojson"
    assert response["compatibility_mode"] == "wqx2"
    assert response["features"] == [feature]
    assert response["provenance"]["source_version"] == "WQX 2 public web services"
