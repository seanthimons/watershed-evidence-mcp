# Architecture

## Design principle

Tools represent a domain action an agent can select correctly, rather than a thin wrapper over a public REST endpoint.

## Layers

- `server.py`: MCP-facing tool definitions and client-safe errors.
- `models.py`: Pydantic input contracts and evidence/provenance types.
- `adapters/wqp.py`: WQP parameter construction, call policy, and response normalization.
- `adapters/waters.py`: EPA WATERS GeoViewer river-name resolution.
- `adapters/freshwater.py`: Freshwater Explorer screening-only adapter.
- `http.py`: injectable HTTP boundary.

## Query policy

`wqp_measurements` needs one exact geographic/station selector, at least one exact WQP characteristic, and an inclusive date range. Results are bounded by `result_limit`. The WQP availability summary is the intended preflight tool.

## Evidence labels

- `observation`: a raw WQP monitoring observation.
- `coverage_summary`: WQP station/result/activity counts.
- `screening_baseline`: Freshwater Explorer curated/modelled context, never a regulatory conclusion.
- `assessment_context`: ATTAINS reporting context, never a causal finding.

## Compatibility

WQP legacy WQX 2 endpoints are the default. WQX 3 is isolated behind configuration in a later slice because its schema transition remains active.
