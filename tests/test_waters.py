from watershed_evidence_mcp.adapters.waters import feature_to_candidate


def test_geoviewer_feature_becomes_a_candidate_without_inventing_precision() -> None:
    feature = {
        "attributes": {
            "GNIS_NAME": "Little Miami River",
            "REACHCODE": "05090202000010",
            "NHDPLUSID": 123456789,
            "STATE": "OH",
        },
        "geometry": {
            "paths": [[[-84.1, 39.0], [-84.0, 39.1]]],
        },
    }

    candidate = feature_to_candidate(feature)

    assert candidate.name == "Little Miami River"
    assert candidate.reachcode == "05090202000010"
    assert candidate.nhdplusid == "123456789"
    assert candidate.state == "OH"
    assert candidate.bounding_box.west == -84.1
    assert candidate.bounding_box.north == 39.1
