# Architecture

## Design principle

Tools represent a domain action an agent can select correctly, rather than a thin wrapper over a public REST endpoint.

## Layers

- `server.py`: MCP-facing tool definitions and client-safe errors.
- `models.py`: Pydantic input contracts and evidence/provenance types.
- `adapters/wqp.py`: WQP parameter construction, call policy, and response normalization.
- `adapters/waters.py`: EPA WATERS GeoViewer river-name resolution.
- `adapters/freshwater.py`: Freshwater Explorer screening-only adapter.
- `adapters/attains.py`: ATTAINS assessment-context adapter with explicit API-key handling.
- `http.py`: injectable HTTP boundary.

## Query policy

`wqp_measurements` needs one exact geographic/station selector, at least one exact WQP characteristic, and an inclusive date range. Results are bounded by `result_limit`; a cap-reached result is explicitly marked `truncated` and instructs the caller to narrow dates, station IDs, or characteristics for a separate bounded slice. The WQP availability summary is the intended preflight tool.

## ATTAINS policy

`get_assessment_context` requires exactly one `assessment_unit_id` or `huc12`. The adapter first resolves assessment-unit identifiers through ATTAINS's `assessmentUnits` service, which authoritatively provides organization IDs; it then retrieves assessments per organization. This prevents unverified state-prefix inference and supports HUC12s that cross state or tribal-organization boundaries while retaining a hard cap of 50 resolved organization/unit pairs. A HUC12 is a disclosed resolution step, not a river-corridor or causal inference. ATTAINS requires a free Data.gov API key supplied only through `ATTAINS_API_KEY`; the adapter sends it in the documented `X-Api-Key` header and provenance URLs deliberately omit credentials. Missing configuration fails before network activity. Assessment output is labelled `assessment_context`: a reporting-cycle finding, not a current-condition measurement or causal conclusion.

## Cache and transport policy

Measurement responses are stored in a local DuckDB cache. The key is a SHA-256 digest of canonicalized source, source version, endpoint, and query parameters. Entries expire after one hour and are removed during lookup; source-version changes necessarily produce distinct keys. Responses retain their original retrieval time and cache-hit status. HTTP calls have a 20-second timeout, a 10 MB body limit, and content-type validation before parsing.

## Evidence labels

- `observation`: a raw WQP monitoring observation.
- `coverage_summary`: WQP station/result/activity counts.
- `screening_baseline`: Freshwater Explorer curated/modelled context, never a regulatory conclusion.
- `assessment_context`: ATTAINS reporting context, never a causal finding.

## Compatibility

WQP legacy WQX 2 endpoints are the default. `compatibility_mode="wqx3"` is an explicit adapter boundary but fails safely until the active WQX 3 schema is validated against the provenance-preserving result contract; it never silently falls back to WQX 2.
