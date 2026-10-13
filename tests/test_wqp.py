from datetime import date

import pytest

from watershed_evidence_mcp.adapters.wqp import WqpAdapter, normalize_result_row
from watershed_evidence_mcp.models import BoundingBox, QueryScope, WqpQuery


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


def test_scope_rejects_unbounded_result_query() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        QueryScope()


def test_normalization_preserves_interpretation_fields() -> None:
    row = {
        "OrganizationIdentifier": "USGS-OH",
        "MonitoringLocationIdentifier": "USGS-03240000",
        "ActivityStartDate": "2024-01-01",
        "CharacteristicName": "Specific conductance",
        "ResultMeasureValue": "485",
        "ResultMeasure/MeasureUnitCode": "uS/cm",
        "ResultValueTypeName": "Actual",
        "ResultDetectionConditionText": "Present Above Quantification Limit",
        "DetectionQuantitationLimitMeasure/MeasureValue": "1",
        "DetectionQuantitationLimitMeasure/MeasureUnitCode": "uS/cm",
        "AnalyticalMethod/MethodIdentifier": "2510 B",
        "LaboratoryName": "Example Laboratory",
    }

    normalized = normalize_result_row(row)

    assert normalized["station_id"] == "USGS-03240000"
    assert normalized["value"] == "485"
    assert normalized["unit"] == "uS/cm"
    assert normalized["qualifier"] == "Present Above Quantification Limit"
    assert normalized["method_identifier"] == "2510 B"
