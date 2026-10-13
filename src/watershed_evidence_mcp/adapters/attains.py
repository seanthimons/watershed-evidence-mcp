"""EPA ATTAINS assessment-context adapter with explicit API-key handling."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlencode

from watershed_evidence_mcp.http import JsonHttpClient
from watershed_evidence_mcp.models import AssessmentContextQuery

ATTAINS_BASE_URL = "https://api.epa.gov/attains"
ASSESSMENTS_URL = f"{ATTAINS_BASE_URL}/assessments"
HUC12_SUMMARY_URL = f"{ATTAINS_BASE_URL}/huc12summary"
MAX_HUC_ASSESSMENT_UNITS = 50


class AttainsConfigurationError(ValueError):
    """ATTAINS cannot be called safely with the current local configuration."""


def _items(value: object) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _first(mapping: dict, *keys: str) -> object | None:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _string(value: object | None) -> str | None:
    return str(value) if value is not None else None


def _normalize_use(use: dict) -> dict:
    return {
        "name": _string(_first(use, "useName", "designatedUseName", "name")),
        "support_code": _string(_first(use, "useAttainmentCode", "useSupport", "status")),
        "support_status": _string(_first(use, "useAttainmentCodeName", "supportStatusName")),
        "threatened": _string(_first(use, "threatenedIndicator")),
    }


def _normalize_parameter(parameter: dict) -> dict:
    associated_uses = _items(parameter.get("associatedUses"))
    return {
        "name": _string(_first(parameter, "parameterName", "name")),
        "status": _string(_first(parameter, "parameterStatusName", "parameterStatus", "status")),
        "pollutant_indicator": _string(
            _first(parameter, "pollutantIndicator", "pollutantInd", "isPollutant")
        ),
        "associated_uses": [
            {
                "name": _string(_first(use, "associatedUseName", "useName")),
                "attainment": _string(
                    _first(use, "parameterAttainmentCode", "parameterAttainment")
                ),
            }
            for use in associated_uses
        ],
        "associated_action_ids": [
            identifier
            for action in _items(parameter.get("associatedActions"))
            if (identifier := _string(_first(action, "associatedActionIdentifier"))) is not None
        ],
    }


def normalize_assessment(assessment: dict, report: dict) -> dict:
    """Reduce an ATTAINS assessment plus its report envelope to reporting context only."""
    assessment_unit_id = _string(_first(assessment, "assessmentUnitIdentifier", "assessmentUnitId"))
    organization_id = _string(_first(report, "organizationIdentifier", "organizationId"))
    source_identifiers = {"assessment_unit_id": assessment_unit_id}
    if organization_id is not None:
        source_identifiers["organization_id"] = organization_id

    return {
        "assessment_unit_id": assessment_unit_id,
        "reporting_cycle": _string(_first(report, "reportingCycleText", "reportingCycle")),
        "report_status": _string(_first(report, "reportStatusCode")),
        "assessment_status": _string(_first(assessment, "overallStatus", "assessmentStatus")),
        "epa_ir_category": _string(_first(assessment, "epaIRCategory", "epaIrCategory")),
        "designated_uses": [
            _normalize_use(use) for use in _items(assessment.get("useAttainments"))
        ],
        "parameter_context": [
            _normalize_parameter(parameter) for parameter in _items(assessment.get("parameters"))
        ],
        "probable_sources": [
            {
                "name": _string(_first(source, "sourceName")),
                "confirmed": _string(_first(source, "sourceConfirmedIndicator")),
            }
            for source in _items(assessment.get("probableSources"))
        ],
        "source_identifiers": source_identifiers,
    }


@dataclass(frozen=True)
class AssessmentContextResult:
    records: list[dict]
    assessment_query_url: str
    resolution_query_url: str | None = None


class AttainsAdapter:
    """Retrieve read-only ATTAINS reporting context without causal interpretation."""

    def __init__(self, client: JsonHttpClient | None = None, api_key: str | None = None) -> None:
        self.client = client or JsonHttpClient()
        self.api_key = api_key if api_key is not None else os.getenv("ATTAINS_API_KEY")

    def _require_api_key(self) -> str:
        if not self.api_key:
            raise AttainsConfigurationError(
                "ATTAINS_API_KEY is required for EPA ATTAINS. Obtain a free Data.gov key at "
                "https://api.data.gov/signup/ and provide it through the environment."
            )
        return self.api_key

    @staticmethod
    def _public_query_url(url: str, params: dict[str, str]) -> str:
        return (
            f"{url}?{urlencode({key: value for key, value in params.items() if key != 'api_key'})}"
        )

    async def _get_assessments(
        self, assessment_unit_ids: list[str], reporting_cycle: str | None
    ) -> tuple[list[dict], str]:
        params = {
            "assessmentUnitIdentifier": ",".join(assessment_unit_ids),
        }
        if reporting_cycle is not None:
            params["reportingCycle"] = reporting_cycle
        payload = await self.client.get_json(
            ASSESSMENTS_URL,
            params,
            headers={"X-Api-Key": self._require_api_key()},
        )
        records = [
            normalize_assessment(assessment, report)
            for report in _items(payload.get("items"))
            for assessment in _items(report.get("assessments"))
        ]
        return records, self._public_query_url(ASSESSMENTS_URL, params)

    async def assessment_context(self, query: AssessmentContextQuery) -> AssessmentContextResult:
        """Return current or requested-cycle assessment context for an exact selector."""
        if query.assessment_unit_id is not None:
            records, assessment_query_url = await self._get_assessments(
                [query.assessment_unit_id], query.reporting_cycle
            )
            return AssessmentContextResult(records, assessment_query_url)

        huc_params = {"huc": query.huc12 or ""}
        huc_payload = await self.client.get_json(
            HUC12_SUMMARY_URL,
            huc_params,
            headers={"X-Api-Key": self._require_api_key()},
        )
        assessment_summaries = _items(huc_payload.get("items"))
        resolution_query_url = self._public_query_url(HUC12_SUMMARY_URL, huc_params)
        if not assessment_summaries:
            return AssessmentContextResult([], resolution_query_url, resolution_query_url)
        if len(assessment_summaries) != 1:
            raise ValueError("ATTAINS returned an unexpected HUC12 summary shape")
        assessment_unit_ids = [
            _string(_first(unit, "assessmentUnitId", "assessmentUnitIdentifier"))
            for unit in _items(assessment_summaries[0].get("assessmentUnits"))
        ]
        assessment_unit_ids = [
            identifier for identifier in assessment_unit_ids if identifier is not None
        ]
        if not assessment_unit_ids:
            return AssessmentContextResult([], resolution_query_url, resolution_query_url)
        if len(assessment_unit_ids) > MAX_HUC_ASSESSMENT_UNITS:
            raise ValueError(
                "HUC12 resolves to more than 50 assessment units; select an assessment_unit_id "
                "instead"
            )
        records, assessment_query_url = await self._get_assessments(
            assessment_unit_ids, query.reporting_cycle
        )
        return AssessmentContextResult(
            records,
            assessment_query_url,
            self._public_query_url(HUC12_SUMMARY_URL, huc_params),
        )
