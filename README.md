# Watershed Evidence MCP

A provenance-first Model Context Protocol (MCP) server for public U.S. water-quality evidence.

It helps an AI client answer bounded questions about a **river, watershed, or area** by separating four distinct evidence types:

1. Raw monitoring observations from the Water Quality Portal (WQP).
2. Monitoring-location coverage and availability summaries from WQP.
3. EPA Freshwater Explorer curated/modelled screening context.
4. Assessment context from EPA ATTAINS.

This is an exploratory prototype for the [GSA MCP Server and AI Agent Government Hackathon](https://www.gsa.gov/artificial-intelligence/ai-community-of-practice/events-and-training/mcp-server-and-ai-agent-government-hackathon). It only calls public data services and performs no writes.

## Why not WQX Web?

WQX Web's API supports authenticated data-submission workflows. Public retrieval belongs in the Water Quality Portal. This server intentionally does **not** expose WQX submission APIs.

## Tool flow

```text
resolve_waterbody → wqp_available_data → wqp_monitoring_sites → wqp_measurements
                                      ↘ freshwater_screening_baseline
two box corners → resolve_watershed → HUC8 → (any wqp_* huc8 scope)
                                    ↘ HUC12 → get_assessment_context
assessment-unit ID or HUC12 ───────────────→ get_assessment_context
```

### Start from a place you know

If you know where the river is but not what it is called, drag a box around it and send two opposite corners to `resolve_watershed`:

```json
{"name":"resolve_watershed","arguments":{"corner_1":{"latitude":39.30,"longitude":-84.20},"corner_2":{"latitude":39.10,"longitude":-84.40},"level":"huc8"}}
```

The corners can be in any order. The tool returns the USGS Watershed Boundary Dataset units that intersect the box (HUC12 by default, HUC8 with `level`), with each unit's name, area, and states, up to 50 (a truncation warning appears beyond that). A box that straddles a watershed boundary returns every unit it touches; you choose one. Boxes are limited to 0.5° per side, so a box crossing the antimeridian is rejected, and a flat box (both corners on one latitude or longitude) is rejected too. The result is a lookup aid: intersecting a box does not mean a river or station lies inside the watershed.

The server uses the summary endpoint before raw-result retrieval. `wqp_measurements` requires a specific characteristic plus a bounded date range and either selected sites, a bounding box, or a point/radius. Use `wqp_vocab_search` to translate a user phrase into an exact WQP controlled-vocabulary value before supplying it to `wqp_measurements`.

## Run locally

```bash
uv sync --all-groups
cp .env.example .env
# Set ATTAINS_API_KEY in .env if you will use assessment-context retrieval.
uv run watershed-evidence-mcp
```

The server follows the standard Python `.env` convention through `python-dotenv`: it loads **only** a `.env` file in its current working directory, without overriding values already exported by the host environment. The example MCP command uses `uv --directory` so the repository is the working directory. Keep `.env` local; it is ignored by Git. `.env.example` contains only the variable names required for local setup.

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

## Remote (HTTP) mode

Set `PORT` (or `MCP_TRANSPORT=streamable-http`, optionally `MCP_HOST`/`MCP_PORT`) to serve MCP at `/mcp` with a `/health` check; otherwise the server uses stdio. A stray `PORT` exported in your shell switches a local run to HTTP; unset it for stdio clients. Without `PORT`, HTTP mode binds `127.0.0.1` unless `MCP_HOST` is set. The `Dockerfile` builds this mode. The endpoint is unauthenticated; see [`SECURITY.md`](SECURITY.md). The server also exposes an `investigate_waterbody` prompt (the recommended evidence workflow) and `watershed://evidence-types` / `watershed://caveats` resources.

## Hackathon demo

The presentation-grade Little Miami River near Milford flow is documented in
[`docs/little-miami-demo.md`](docs/little-miami-demo.md). It includes a reproducible
MCP client script, explicit river-name disambiguation, bounded source queries,
evidence labels, failure behavior, and reset instructions.

```bash
uv run python scripts/run_little_miami_demo.py
```

## Guardrails

- Every successful upstream response includes query URL(s), retrieval timestamp, source/version, and a data-use caveat.
- It never labels a screening baseline as a regulatory conclusion.
- It does not infer a river corridor from a name alone: `resolve_waterbody` returns candidates and the caller must choose one.
- `resolve_watershed` takes two opposite corners (latitude/longitude, any order; each side at most 0.5°) and returns the USGS WBD HUC8 or HUC12 units that intersect the box. Intersection is not containment; a box that straddles several watersheds returns all of them and the caller must choose.
- It preserves original identifiers, units, qualifiers, and source fields.
- `wqp_measurements` uses a local DuckDB cache keyed by normalized parameters, endpoint, source, and source version. Entries have a one-hour TTL; expired entries are deleted on lookup, and a source-version change creates a distinct cache key.
- ATTAINS calls require a free Data.gov API key supplied at runtime as `ATTAINS_API_KEY`; the adapter sends it only as the documented `X-Api-Key` header, never embeds or logs it, and never includes it in returned provenance URLs. It resolves each requested assessment unit through ATTAINS to obtain authoritative organization IDs before retrieving assessment decisions, rather than inferring a state from an identifier prefix. HUC12 retrieval remains bounded to 50 resolved organization/unit pairs. Missing configuration fails before a network request with the registration URL.
- ATTAINS responses describe a reporting cycle and are context only; they do not establish current condition or prove a cause.
- It caps results and labels every cap-reached response `truncated: true` (WQP and `freshwater_screening_baseline` both report `truncated` and `requested_max_records`); WQP results have no stable cursor here, so the continuation strategy is to narrow date range, station IDs, or characteristics before requesting the next slice.
- Upstream requests use a 20-second timeout, a 10 MB response limit, and expected-content-type checks. Service failures name the safe corrective action without exposing a traceback.
- WQX 3 is the default compatibility mode: it queries the `basicPhysChem` profile at `https://www.waterqualitydata.us/wqx3/`. `compatibility_mode="wqx2"` selects the legacy WQX 2 service, which no longer receives USGS data added after early 2024. Both modes return the same record keys; values are passed through untranslated, so vocabularies can differ (for example sample fraction `Total` in WQX 2 vs `Unfiltered` in WQX 3) and must not be merged as equivalent. WQX 3 has no laboratory name in this profile (`laboratory_name: null`).
- `wqp_monitoring_sites` reads the WQX 3 Station service (CSV converted to GeoJSON). Properties keep WQX 3 column names such as `Location_Identifier`, `Location_Type`, and `Location_HUCTwelveDigitCode`; geometry uses WQP's standardized NAD83 coordinates and is null when they are missing.
- `wqp_available_data` still uses the WQX 2 summary service because WQX 3 has no summary endpoint. Its counts exclude USGS data added after early 2024 and are a lower bound; each response includes a `coverage_note` saying so.
- Records keep `sample_fraction`, `result_status`, `activity_type`, `usgs_pcode`, `provider_name`, and detection limits. WQX 3 has two detection-limit slots, kept as `detection_limit_*` (A) and `detection_limit_b_*` (B); neither is preferred. In WQX 2 the `detection_limit_b_*` fields are always null because that profile has only one slot, not because no second limit exists.
- `resolve_waterbody` candidates include `huc8`, the first 8 digits of the NHD reachcode. It is the whole subbasin containing the reach, far wider than the river itself; use it as a WQP `huc8` scope only when that breadth is intended.

## Official sources

- [WQP Web Services Guide](https://www.waterqualitydata.us/webservices_documentation/)
- [WQP modernization / WQX 3 reference](https://www.epa.gov/waterdata/water-quality-portal-modernization-quick-reference-guide)
- [EPA Freshwater Explorer](https://www.epa.gov/water-research/freshwater-explorer)
- [EPA ATTAINS Web Services](https://www.epa.gov/waterdata/how-access-and-use-attains-web-services)
- [USGS Watershed Boundary Dataset MapServer](https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer)
- [EPA WATERS GeoViewer surface-water layer](https://watersgeo.epa.gov/arcgis/rest/services/OWOTHER/WATERS_GeoViewer_SurfaceWater/MapServer/1)

## Current scope

The initial implementation supports WQP public station summaries, station inventory, exact-characteristic measurement retrieval, vocabulary discovery, and river-name candidate resolution. ### Bounded sample vs. complete collection

- `wqp_measurements` is a **bounded exploratory sample**: at most `result_limit` rows, `truncated: true` when the cap is reached. Never present it as a complete dataset.
- `wqp_measurements_page` retrieves a **complete, explicitly defined collection** (stations/area, exact characteristics, date range) as contiguous date-window pages. WQP has no stable cursor and unsorted results, so completeness is established per window: a window is returned only if the source gave fewer rows than `result_limit`; otherwise the window is halved (at most 12 upstream requests per call). A single day that still hits the cap raises an error rather than dropping records.
- Call with no `continuation_token`, then pass each `collection.continuation_token` back (same query) until it is `null` (`final_page: true`). The collection is complete only if every page was retrieved; windows tile `declared_range` with no gaps, and `query_id` identifies the query. Invalid, foreign, or out-of-range tokens are rejected. Records stay raw (units, qualifiers, detection limits, methods) and per-page provenance is preserved. Pages are cached for one hour, so a collection can differ if the source changes between calls.

`freshwater_screening_baseline` takes a `layer`: `predicted_conductivity` (default; stream reaches, `id` = `COMID`), or the station point layers `station_water_chemistry_10th_percentile` (pH, DOC, hardness), `station_aluminum_criteria`, and `station_cadmium_criteria` (calculated acute/chronic criteria; `id` = WQP station ID). Criteria layers carry their own caveat: they are screening values, not adopted standards, exceedances, or impairment findings. Every layer is returned as a GeoJSON `feature_collection` (EPSG:4326, attributes in `properties`) alongside `bounding_box`, `truncated`, and `records_without_geometry`. Rendering is out of scope for this server: a client or agent can pass `feature_collection` to its own plotting stack (for example geopandas, `sf`, or Leaflet) and should label the output as modelled screening context, not observations or an impairment finding. Do not infer completeness from the record count; use `truncated`.

Freshwater Explorer and ATTAINS adapters are deliberately isolated behind their own modules so service changes do not break WQP retrieval.
