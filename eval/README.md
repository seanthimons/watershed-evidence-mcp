# Evaluation questions

`phoenix/datasets/watershed-eval-0/evaluation.xml` holds 10 question/answer pairs in the
GSA template's format. Each is read-only and independent. Q1, Q4 and Q6 take a single call; the rest chain
several. Q1 and Q9 have short or guessable answers and are there to check guardrails
(exact vocabulary, no regulatory conclusion), not retrieval depth. Q10 checks that an agent
does not drop or impute non-detects: 25 of 30 Lead results have no numeric value. The
rejected-unbounded-scope guardrail is covered by the unit tests instead.

## Verification record

Answers were produced by calling the local MCP server over stdio against the live public
services on 2026-10-19 (no model requests). They depend on historical, closed date ranges
and fixed identifiers, but upstream data can be revised or stations added:

- Q3 (station-type count) and Q4 (largest group) are snapshots of the WQP inventory, which
  grows as new data are reported.
- Q2 depends on the unordered WATERS result list; with a cap of 25 the NHDPlusID was returned
  in the first 25 on 2026-10-19 but the service does not guarantee order.
- Q8 uses a bounding box that returned 10 records (`truncated: false`) so the COMID cannot be
  dropped by the cap; the value is compared rounded to one decimal.
- The Freshwater Explorer service intermittently times out at 20 s; retry before treating a
  timeout as a wrong answer.
- Q9 has no data dependency; it tests the server's guardrails.
- Q10 uses a closed 2015-2022 range at an Ohio EPA station (30 Lead results, 5 numeric).
- No question exercises `get_assessment_context`, which needs an `ATTAINS_API_KEY`.

Re-run each question through the tools and update an answer if upstream data changed.
