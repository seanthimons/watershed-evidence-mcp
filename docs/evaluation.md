# Evaluation protocol and initial live results

The GSA hackathon requires submitters to document evaluation setup and results. This document defines the repeatable protocol and records the first verified public-service run.

## Scenarios

1. Valid WQP coverage lookup for a small, real bounding box.
2. Valid WQP site lookup for the same area.
3. Valid bounded result query for one documented characteristic and date range.
4. Ambiguous river-name lookup returns multiple candidates and a disambiguation warning.
5. Valid Freshwater Explorer predicted-background screening lookup.
6. Invalid: no spatial/station selector.
7. Invalid: reversed dates.
8. Invalid: result request exceeds maximum cap.
9. Upstream outage/malformed response is expressed as an actionable tool error without exposing internals.
10. Valid ATTAINS assessment-context lookup with an environment-supplied API key; output includes reporting cycle, use, status, parameter context, source identifiers, query URL, timestamp, and causal caveat.
11. Invalid: missing or malformed HUC12 / assessment-unit selector is rejected before a network call.
12. Invalid configuration: missing `ATTAINS_API_KEY` fails cleanly before a network call.

## Metrics

For each live scenario record:

- UTC time and endpoint/version
- input parameters (no secrets)
- HTTP status, result count, and wall-clock duration
- successful structured response / expected validation error
- provenance completeness: source, query URL, timestamp, and caveat all present

## ATTAINS live-verification status

On 2026-10-13, the new EPA endpoint returned the documented `API_KEY_MISSING` response without a key. A live `huc12summary` request with the EPA-documented `DEMO_KEY` returned one real HUC12 summary and 18 assessment-unit identifiers for HUC12 `020700100204`, but the `assessments` endpoint returned HTTP 429 for that shared low-rate key.

The adapter was subsequently verified end-to-end using an environment-supplied, non-committed Data.gov key. `get_assessment_context(assessment_unit_id="DCTFD01R_00", reporting_cycle="2024")` first resolved the unit to authoritative organization ID `DOEE`, then returned HTTP 200 and one normalized record: reporting cycle `2024`, report status `EPA Final Action`, assessment status `Not Supporting`, four designated uses, and six parameter-context records. This two-step resolution avoids assuming that an assessment-unit prefix is a state code. No credential value was recorded in this document, provenance, source control, or test output.

## Reproducible live evaluation

The normal test suite is intentionally offline and deterministic. It uses `httpx.MockTransport` plus small, redacted representative fixtures in `tests/fixtures/`; it does not call EPA, WQP, or any other network service.

Run the deterministic evidence suite:

```bash
uv run pytest
```

Run the explicitly opt-in live evaluation separately:

```bash
uv run python scripts/run_live_evaluation.py --output-dir evaluation-reports
```

The command performs five public, read-only, bounded requests: WATERS name resolution (five candidates), WQP summary and station lookups for one public station, WQP results with a 25-record cap, and Freshwater Explorer with a 10-record cap. It uses a temporary WQP cache so the measurement scenario always reaches the live service. It creates timestamped JSON and Markdown reports containing endpoint names, query shape, success/error outcome, record count, and wall-clock duration. The ignored `evaluation-reports/` directory prevents local reports from entering Git history. The report deliberately retains neither response bodies nor credentials; it does not call ATTAINS, because that endpoint needs a user-supplied API key.

## Security posture and limitations

- The server is read-only. It makes no submission, mutation, or credential-management calls.
- Public-source requests have a 20-second timeout, 10 MB body cap, content-type validation, bounded Pydantic inputs, and actionable upstream errors.
- `ATTAINS_API_KEY` is only supplied at runtime as the documented header and is never included in provenance URLs, reports, fixtures, or tests.
- Public records retain their source attribution, original identifiers, units, qualifiers, detection limits, method fields, and caveats. Their reuse terms can vary by contributor; users must check source-specific licensing before redistribution.
- WQP retrieval is capped and says when a result may be incomplete. WQX 2 has no stable cursor in this adapter, so continuation means narrowing the date range, station selection, or characteristic set rather than assuming a global page sequence.
- Live outcomes are observations of an external service at one time, not availability guarantees or performance claims. ATTAINS can be rate-limited, and source schemas may change.

## Hardened-retrieval verified run

Run from the repository with Python 3.11.15 on 2026-10-13 EDT. These are direct live-service results from the hardened WQX 2 adapter, not fixtures.

| Scenario | Input | Result | Wall-clock |
| --- | --- | --- | --- |
| WQP availability summary | `USGS-03246200` | 1 GeoJSON feature | 0.15 s |
| WQP station inventory | `USGS-03246200` | 1 GeoJSON feature | 0.09 s |
| WQP measurement retrieval | `USGS-03246200`, `Specific conductance`, 1970-01-01 through 1980-01-01, 25-record cap | 25 normalized raw observations; `truncated: true` because the cap was reached | 0.21 s |
| Repeated identical measurement request | Same normalized request | 25 records from DuckDB cache; original retrieval timestamp preserved; `cache.hit: true` | 0.03 s |

The summary and station services returned `application/vnd.geo+json`; this is now an accepted, explicitly tested GeoJSON media type. The CSV result endpoint returned `text/csv`. No response crossed the 10 MB safety limit.

## Initial verified run

Run from the repository with Python 3.11.15 on 2026-10-13 EDT. The program output and request URLs were retained in the implementation session; values below are direct live-service results, not fixtures.

| Scenario | Input | Result | Wall-clock |
| --- | --- | --- | --- |
| Tool registration | Local FastMCP inspection | 7 tools registered | n/a |
| River resolution | `Little Miami River`, max 5 | 5 candidates; first was reachcode `05090202002563`, NHDPlusID `25243915` | 2.52 s |
| Freshwater Explorer baseline | WGS84 bbox `-84.1,39.1,-84.0,39.2`, 10-record cap | 10 predicted-background conductivity records | 4.27 s |
| WQP measurement retrieval | `USGS-03246200`, `Specific conductance`, 1970-01-01 through 1980-01-01, 25-record cap | 25 normalized raw observations; first value `355 uS/cm @25C`, sampled 1972-08-23 | 0.17 s |

Live services used:

- EPA WATERS GeoViewer Surface Water MapServer layer 1
- EPA Freshwater Explorer Predicted Background Conductivity FeatureServer layer 0
- Water Quality Portal legacy WQX 2 `Result/search`

These performance figures are a starting point, not a service-level claim. The Freshwater Explorer request was notably slower than WQP and should be cached for a demo.

## Safety checks

- No write endpoints or credentials.
- No claim that public contributor records have a blanket reuse license.
- No conversion of modelled/curated screening layers into a regulatory decision.
- No unbounded result request.
