# Watershed Evidence MCP evaluation

Sean Thimons, U.S. EPA, Office of Water · Nov 23, 2026

*This is a hackathon prototype. It has not been reviewed or approved by the U.S. EPA, and the views expressed are the author's own, not the position or policy of the agency. Outputs are public-data retrieval, not regulatory determinations.*

GSA MCP and AI Agent Hackathon. Follows the sections of the GSA sample evaluation document.

- **Server under test:** Watershed Evidence MCP (Python, FastMCP), version 0.1.0
- **Evaluation framework:** offline pytest suite, opt-in live evaluation script, and a 10-item question set in the GSA template format
- **Agent model:** Claude Haiku 5.5 (`claude-haiku-5-5`), run headless with `claude -p` and default sampling settings (no temperature set), three trials per question in each of three arms, on Nov 23, 2026
- **Dataset:** watershed-eval-0 (10 items)
- **Dates:** live service runs on Nov 23, 2026 (WQX 3 default); question set verified Oct 19, 2026 and re-checked Nov 23, 2026

## 1. Overview and objectives

The goal of this evaluation is to show that the server gives an agent correct, bounded and traceable public water-quality evidence, and that it refuses to turn that evidence into conclusions it has no authority to make. A passing server returns the right records from the right public service, labels every result with its evidence type and provenance, fails cleanly on bad input or upstream trouble, and never presents a modelled baseline or raw samples as a regulatory finding.

The server exposes nine read-only tools, one guided prompt and two reference resources:

- **Place:** resolve_waterbody turns a river name into NHDPlus reach candidates through EPA WATERS. resolve_watershed turns a two-corner map box into the intersecting HUC8 or HUC12 units from the USGS Watershed Boundary Dataset.
- **Water Quality Portal (WQX 3 by default, WQX 2 on request):** wqp_vocab_search, wqp_available_data, wqp_monitoring_sites, wqp_measurements and wqp_measurements_page.
- **Modelled context:** freshwater_screening_baseline queries EPA Freshwater Explorer.
- **Assessment context:** get_assessment_context queries EPA ATTAINS with an environment-supplied API key.
- **Prompt and resources:** investigate_waterbody, plus the evidence-types and caveats resources.

## 2. Testing methodology

### Framework and reproducibility

Testing runs in three layers, each with one command.

1. **Offline suite:** `uv run pytest` runs every tool against small, redacted fixtures through httpx.MockTransport. It makes no network calls, so results are deterministic. All 77 tests passed on Nov 23, 2026.
2. **Live evaluation:** `uv run python scripts/run_live_evaluation.py --output-dir evaluation-reports` runs seven scenarios (eight with ATTAINS), each a public, read-only, bounded request sequence: WATERS name resolution, WQP summary and station lookups, a WQP vocabulary lookup, WQP results with a 25-record cap, a paged complete collection (10 records per page), and Freshwater Explorer with a 10-record cap. It adds one ATTAINS lookup when a key is configured and records it as skipped otherwise. Each run writes timestamped JSON and Markdown reports with no response bodies or credentials.
3. **Demo run:** `uv run python scripts/run_little_miami_demo.py` runs the full Little Miami River workflow and checks that each step returns the expected evidence type.

### Scenario protocol

Fifteen scenarios cover valid lookups, a complete paged collection, a map-box-to-watershed lookup (offline tests only), an ambiguous river name that must return several candidates with a warning, invalid inputs (no spatial selector, reversed dates, a request over the record cap, a malformed HUC12 or assessment-unit selector), an upstream outage or malformed response, and a missing ATTAINS key. For each live scenario the protocol records the UTC time and endpoint, input parameters, HTTP status, result count, wall-clock time, whether a structured response or the expected validation error came back, and whether provenance was complete (source, query URL, timestamp and caveat).

### Golden dataset

watershed-eval-0 holds 10 question and answer pairs in the GSA template's format. Answers were produced by calling the server over stdio against the live public services on Oct 19, 2026, with no model requests. On Nov 23, 2026, after WQX 3 became the default, all 10 were re-checked with direct tool calls and every answer still held. Three questions take a single tool call and the rest chain several.

- **Guardrails:** two questions have short answers and check exact vocabulary and that no regulatory conclusion is drawn.
- **Non-detects:** one question checks that non-detects are neither dropped nor imputed: 25 of 30 lead results at the chosen Ohio EPA station have no numeric value.
- **Not yet covered:** no question exercises get_assessment_context, which needs an API key.

### Evaluators

The same Haiku model answered every question in three arms that differ only in tool access: (1) this MCP server, (2) no tools, and (3) web search and web fetch only. Each run got the question text plus one instruction to finish with a line `ANSWER: <answer>` in the format the question asks for. There was no LLM judge. A script compared the final `ANSWER:` line with the gold answer by normalized match (case, spacing, the micro sign, markdown marks and a trailing period ignored; Q2 and Q10 matched on the key values), and a run with no `ANSWER:` line counted as wrong. The misses were read afterwards to find out why they happened.

### Test design rationale

The two failures that matter most for a public-evidence server are returning the wrong data and claiming more than the data supports. The scenario protocol and offline suite cover the first. The evidence labels, the guardrail questions and the non-detect question cover the second.

## 3. Performance metrics

### Metrics tracked

- Structured success or expected validation error for every scenario
- Result count and whether a cap truncated it
- Wall-clock time per request, and cache hits on repeat requests
- Provenance completeness on every response

### Results

Live results from Nov 23, 2026, made with `scripts/run_live_evaluation.py` after WQX 3 became the default. Every row succeeded.

| Scenario | Result | Time |
| --- | --- | --- |
| River name resolution, Little Miami River | 5 candidates | 3.47 s |
| WQP availability summary (WQX 2 summary service), one USGS station | 1 GeoJSON feature | 0.25 s |
| WQP station inventory (WQX 3), same station | 1 station | 1.07 s |
| WQP vocabulary lookup, Specific conductance | 3 records | 0.15 s |
| WQP specific conductance (WQX 3), 1970 to 1980, 25-record cap | 25 observations | 1.98 s |
| Same query as a paged complete collection, 10 records per page | 31 records | 22.52 s |
| Freshwater Explorer baseline, 10-record cap | 10 records with reach geometry | 7.63 s |
| ATTAINS assessment context, one assessment unit | 1 record | 1.25 s |

The earlier run on Oct 13, 2026 used the WQX 2 adapter. It measured 0.15 s for the availability summary and 0.21 s for a 25-record request. A repeat of that request came from the DuckDB cache in 0.03 s with the original retrieval time kept. Freshwater Explorer took 4.27 s and name resolution 2.52 s.

ATTAINS was verified end to end with a real Data.gov key: the assessment-unit lookup resolved its organization first, then returned HTTP 200 with one normalized record (reporting cycle, status, four designated uses and six parameter records). The shared demo key returned HTTP 429. The Nov 23 run also resolved and returned one record with a real key.

### Agent results

Haiku 5.5, 10 questions, 3 trials each (30 runs per arm). Scores are correct runs out of 30.

| Arm | Correct runs | Questions right in all 3 trials | Cost for 30 runs |
| --- | --- | --- | --- |
| MCP server | 27 of 30 (90%) | 9 of 10 | $0.18 |
| Web search only | 13 of 30 (43%) | 3 of 10 | $0.76 |
| No tools | 6 of 30 (20%) | 2 of 10 | $0.72* |

- **MCP server:** every question was right in all three trials except Q7 (the 614-record Orthophosphate collection), which failed in all three rerun trials (one first-pass trial did reach 614). The third date-window page came back as about 76,000 characters, which is over the client's inline output limit. The client saved it to a file, and the test setup gave the agent no file-reading tool, so the agent could not finish the count. It said so and did not guess. A real client with a file reader would likely get past this, but the page size is a usability limit worth fixing.
- **Web search only:** the agent answered Q1, Q9 and Q10 correctly in all three trials of the rerun. It gave wrong counts with no warning on Q3 (18 against 17, three times) and Q6 (65, false, twice), and said "approximately 580 rows" for Q7. Several runs reported "no data" or "unable to determine" for questions whose data exist.
- **No tools:** the agent got only Q1 (vocabulary) and Q9 (no regulatory conclusion) right in all three trials. 16 of 30 runs ended without an `ANSWER:` line; the ones inspected were attempts to call a tool it did not have. They count as wrong. The other misses were refusals to guess.
- **Guardrail:** all 9 runs of Q9 in the three arms gave "cannot be determined", and none made a regulatory claim.
- **Rate limits:** the first pass ran six jobs in parallel and the Water Quality Portal answered many requests with HTTP 429. That pass scored the MCP arm 22 of 30 and the web arm 13 of 30, and most MCP misses were 429 errors that the agent reported honestly. The scores above come from a rerun at two jobs at a time, where one run in each arm mentioned a 429 in its raw output. The no-tool arm does not call any service, so its score comes from the first pass.
- **Cost:** *Two no-tool runs that ended without an `ANSWER:` line account for about $0.65 of the no-tool total, so cost per run is not a fair comparison between arms.
- **Caveats:** one model, one date, three trials per question and strict string matching. Q8 in the web arm was marked wrong in one run because the agent wrote "modelled screening context" instead of the label `screening_baseline`. The no-tool arm is a closed-book baseline, not a statement about what a person with a browser could do.

### Failure analysis

- The WQX 3 Station service was the least predictable call. For the Milford demo box a direct request took 14 s to more than 60 s, and the 20-second timeout fired twice before a third run succeeded. Retry, and rehearse the demo beforehand.
- Freshwater Explorer was the slowest call in the Nov 23 live run (7.63 s) and intermittently times out at the 20-second limit, so it should be cached for demos and retried before a timeout counts as a wrong answer.
- The paged collection makes one upstream request per date window, so it is much slower (22.52 s for 31 records) than a bounded request.
- A date-window page from the 614-record Orthophosphate collection came back at about 76,000 characters, over the client's inline output limit in the agent test, so Haiku could not finish the count in any rerun trial (see Agent results). The limit itself was not measured.
- WATERS does not guarantee result order, so one question depends on its reach appearing within the first 25 candidates.
- Station counts in the WQP inventory are snapshots and grow as new data is reported.

## 4. Security considerations

### Data classification

All data comes from public federal services (Water Quality Portal, EPA WATERS, USGS Watershed Boundary Dataset, Freshwater Explorer and ATTAINS). No PII or CUI appears in queries, fixtures, reports or traces. Contributor reuse terms can vary, so users should check source licensing before redistributing records.

### Read-only by design

No tool writes to any service. The server makes no submission, mutation or credential-management calls.

### Input validation and bounded requests

Inputs are Pydantic models with bounded fields and Literal types, such as the sample medium and the WQX compatibility mode. Every request has a 20-second timeout, a 10 MB body cap and content-type validation. Results that reach a cap come back flagged as truncated, and unbounded requests are rejected.

### Secrets and configuration

The ATTAINS key is read from the environment at runtime and sent only as the documented request header. It never appears in provenance URLs, reports, fixtures or tests.

### Scope containment

The server keeps modelled screening layers and raw samples separate from assessment decisions and never converts either into a regulatory finding. Two questions in the dataset test this guardrail.

### Known gaps

- HTTP mode has no authentication. It needs an authenticating gateway and the usual ATO process before any agency use. Local stdio use does not have this exposure.
- The question set has no adversarial or prompt-injection cases yet.

## 5. Lessons learned and recommendations

### What worked

Offline fixtures kept the test suite fast and repeatable, while the opt-in live run proved the adapters against the real services. Labelling every result with its evidence type made it easy to check whether an answer leaned on the right kind of evidence. The DuckDB cache cut a repeat WQP request from 0.21 s to 0.03 s.

### Limitations

The question set is small (10 items) and does not cover ATTAINS. Agent accuracy was measured with one small model (Haiku 5.5), so it says little about larger models or other clients. Live timings are one observation of external services, not performance guarantees.

### Recommendations

1. Put an authenticating gateway in front of HTTP mode before anyone else can reach it.
2. Keep WQX 3 and WQX 2 values separate, since their vocabularies differ. Retry a slow WQX 3 call instead of switching modes silently, and label any WQX 2 result as such.
3. Give the default setup an agency ATTAINS key so assessment context works out of the box.
4. Rerun the agent comparison with a larger model and a client that can read saved tool output, and add ATTAINS, adversarial and out-of-scope questions.
5. Shrink or summarize the records in each `wqp_measurements_page` response so a 100-record page fits inside a client's inline output limit.
6. Human-review agent answers and generated code before relying on them.
