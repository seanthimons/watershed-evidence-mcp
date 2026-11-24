# Initial public test seams

These seams will be tested before dependency-backed integration work:

1. **WQP query construction** — a validated public `WqpQuery` becomes the documented WQP parameter set without silently widening scope.
2. **WQP response normalization** — a representative public WQP record preserves identifiers, units, qualifiers, method fields, and provenance.
3. **River-name resolution** — an EPA GeoViewer feature becomes a candidate and retains ambiguity instead of guessing.
4. **MCP tool contract** — supplied valid inputs produce structured JSON; invalid/unbounded inputs are rejected before a network call.
5. **ATTAINS assessment-context normalization** — an assessment preserves reporting-cycle, use-support, parameter, and source-identifier context without asserting causation.
6. **ATTAINS selector and no-result handling** — one exact assessment-unit ID or HUC12 is required; a valid empty upstream response is structured and query provenance never reveals an API key.
7. **Box-to-watershed resolution** — two corners in any order become one normalized envelope; oversize, degenerate, or antimeridian boxes are rejected before a network call; multiple, truncated, and empty matches are reported explicitly.

Live smoke tests will call the actual WQP and EPA GeoViewer endpoints separately from the deterministic test suite, record wall-clock time and result count, and fail loudly rather than using invented data.
