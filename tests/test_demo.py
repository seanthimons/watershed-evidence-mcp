import pytest

from watershed_evidence_mcp.demo import (
    DemoSelection,
    render_evidence_packet,
    validate_selected_candidate,
)


def selection() -> DemoSelection:
    return DemoSelection(
        reachcode="05090202002563",
        nhdplusid="25243915",
        bounding_box={"west": -84.32, "south": 39.15, "east": -84.27, "north": 39.2},
        station_id="USGS-03245500",
    )


def provenance(url: str) -> dict[str, str]:
    return {
        "source": "Example source",
        "source_version": "Example version",
        "retrieved_at": "2026-10-13T21:00:00Z",
        "query_url": url,
        "caveat": "Example source-specific caveat.",
    }


def resolution() -> dict:
    return {
        "candidates": [
            {
                "name": "Little Miami River",
                "reachcode": "05090202002563",
                "nhdplusid": "25243915",
                "bounding_box": {
                    "west": -84.299,
                    "south": 39.165,
                    "east": -84.297,
                    "north": 39.166,
                },
            }
        ],
        "ambiguity_warning": (
            "Select a candidate and supply an explicit spatial scope before querying WQP."
        ),
        "provenance": provenance("https://example.test/resolve"),
    }


def test_render_evidence_packet_preserves_observation_metadata_and_provenance() -> None:
    coverage = {
        "evidence_type": "coverage_summary",
        "feature_count": 11,
        "provenance": provenance("https://example.test/coverage"),
    }
    stations = {
        "evidence_type": "station_inventory",
        "feature_count": 29,
        "provenance": provenance("https://example.test/stations"),
    }
    observations = {
        "evidence_type": "observation",
        "returned_records": 2,
        "truncated": False,
        "records": [
            {
                "station_id": "USGS-03245500",
                "activity_date": "2023-01-23",
                "activity_time": "10:44:00",
                "value": "626",
                "unit": "uS/cm @25C",
                "value_type": "Actual",
                "qualifier": None,
                "detection_limit_value": "1",
                "detection_limit_unit": "uS/cm @25C",
                "method_identifier": "2510 B",
                "laboratory_name": "Example Lab",
            },
            {
                "station_id": "USGS-03245500",
                "activity_date": "2023-02-17",
                "activity_time": "07:54:00",
                "value": "419",
                "unit": "uS/cm @25C",
                "value_type": "Actual",
                "qualifier": None,
                "detection_limit_value": "1",
                "detection_limit_unit": "uS/cm @25C",
                "method_identifier": "2510 B",
                "laboratory_name": "Example Lab",
            },
        ],
        "provenance": provenance("https://example.test/observations"),
    }
    baseline = {
        "evidence_type": "screening_baseline",
        "records": [{"COMID": 25243915, "StreamName": "Little Miami River", "AvgPredEC": 242.58}],
        "provenance": provenance("https://example.test/baseline"),
    }

    packet = render_evidence_packet(
        selection(), resolution(), coverage, stations, observations, baseline
    )

    assert "## Scope selection (not evidence)" in packet
    assert "**Coverage summary**" in packet
    assert "### Observation" in packet
    assert "**Screening baseline**" in packet
    assert "**Assessment context — not retrieved**" in packet
    assert "Comparable bounded-observation range: 419–626 uS/cm @25C" in packet
    assert "USGS-03245500" in packet
    assert "2510 B" in packet
    assert "Example Lab" in packet
    assert "Detection limit" in packet
    for url in [
        "https://example.test/resolve",
        "https://example.test/coverage",
        "https://example.test/stations",
        "https://example.test/observations",
        "https://example.test/baseline",
    ]:
        assert url in packet
    assert "Source: Example source (Example version)" in packet
    assert "Retrieved: 2026-10-13T21:00:00Z" in packet
    assert "Caveat: Example source-specific caveat." in packet
    assert "Screening comparison only — not a regulatory determination." in packet
    assert "candidate and scope were selected explicitly" in packet


def test_render_evidence_packet_declines_range_for_mixed_units_or_qualifiers() -> None:
    observations = {
        "evidence_type": "observation",
        "returned_records": 2,
        "truncated": False,
        "records": [
            {"value": "626", "unit": "uS/cm @25C", "qualifier": None, "value_type": "Actual"},
            {"value": "419", "unit": "mS/cm", "qualifier": "<", "value_type": "Actual"},
        ],
        "provenance": provenance("https://example.test/observations"),
    }
    coverage = {
        "evidence_type": "coverage_summary",
        "provenance": provenance("https://example.test/c"),
    }
    stations = {
        "evidence_type": "station_inventory",
        "provenance": provenance("https://example.test/s"),
    }
    baseline = {
        "evidence_type": "screening_baseline",
        "records": [],
        "provenance": provenance("https://example.test/b"),
    }

    packet = render_evidence_packet(
        selection(), resolution(), coverage, stations, observations, baseline
    )

    assert "No comparable numeric range is displayed" in packet
    assert "626 | uS/cm @25C" in packet
    assert "419 | mS/cm" in packet


def test_validate_selected_candidate_fails_before_retrieval_when_selection_is_absent() -> None:
    with pytest.raises(ValueError, match="was not returned"):
        validate_selected_candidate(selection(), {"candidates": []})
