# Watershed Evidence MCP

A provenance-first Model Context Protocol (MCP) server for public U.S. water-quality evidence.

It helps an AI client answer bounded questions about a **river, watershed, or area** by separating four distinct evidence types:

1. Raw monitoring observations from the Water Quality Portal (WQP).
2. Monitoring-location coverage and availability summaries from WQP.
3. EPA Freshwater Explorer curated/modelled screening context.
4. Assessment context from EPA ATTAINS (planned adapter).

This is an exploratory prototype for the [GSA MCP Server and AI Agent Government Hackathon](https://www.gsa.gov/artificial-intelligence/ai-community-of-practice/events-and-training/mcp-server-and-ai-agent-government-hackathon). It only calls public data services and performs no writes.

## Why not WQX Web?

WQX Web's API supports authenticated data-submission workflows. Public retrieval belongs in the Water Quality Portal. This server intentionally does **not** expose WQX submission APIs.

## Tool flow

```text
resolve_waterbody → wqp_available_data → wqp_monitoring_sites → wqp_measurements
                                      ↘ freshwater_screening_baseline
```

The server uses the summary endpoint before raw-result retrieval. `wqp_measurements` requires a specific characteristic plus a bounded date range and either selected sites, a bounding box, or a point/radius.

## Run locally

```bash
uv sync --all-groups
uv run watershed-evidence-mcp
```

Use an MCP client configured for stdio, for example:

```json
{
  "mcpServers": {
    "watershed-evidence": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/watershed-evidence-mcp", "run", "watershed-evidence-mcp"]
    }
  }
}
```

## Guardrails

- Every successful upstream response includes query URL(s), retrieval timestamp, source/version, and a data-use caveat.
- It never labels a screening baseline as a regulatory conclusion.
- It does not infer a river corridor from a name alone: `resolve_waterbody` returns candidates and the caller must choose one.
- It preserves original identifiers, units, qualifiers, and source fields.
- `wqp_measurements` uses a local DuckDB cache keyed by normalized parameters, endpoint, source, and source version. Entries have a one-hour TTL; expired entries are deleted on lookup, and a source-version change creates a distinct cache key.
- It caps results and labels every cap-reached response `truncated: true`; WQX 2 results have no stable cursor here, so the continuation strategy is to narrow date range, station IDs, or characteristics before requesting the next slice.
- Upstream requests use a 20-second timeout, a 10 MB response limit, and expected-content-type checks. Service failures name the safe corrective action without exposing a traceback.
- WQX 2 is the default compatibility mode. `compatibility_mode="wqx3"` is explicit but currently rejected pending schema validation, rather than silently routing through a legacy parser.

## Official sources

- [WQP Web Services Guide](https://www.waterqualitydata.us/webservices_documentation/)
- [WQP modernization / WQX 3 reference](https://www.epa.gov/waterdata/water-quality-portal-modernization-quick-reference-guide)
- [EPA Freshwater Explorer](https://www.epa.gov/water-research/freshwater-explorer)
- [EPA WATERS GeoViewer surface-water layer](https://watersgeo.epa.gov/arcgis/rest/services/OWOTHER/WATERS_GeoViewer_SurfaceWater/MapServer/1)

## Current scope

The initial implementation supports WQP public station summaries, station inventory, exact-characteristic measurement retrieval, vocabulary discovery, and river-name candidate resolution. Freshwater Explorer and ATTAINS adapters are deliberately isolated behind their own modules so service changes do not break WQP retrieval.
