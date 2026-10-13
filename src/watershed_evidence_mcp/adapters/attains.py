"""EPA ATTAINS assessment-context adapter with explicit API-key handling."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlencode

from watershed_evidence_mcp.http import JsonHttpClient
from watershed_evidence_mcp.models import AssessmentContextQuery

ATTAINS_BASE_URL = "https://api.epa.gov/attains"
ASSESSMENTS_URL = f"{ATTAINS_BASE_URL}/assessments"
ASSESSMENT_UNITS_URL = f"{ATTAINS_BASE_URL}/assessmentUnits"
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
    assessment_query_urls: list[str]
    resolution_query_url: str | None = None

    @property
    def assessment_query_url(self) -> str:
        """Primary query URL retained for the shared provenance contract."""
        return self.assessment_query_urls[0]


@dataclass(frozen=True)
class ResolvedAssessmentUnits:
    organization_id: str
    assessment_unit_ids: list[str]


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

    async def _resolve_assessment_units(
        self, assessment_unit_ids: list[str]
    ) -> tuple[list[ResolvedAssessmentUnits], str]:
        params = {"assessmentUnitIdentifier": ",".join(assessment_unit_ids)}
        payload = await self.client.get_json(
            ASSESSMENT_UNITS_URL,
            params,
            headers={"X-Api-Key": self._require_api_key()},
        )
        requested_ids = set(assessment_unit_ids)
        resolutions = [
            ResolvedAssessmentUnits(
                organization_id=organization_id,
                assessment_unit_ids=unit_ids,
            )
            for organization in _items(payload.get("items"))
            if (organization_id := _string(_first(organization, "organizationIdentifier")))
            if (
                unit_ids := [
                    identifier
                    for unit in _items(organization.get("assessmentUnits"))
                    if (identifier := _string(_first(unit, "assessmentUnitIdentifier")))
                    in requested_ids
                ]
            )
        ]
        if sum(len(resolution.assessment_unit_ids) for resolution in resolutions) > (
            MAX_HUC_ASSESSMENT_UNITS
        ):
            raise ValueError(
                "assessment-unit resolution returned more than 50 organization/unit pairs; "
                "select one assessment_unit_id instead"
            )
        return resolutions, self._public_query_url(ASSESSMENT_UNITS_URL, params)

    async def _get_assessments(
        self,
        resolutions: list[ResolvedAssessmentUnits],
        reporting_cycle: str | None,
    ) -> tuple[list[dict], list[str]]:
        records: list[dict] = []
        query_urls: list[str] = []
        for resolution in resolutions:
            params = {
                "organizationId": resolution.organization_id,
                "assessmentUnitIdentifier": ",".join(resolution.assessment_unit_ids),
            }
            if reporting_cycle is not None:
                params["reportingCycle"] = reporting_cycle
            payload = await self.client.get_json(
                ASSESSMENTS_URL,
                params,
                headers={"X-Api-Key": self._require_api_key()},
            )
            records.extend(
                normalize_assessment(assessment, report)
                for report in _items(payload.get("items"))
                for assessment in _items(report.get("assessments"))
            )
            query_urls.append(self._public_query_url(ASSESSMENTS_URL, params))
        return records, query_urls

    async def assessment_context(self, query: AssessmentContextQuery) -> AssessmentContextResult:
        """Return current or requested-cycle assessment context for an exact selector."""
        if query.assessment_unit_id is not None:
            resolutions, resolution_query_url = await self._resolve_assessment_units(
                [query.assessment_unit_id]
            )
            if not resolutions:
                return AssessmentContextResult([], [resolution_query_url], resolution_query_url)
            records, assessment_query_urls = await self._get_assessments(
                resolutions, query.reporting_cycle
            )
            return AssessmentContextResult(records, assessment_query_urls, resolution_query_url)

        huc_params = {"huc": query.huc12 or ""}
        huc_payload = await self.client.get_json(
            HUC12_SUMMARY_URL,
            huc_params,
            headers={"X-Api-Key": self._require_api_key()},
        )
        assessment_summaries = _items(huc_payload.get("items"))
        huc_resolution_query_url = self._public_query_url(HUC12_SUMMARY_URL, huc_params)
        if not assessment_summaries:
            return AssessmentContextResult([], [huc_resolution_query_url], huc_resolution_query_url)
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
            return AssessmentContextResult([], [huc_resolution_query_url], huc_resolution_query_url)
        if len(assessment_unit_ids) > MAX_HUC_ASSESSMENT_UNITS:
            raise ValueError(
                "HUC12 resolves to more than 50 assessment units; select an assessment_unit_id "
                "instead"
            )
        resolutions, assessment_units_query_url = await self._resolve_assessment_units(
            assessment_unit_ids
        )
        if not resolutions:
            return AssessmentContextResult(
                [], [assessment_units_query_url], huc_resolution_query_url
            )
        records, assessment_query_urls = await self._get_assessments(
            resolutions, query.reporting_cycle
        )
        return AssessmentContextResult(records, assessment_query_urls, huc_resolution_query_url)
