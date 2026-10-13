import httpx
import pytest
from pydantic import ValidationError

from watershed_evidence_mcp.adapters.attains import (
    AttainsAdapter,
    AttainsConfigurationError,
    normalize_assessment,
)
from watershed_evidence_mcp.http import JsonHttpClient
from watershed_evidence_mcp.models import AssessmentContextQuery


def test_normalization_keeps_assessment_reporting_context_separate_from_causation() -> None:
    report = {
        "organizationIdentifier": "DOEE",
        "reportingCycleText": "2024",
        "reportStatusCode": "EPA Final Action",
    }
    assessment = {
        "assessmentUnitIdentifier": "DCTFD01R_00",
        "overallStatus": "Not Supporting",
        "epaIRCategory": "4A",
        "useAttainments": [
            {
                "useName": "Primary Contact Recreation",
                "useAttainmentCode": "N",
                "useAttainmentCodeName": "Not Supporting",
                "threatenedIndicator": "N",
            }
        ],
        "parameters": [
            {
                "parameterName": "ESCHERICHIA COLI (E. COLI)",
                "parameterStatusName": "Cause",
                "pollutantIndicator": "Y",
                "associatedUses": [
                    {
                        "associatedUseName": "Primary Contact Recreation",
                        "parameterAttainmentCode": "Not meeting criteria",
                    }
                ],
                "associatedActions": [
                    {"associatedActionIdentifier": "DC_2003_2014_Anacostia_and_Tribs_Bacteria"}
                ],
            }
        ],
        "probableSources": [
            {"sourceName": "UNSPECIFIED URBAN STORMWATER", "sourceConfirmedIndicator": "N"}
        ],
    }

    normalized = normalize_assessment(assessment, report)

    assert normalized["assessment_unit_id"] == "DCTFD01R_00"
    assert normalized["reporting_cycle"] == "2024"
    assert normalized["report_status"] == "EPA Final Action"
    assert normalized["assessment_status"] == "Not Supporting"
    assert normalized["epa_ir_category"] == "4A"
    assert normalized["designated_uses"] == [
        {
            "name": "Primary Contact Recreation",
            "support_code": "N",
            "support_status": "Not Supporting",
            "threatened": "N",
        }
    ]
    assert normalized["parameter_context"] == [
        {
            "name": "ESCHERICHIA COLI (E. COLI)",
            "status": "Cause",
            "pollutant_indicator": "Y",
            "associated_uses": [
                {"name": "Primary Contact Recreation", "attainment": "Not meeting criteria"}
            ],
            "associated_action_ids": ["DC_2003_2014_Anacostia_and_Tribs_Bacteria"],
        }
    ]
    assert normalized["probable_sources"] == [
        {"name": "UNSPECIFIED URBAN STORMWATER", "confirmed": "N"}
    ]
    assert normalized["source_identifiers"] == {
        "assessment_unit_id": "DCTFD01R_00",
        "organization_id": "DOEE",
    }


@pytest.mark.asyncio
async def test_assessment_query_flattens_the_documented_report_envelope() -> None:
    payload = {
        "count": 1,
        "items": [
            {
                "organizationIdentifier": "DOEE",
                "reportingCycleText": "2024",
                "reportStatusCode": "EPA Final Action",
                "assessments": [
                    {
                        "assessmentUnitIdentifier": "DCTFD01R_00",
                        "overallStatus": "Not Supporting",
                        "epaIRCategory": "4A",
                        "useAttainments": [],
                        "parameters": [],
                        "probableSources": [],
                    }
                ],
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/assessmentUnits"):
            return httpx.Response(
                200,
                json={
                    "count": 1,
                    "items": [
                        {
                            "organizationIdentifier": "DOEE",
                            "assessmentUnits": [{"assessmentUnitIdentifier": "DCTFD01R_00"}],
                        }
                    ],
                },
            )
        return httpx.Response(200, json=payload)

    adapter = AttainsAdapter(
        api_key="not-embedded",
        client=JsonHttpClient(transport=httpx.MockTransport(handler)),
    )
    result = await adapter.assessment_context(
        AssessmentContextQuery(assessment_unit_id="DCTFD01R_00", reporting_cycle="2024")
    )

    assert result.records == [
        {
            "assessment_unit_id": "DCTFD01R_00",
            "reporting_cycle": "2024",
            "report_status": "EPA Final Action",
            "assessment_status": "Not Supporting",
            "epa_ir_category": "4A",
            "designated_uses": [],
            "parameter_context": [],
            "probable_sources": [],
            "source_identifiers": {
                "assessment_unit_id": "DCTFD01R_00",
                "organization_id": "DOEE",
            },
        }
    ]


@pytest.mark.asyncio
async def test_assessment_query_returns_clean_no_result_with_a_redacted_query_url() -> None:
    def no_result_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Api-Key"] == "not-embedded"
        assert "api_key" not in request.url.params
        return httpx.Response(200, json={"count": 0, "items": []})

    adapter = AttainsAdapter(
        api_key="not-embedded",
        client=JsonHttpClient(transport=httpx.MockTransport(no_result_handler)),
    )

    result = await adapter.assessment_context(
        AssessmentContextQuery(assessment_unit_id="OH-05090202-001")
    )

    assert result.records == []
    assert "api_key" not in result.assessment_query_url
    assert "assessmentUnitIdentifier=OH-05090202-001" in result.assessment_query_url


@pytest.mark.asyncio
async def test_missing_api_key_fails_before_any_request() -> None:
    def unexpected_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request: {request.url}")

    adapter = AttainsAdapter(
        api_key="",
        client=JsonHttpClient(transport=httpx.MockTransport(unexpected_request)),
    )

    with pytest.raises(AttainsConfigurationError, match="ATTAINS_API_KEY"):
        await adapter.assessment_context(
            AssessmentContextQuery(assessment_unit_id="OH-05090202-001")
        )


def test_assessment_context_requires_one_valid_identifier() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        AssessmentContextQuery()

    with pytest.raises(ValidationError, match="pattern"):
        AssessmentContextQuery(huc12="05090202")

    with pytest.raises(ValidationError, match="invalid assessment_unit_id"):
        AssessmentContextQuery(assessment_unit_id="not an ATTAINS identifier")


@pytest.mark.asyncio
async def test_huc12_resolution_forwards_ids_cycle_and_resolution_provenance() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/huc12summary"):
            return httpx.Response(
                200,
                json={
                    "count": 1,
                    "items": [
                        {
                            "assessmentUnits": [
                                {"assessmentUnitId": "DCTFD01R_00"},
                                {"assessmentUnitId": "DCTNA01R_00"},
                            ]
                        }
                    ],
                },
            )
        if request.url.path.endswith("/assessmentUnits"):
            return httpx.Response(
                200,
                json={
                    "count": 1,
                    "items": [
                        {
                            "organizationIdentifier": "DOEE",
                            "assessmentUnits": [
                                {"assessmentUnitIdentifier": "DCTFD01R_00"},
                                {"assessmentUnitIdentifier": "DCTNA01R_00"},
                            ],
                        }
                    ],
                },
            )
        return httpx.Response(200, json={"count": 0, "items": []})

    adapter = AttainsAdapter(
        api_key="not-embedded",
        client=JsonHttpClient(transport=httpx.MockTransport(handler)),
    )
    result = await adapter.assessment_context(
        AssessmentContextQuery(huc12="020700100204", reporting_cycle="2024")
    )

    assert result.records == []
    assert result.resolution_query_url == (
        "https://api.epa.gov/attains/huc12summary?huc=020700100204"
    )
    assert len(requests) == 3
    assert requests[1].url.path.endswith("/assessmentUnits")
    assert requests[2].url.params["organizationId"] == "DOEE"
    assert "state" not in requests[2].url.params
    assert requests[2].url.params["assessmentUnitIdentifier"] == "DCTFD01R_00,DCTNA01R_00"
    assert requests[2].url.params["reportingCycle"] == "2024"


@pytest.mark.asyncio
async def test_assessment_query_resolves_authoritative_organization_before_retrieval() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/assessmentUnits"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "organizationIdentifier": "NAVAJO",
                            "assessmentUnits": [{"assessmentUnitIdentifier": "ZZ-TRIBAL-001"}],
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"count": 0, "items": []})

    adapter = AttainsAdapter(
        api_key="not-embedded",
        client=JsonHttpClient(transport=httpx.MockTransport(handler)),
    )
    await adapter.assessment_context(AssessmentContextQuery(assessment_unit_id="ZZ-TRIBAL-001"))

    assert len(requests) == 2
    assert requests[1].url.params["organizationId"] == "NAVAJO"
    assert "state" not in requests[1].url.params


@pytest.mark.asyncio
async def test_huc12_resolution_handles_multiple_authoritative_organizations() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/huc12summary"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "assessmentUnits": [
                                {"assessmentUnitId": "DC-001"},
                                {"assessmentUnitId": "MD-001"},
                            ]
                        }
                    ]
                },
            )
        if request.url.path.endswith("/assessmentUnits"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "organizationIdentifier": "DOEE",
                            "assessmentUnits": [{"assessmentUnitIdentifier": "DC-001"}],
                        },
                        {
                            "organizationIdentifier": "MDE",
                            "assessmentUnits": [{"assessmentUnitIdentifier": "MD-001"}],
                        },
                    ]
                },
            )
        return httpx.Response(200, json={"count": 0, "items": []})

    adapter = AttainsAdapter(
        api_key="not-embedded",
        client=JsonHttpClient(transport=httpx.MockTransport(handler)),
    )
    result = await adapter.assessment_context(AssessmentContextQuery(huc12="020700100204"))

    assert result.records == []
    assert len(result.assessment_query_urls) == 2
    assert [request.url.params["organizationId"] for request in requests[2:]] == ["DOEE", "MDE"]


@pytest.mark.asyncio
async def test_empty_huc12_summary_returns_no_result_without_an_assessments_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"count": 0, "items": []})

    adapter = AttainsAdapter(
        api_key="not-embedded",
        client=JsonHttpClient(transport=httpx.MockTransport(handler)),
    )
    result = await adapter.assessment_context(AssessmentContextQuery(huc12="020700100204"))

    assert result.records == []
    assert result.assessment_query_url == result.resolution_query_url
    assert len(requests) == 1
    assert requests[0].url.path.endswith("/huc12summary")


@pytest.mark.asyncio
async def test_huc12_resolution_rejects_more_than_fifty_assessment_units() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "count": 1,
                "items": [
                    {
                        "assessmentUnits": [
                            {"assessmentUnitId": f"DC-{number:03d}"} for number in range(51)
                        ]
                    }
                ],
            },
        )

    adapter = AttainsAdapter(
        api_key="not-embedded",
        client=JsonHttpClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ValueError, match="more than 50"):
        await adapter.assessment_context(AssessmentContextQuery(huc12="020700100204"))
