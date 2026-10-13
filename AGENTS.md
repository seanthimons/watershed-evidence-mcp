# AGENTS.md

## Project

Watershed Evidence MCP is a read-only Python MCP server for retrieving public
U.S. water-quality evidence from EPA WATERS, the Water Quality Portal (WQP),
and Freshwater Explorer. Its central contract is provenance-first, bounded
retrieval: preserve source metadata and caveats, and never present screening
context or public records as regulatory determinations.

Read `README.md`, `TEST_SEAMS.md`, and the relevant adapter before non-trivial
changes.

## Layout

- `src/watershed_evidence_mcp/server.py`: MCP tool definitions and response shaping.
- `src/watershed_evidence_mcp/models.py`: Pydantic input/output contracts and bounds.
- `src/watershed_evidence_mcp/http.py`: injectable HTTP boundary and upstream errors.
- `src/watershed_evidence_mcp/adapters/`: source-specific public API clients.
- `tests/`: async unit tests with mocked HTTP transports.
- `docs/architecture.md`: source boundaries and design decisions.
- `docs/evaluation.md`: hackathon evaluation approach.

## Commands

```bash
uv sync --all-groups --locked
uv run ruff format --check .
uv run ruff check .
uv run pytest
uv run pytest tests/test_wqp.py
uv run watershed-evidence-mcp
```

Use Python 3.11 or later as declared in `pyproject.toml`. Add or update the
lockfile only for an intentional dependency change, using `uv lock` followed
by the relevant checks.

## Working rules

- Inspect the affected source, tests, and documentation before editing. Keep
  unrelated local work untouched.
- Keep MCP tools read-only. Do not add credentials, write endpoints, or hidden
  defaults that widen a query.
- Enforce request bounds in Pydantic models or at the public tool boundary.
  A river name is ambiguous until the caller selects a candidate and supplies
  an explicit spatial or station scope.
- Preserve provenance: source, version, retrieval time, query URL, and a
  source-appropriate caveat belong in every tool response.
- WQP data are heterogeneous public observations. Preserve identifiers, units,
  qualifiers, detection limits, and method metadata; do not silently
  harmonize, infer, or make regulatory claims.
- Freshwater Explorer values are screening context, not current raw
  observations or regulatory findings.
- Keep external HTTP behind `JsonHttpClient` or an adapter seam. Unit tests
  must use deterministic mocked transports; routine tests must not call live
  government services.
- Use type hints, Pydantic models, and Ruff-compatible Python. Prefer small,
  explicit transformations over generic abstractions.
- Do not commit tokens, API keys, private URLs, or recorded live payloads.
  Add a Gitleaks allowlist entry only for a confirmed false positive and scope
  it narrowly.

## Git and completion

- Use a conventional branch name such as `feat/wqp-query-bounds` or
  `fix/provenance-caveat` and Conventional Commits.
- Keep commits scoped to one logical change. Do not commit generated caches,
  `.venv/`, or unrelated formatting churn.
- Definition of done: targeted tests pass; `ruff format --check` and `ruff
  check` pass; the full test suite passes for shared contracts, adapters, or
  CI changes. Update user-facing documentation when tool behavior changes.
- If a required check cannot run, report the blocker and the closest completed
  validation. Push the feature branch before handoff; do not push directly to
  `main`.
