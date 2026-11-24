# Evaluation protocol and live results

The GSA hackathon requires submitters to document evaluation setup and results. This document defines the repeatable protocol and records the verified public-service runs, from the first WQX 2 run on 2026-10-13 to the WQX 3 run on 2026-11-23.

## Scenarios

1. Valid WQP coverage lookup for a small, real bounding box.
2. Valid WQP site lookup for the same area.
3. Valid bounded result query for one documented characteristic and date range.
4. Valid WQP controlled-vocabulary lookup for `Specific conductance`.
5. Ambiguous river-name lookup returns multiple candidates and a disambiguation warning.
6. Valid Freshwater Explorer predicted-background screening lookup.
7. Invalid: no spatial/station selector.
8. Invalid: reversed dates.
9. Invalid: result request exceeds maximum cap.
10. Upstream outage/malformed response is expressed as an actionable tool error without exposing internals.
11. Valid ATTAINS assessment-context lookup with an environment-supplied API key; output includes reporting cycle, use, status, parameter context, source identifiers, query URL, timestamp, and causal caveat.
12. Invalid: missing or malformed HUC12 / assessment-unit selector is rejected before a network call.
13. Invalid configuration: missing `ATTAINS_API_KEY` fails cleanly before a network call.
14. Valid complete-collection retrieval: `wqp_measurements_page` follows continuation tokens to the final page and returns every record in the declared range.
15. Box-to-watershed resolution: a two-corner box returns intersecting HUC8/HUC12 units; oversize, flat, and antimeridian boxes are rejected before a network call (offline tests only).

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

The command runs seven scenarios (eight with ATTAINS), each a public, read-only, bounded request sequence: WATERS name resolution (five candidates), WQP summary and station lookups for one public station, a five-result WQP controlled-vocabulary lookup for `Specific conductance`, WQP results with a 25-record cap, a paged complete collection (10 records per page, at most 20 pages), and Freshwater Explorer with a 10-record cap. It uses a temporary WQP cache so the measurement scenario always reaches the live service. If `ATTAINS_API_KEY` is configured through the standard project `.env` file or exported environment, it also evaluates one bounded ATTAINS assessment-context lookup; otherwise that row is recorded as `skipped`, with no request attempted. It creates timestamped JSON and Markdown reports containing endpoint names, query shape, success/error outcome, HTTP outcome, record count, and wall-clock duration. The ignored `evaluation-reports/` directory prevents local reports from entering Git history. The report deliberately retains neither response bodies nor credentials.

## Security posture and limitations

- The server is read-only. It makes no submission, mutation, or credential-management calls.
- Public-source requests have a 20-second timeout, 10 MB body cap, content-type validation, bounded Pydantic inputs, and actionable upstream errors.
- `ATTAINS_API_KEY` is only supplied at runtime as the documented header and is never included in provenance URLs, reports, fixtures, or tests.
- Public records retain their source attribution, original identifiers, units, qualifiers, detection limits, method fields, and caveats. Their reuse terms can vary by contributor; users must check source-specific licensing before redistribution.
- WQP retrieval is capped and says when a result may be incomplete. For `wqp_measurements`, continuation means narrowing the date range, station selection, or characteristic set. WQP has no stable cursor, so `wqp_measurements_page` instead pages a complete collection by date window with continuation tokens.
- Live outcomes are observations of an external service at one time, not availability guarantees or performance claims. ATTAINS can be rate-limited, and source schemas may change.

## WQX 3 live run (2026-11-23)

Run with `scripts/run_live_evaluation.py` after WQX 3 became the default WQP mode. Every row succeeded, with a real `ATTAINS_API_KEY` configured. Each timing is one observation of a public service.

| Scenario | Input | Result | Wall-clock |
| --- | --- | --- | --- |
| WATERS river-name resolution | `Little Miami River`, max 5 | 5 candidates | 3.47 s |
| WQP availability summary (WQX 2 summary service) | `USGS-03246200` | 1 GeoJSON feature | 0.25 s |
| WQP station inventory (WQX 3 Station) | `USGS-03246200` | 1 station | 1.07 s |
| WQP controlled vocabulary | `CharacteristicName`, `Specific conductance`, page size 5 | 3 records | 0.15 s |
| WQP bounded measurements (WQX 3) | `USGS-03246200`, `Specific conductance`, 1970-01-01 through 1980-01-01, 25-record cap | 25 records | 1.98 s |
| WQP paged complete collection (WQX 3) | Same query, 10 records per page | 31 records over the date-window pages | 22.52 s |
| Freshwater Explorer baseline | WGS84 bbox `-84.1,39.1,-84.0,39.2`, 10-record cap | 10 records with stream-reach geometry | 7.63 s |
| ATTAINS assessment context | `DCTFD01R_00`, reporting cycle 2024 | 1 record | 1.25 s |

Observed latency to plan for:

- The WQX 3 Station service was the least predictable call in the Little Miami demo. For the Milford box (`-84.32,39.15,-84.27,39.20`) a direct request took between 14 s and more than 60 s, and the 20-second client timeout fired twice before a third run succeeded (29 stations). Retry, and rehearse the demo beforehand.
- The paged collection makes one upstream request per date window, so it is much slower than a single bounded request.

All 10 questions in `eval/phoenix/datasets/watershed-eval-0/evaluation.xml` were re-checked against the current code on the same day with direct tool calls (no model requests), and every answer still held under WQX 3. See `eval/README.md`.

## Agent comparison (2026-11-23)

Claude Haiku 5.5 answered the 10 gold questions three times each in three arms that differ only in tool access, run headless with `claude -p`. Grading was a normalized match of the final `ANSWER:` line against the gold answer (case, spacing, markdown marks and a trailing period ignored; Q2 and Q10 matched on the key values), with no LLM judge; a run without an `ANSWER:` line counted as wrong.

| Arm | Correct runs | Questions right in all 3 trials |
| --- | --- | --- |
| This MCP server | 27 of 30 | 9 of 10 |
| Web search and fetch only | 13 of 30 | 3 of 10 |
| No tools | 6 of 30 | 2 of 10 |

- Q7 (the 614-record complete collection) failed in all three rerun MCP trials (one first-pass trial did reach 614): a date-window page of about 76,000 characters exceeded the client's inline output limit, and the test setup gave the agent no file reader. The agent reported this and did not guess.
- Recommendation: shrink or summarize the records in each `wqp_measurements_page` response so a page fits a client's inline output limit. The limit itself was not measured; the agent's report put the failing page at about 76,000 characters.
- A first pass ran six jobs in parallel, and the Water Quality Portal answered with HTTP 429 (MCP arm 22 of 30). The scores above come from a rerun at two jobs at a time. The no-tool score comes from the first pass because that arm calls no service.
- One small model, one date, three trials per question. In the no-tool arm, 16 of 30 runs ended without an `ANSWER:` line, and the ones inspected were attempts to call an unavailable tool. The harness and graded results are kept locally under `evaluation-reports/agent-eval-2026-11-23/`, which is not tracked by git.

## Hardened-retrieval verified run

Run from the repository with Python 3.11.15 on 2026-10-13 EDT. These are direct live-service results from the hardened WQX 2 adapter, not fixtures. WQX 3 became the default on 2026-11-23; the WQX 2 rows below are a historical record (WQX 3 reports units without the `@25C` suffix, for example). The current figures are in the WQX 3 run above.

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
| Tool registration | Local FastMCP inspection | 7 tools registered (9 tools, 1 prompt and 2 resources as of 2026-11-23) | n/a |
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
