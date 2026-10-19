from datetime import date

import httpx
import pytest

from watershed_evidence_mcp.adapters.wqp import WqpAdapter, normalize_result_row
from watershed_evidence_mcp.http import JsonHttpClient, UpstreamServiceError
from watershed_evidence_mcp.models import BoundingBox, QueryScope, WqpQuery
from watershed_evidence_mcp.tools.wqp import wqp_vocab_search


def valid_query() -> WqpQuery:
    return WqpQuery(
        scope=QueryScope(bounding_box=BoundingBox(west=-84.0, south=39.0, east=-83.9, north=39.1)),
        characteristic_names=["Specific conductance"],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )


def test_result_parameters_are_bounded_and_preserve_exact_characteristic() -> None:
    params = WqpAdapter.result_parameters(valid_query())

    assert params["bBox"] == "-84.0,39.0,-83.9,39.1"
    assert params["characteristicName"] == "Specific conductance"
    assert params["startDateLo"] == "01-01-2024"
    assert params["startDateHi"] == "12-31-2024"
    assert params["sampleMedia"] == "Water"
    assert params["mimeType"] == "csv"
    assert params["resultLimit"] == "1000"


@pytest.mark.asyncio
async def test_vocabulary_search_uses_live_case_sensitive_endpoint_and_preserves_query_url() -> (
    None
):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"codes": [{"value": "Specific conductance"}], "recordCount": 1},
            request=request,
        )

    adapter = WqpAdapter(client=JsonHttpClient(transport=httpx.MockTransport(handler)))

    payload, query_url = await adapter.vocabulary_search(
        "CharacteristicName", "Specific conductance", page_size=5, page_number=2
    )

    assert payload["codes"] == [{"value": "Specific conductance"}]
    assert query_url == (
        "https://www.waterqualitydata.us/Codes/characteristicname?"
        "text=Specific+conductance&pagesize=5&pagenumber=2&mimeType=json"
    )
    assert len(requests) == 1
    assert str(requests[0].url) == query_url


@pytest.mark.asyncio
async def test_vocabulary_search_names_wqp_and_the_requested_vocabulary_on_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    adapter = WqpAdapter(client=JsonHttpClient(transport=httpx.MockTransport(handler)))

    with pytest.raises(
        UpstreamServiceError,
        match=r"WQP controlled-vocabulary search failed for CharacteristicName:.*HTTP 503",
    ):
        await adapter.vocabulary_search(
            "CharacteristicName", "Specific conductance", page_size=5, page_number=1
        )


@pytest.mark.asyncio
async def test_vocabulary_search_rejects_invalid_text_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected_request(*args: object, **kwargs: object) -> tuple[dict, str]:
        raise AssertionError("vocabulary search must reject invalid text before an HTTP request")

    monkeypatch.setattr(WqpAdapter, "vocabulary_search", unexpected_request)

    for text in ("", "   ", "x" * 201, " " * 10_000 + "x"):
        with pytest.raises(
            ValueError, match="text must be nonblank and no longer than 200 characters"
        ):
            await wqp_vocab_search("CharacteristicName", text)


def test_scope_rejects_unbounded_result_query() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        QueryScope()


def test_scope_rejects_empty_station_selection() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        QueryScope(station_ids=[])


def test_normalization_preserves_interpretation_fields() -> None:
    row = {
        "OrganizationIdentifier": "USGS-OH",
        "MonitoringLocationIdentifier": "USGS-03240000",
        "ActivityStartDate": "2024-01-01",
        "CharacteristicName": "Specific conductance",
        "ResultMeasureValue": "485",
        "ResultMeasure/MeasureUnitCode": "uS/cm",
        "ResultValueTypeName": "Actual",
        "MeasureQualifierCode": "<",
        "ResultDetectionConditionText": "Present Above Quantification Limit",
        "DetectionQuantitationLimitMeasure/MeasureValue": "1",
        "DetectionQuantitationLimitMeasure/MeasureUnitCode": "uS/cm",
        "ResultAnalyticalMethod/MethodIdentifier": "2510 B",
        "LaboratoryName": "Example Laboratory",
    }

    normalized = normalize_result_row(row)

    assert normalized["station_id"] == "USGS-03240000"
    assert normalized["value"] == "485"
    assert normalized["unit"] == "uS/cm"
    assert normalized["qualifier"] == "<"
    assert normalized["detection_condition"] == "Present Above Quantification Limit"
    assert normalized["method_identifier"] == "2510 B"
