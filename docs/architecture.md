# Architecture

## Design principle

Tools represent a domain action an agent can select correctly, rather than a thin wrapper over a public REST endpoint.

## Layers

- `server.py`: MCP-facing tool definitions and client-safe errors.
- `models.py`: Pydantic input contracts and evidence/provenance types.
- `adapters/wqp.py`: WQP parameter construction, call policy, and response normalization.
- `adapters/waters.py`: EPA WATERS GeoViewer river-name resolution.
- `adapters/wbd.py`: USGS Watershed Boundary Dataset lookup from a two-corner box to HUC8/HUC12.
- `adapters/freshwater.py`: Freshwater Explorer screening-only adapter.
- `adapters/attains.py`: ATTAINS assessment-context adapter with explicit API-key handling.
- `http.py`: injectable HTTP boundary.

## Query policy

`wqp_measurements` needs one exact geographic/station selector, at least one exact WQP characteristic, and an inclusive date range. Results are bounded by `result_limit`; a cap-reached result is explicitly marked `truncated` and instructs the caller to narrow dates, station IDs, or characteristics for a separate bounded slice. The WQP availability summary is the intended preflight tool. `wqp_measurements_page` adds a complete-collection mode: deterministic date-window pages in which each window is returned only when the upstream result is under the cap, with an opaque continuation token bound to the query identity (see README).

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

WQX 3 (`basicPhysChem` profile) is the default WQP mode; `compatibility_mode="wqx2"` selects the legacy WQX 2 endpoints. Each mode has its own normalizer that emits the same record keys without translating values; it never falls back to WQX 2. The two modes use distinct cache keys (source version and base URL), and a record-schema tag in the cache key keeps rows cached under an older record shape from being served. WQX 2 no longer receives USGS data added after early 2024. Station inventory also uses the WQX 3 Station service. The availability summary stays on WQX 2 because WQX 3 has no summary endpoint, so its counts are labelled as a lower bound.
