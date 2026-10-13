from watershed_evidence_mcp.demo import DemoSelection, render_evidence_packet


def test_render_evidence_packet_keeps_evidence_types_and_query_links_visible() -> None:
    selection = DemoSelection(
        reachcode="05090202002563",
        nhdplusid="25243915",
        bounding_box={"west": -84.32, "south": 39.15, "east": -84.27, "north": 39.2},
        station_id="USGS-03245500",
    )
    resolution = {
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
        "provenance": {"query_url": "https://example.test/resolve"},
    }
    coverage = {
        "evidence_type": "coverage_summary",
        "feature_count": 11,
        "provenance": {"query_url": "https://example.test/coverage"},
    }
    stations = {
        "evidence_type": "station_inventory",
        "feature_count": 29,
        "provenance": {"query_url": "https://example.test/stations"},
    }
    observations = {
        "evidence_type": "observation",
        "returned_records": 2,
        "truncated": False,
        "records": [
            {"activity_date": "2023-01-23", "value": "626", "unit": "uS/cm @25C"},
            {"activity_date": "2023-02-17", "value": "419", "unit": "uS/cm @25C"},
        ],
        "provenance": {"query_url": "https://example.test/observations"},
    }
    baseline = {
        "evidence_type": "screening_baseline",
        "records": [{"COMID": 25243915, "StreamName": "Little Miami River", "AvgPredEC": 242.58}],
        "provenance": {"query_url": "https://example.test/baseline"},
    }

    packet = render_evidence_packet(
        selection, resolution, coverage, stations, observations, baseline
    )

    assert "## Scope selection (not evidence)" in packet
    assert "**Coverage summary**" in packet
    assert "**Observation**" in packet
    assert "**Screening baseline**" in packet
    assert "https://example.test/resolve" in packet
    assert "https://example.test/coverage" in packet
    assert "https://example.test/stations" in packet
    assert "https://example.test/observations" in packet
    assert "https://example.test/baseline" in packet
    assert "Screening comparison only — not a regulatory determination." in packet
    assert "candidate and scope were selected explicitly" in packet


def test_render_evidence_packet_refuses_unselected_or_missing_candidate() -> None:
    selection = DemoSelection(
        reachcode="05090202002563",
        nhdplusid="25243915",
        bounding_box={"west": -84.32, "south": 39.15, "east": -84.27, "north": 39.2},
        station_id="USGS-03245500",
    )

    try:
        render_evidence_packet(selection, {"candidates": []}, {}, {}, {}, {})
    except ValueError as error:
        assert "was not returned" in str(error)
    else:
        raise AssertionError("expected a selected-candidate validation error")
