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

On 2026-10-13, the new EPA endpoint returned the documented `API_KEY_MISSING` response without a key. A live `huc12summary` request with the EPA-documented `DEMO_KEY` returned one real HUC12 summary and 18 assessment-unit identifiers for HUC12 `020700100204`. The `assessments` endpoint then returned HTTP 429 for the shared low-rate demo key, so this repository does **not** record a fabricated end-to-end result. Run scenario 10 with a non-rate-limited `ATTAINS_API_KEY` before representing the adapter as live-verified.

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
| Tool registration | Local FastMCP inspection | 6 tools registered | n/a |
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
