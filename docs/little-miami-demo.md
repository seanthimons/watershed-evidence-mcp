# Little Miami River evidence demo

This is a **presentation flow**, not a second dashboard. It uses the local MCP server as the only data-access surface and renders a short, provenance-linked Markdown evidence packet from live public-service responses.

## Question

> Is conductivity elevated in the Little Miami River near Milford, Ohio relative to its expected background, and what evidence supports that?

The demo deliberately separates observations, coverage, and Freshwater Explorer's modelled screening context. It does **not** make a regulatory or impairment determination.

## Fast path: reproducible demo client

From the repository root:

```bash
uv sync --all-groups --locked
uv run python scripts/run_little_miami_demo.py
```

The script starts `watershed-evidence-mcp` as a stdio child process and calls it through the official Python MCP client. It prints a presentation-ready Markdown packet containing the selected reach, scope, a metadata-preserving observation table, full source provenance, and interpretation boundary.

To save a transient packet outside source control:

```bash
uv run python scripts/run_little_miami_demo.py --output /tmp/little-miami-evidence.md
```

Do not commit live responses: they are time-dependent public-service outputs, not fixtures.

## Scripted flow

The script executes these calls in order. The prompts below are suitable for a compatible MCP client such as Inspector.

1. **Resolve the ambiguous river name**

   Prompt: `Resolve “Little Miami River” and show the candidate reaches. Do not retrieve monitoring data yet.`

   Expected tool call:

   ```json
   {"name":"resolve_waterbody","arguments":{"river_name":"Little Miami River","max_candidates":10}}
   ```

   Expected behavior: multiple candidates and the explicit warning to select a candidate plus spatial scope. Stop here if the selected reachcode `05090202002563` (NHDPlusID `25243915`) is not returned.

2. **Declare the selected reach and bounded study area**

   Selected river reach: `05090202002563`, near Milford. The explicit WGS84 bounding box is west/south/east/north: `-84.32,39.15,-84.27,39.20`.

   This is a demonstrative scope, not a claim that the entire named river is represented.

3. **Preflight coverage before raw retrieval**

   Prompt: `For the declared bounding box, show WQP coverage and stations. Label the results as coverage, not conductivity measurements.`

   Expected tool calls:

   ```json
   {"name":"wqp_available_data","arguments":{"scope":{"bounding_box":{"west":-84.32,"south":39.15,"east":-84.27,"north":39.20}}}}
   {"name":"wqp_monitoring_sites","arguments":{"scope":{"bounding_box":{"west":-84.32,"south":39.15,"east":-84.27,"north":39.20}}}}
   ```

   Select the stream station `USGS-03245500` — *Little Miami River at Milford OH* — for the bounded observation request. Do not treat other returned wells, tributaries, or groundwater aggregates as mainstem Little Miami observations.

4. **Retrieve bounded observations and screening context**

   Prompt: `Retrieve no more than 25 water observations of exact characteristic “Specific conductance” from 2023 through 2025 at USGS-03245500. Also retrieve Freshwater Explorer predicted-background conductivity only for the declared bounding box. Keep their evidence labels distinct.`

   Expected tool calls:

   ```json
   {"name":"wqp_measurements","arguments":{"query":{"scope":{"station_ids":["USGS-03245500"]},"characteristic_names":["Specific conductance"],"start_date":"2023-01-01","end_date":"2025-12-31","result_limit":25}}}
   {"name":"freshwater_screening_baseline","arguments":{"bounding_box":{"west":-84.32,"south":39.15,"east":-84.27,"north":39.20},"max_records":25}}
   ```

   The rendered packet matches Freshwater Explorer's `COMID` to the selected NHDPlusID only for display context. It never re-labels modelled background as a WQP observation.

5. **State the bounded answer correctly**

   Prompt: `Compare the returned observation range to the Freshwater Explorer context as screening only. Cite each source query and say what cannot be concluded.`

   Required labels:

   - **Observation** — raw WQP records, units, qualifiers, methods, and cap/truncation state retained.
   - **Coverage summary** / **Station inventory** — availability evidence, not concentrations.
   - **Screening baseline** — Freshwater Explorer modelled context, not a current observation or criterion.
   - **Assessment context — not retrieved** — the default packet states this explicitly because ATTAINS requires `ATTAINS_API_KEY`; it does not make or imply an assessment finding.

## Failure and ambiguity behavior

- **The river candidate is missing or differs:** stop. Pick a returned candidate and declare a new explicit scope; do not silently substitute a nearby reach.
- **WQP coverage is empty:** report that the selected scope has no returned coverage and do not infer a conductivity result. Narrow or move the scope deliberately.
- **The observation request is truncated:** display `truncated: true` and narrow dates or retain only the selected station before requesting another bounded slice.
- **Freshwater Explorer has no matching COMID:** keep its records as area-level screening context or say the selected reach was not matched. Do not invent a baseline.
- **Units, methods, dates, or qualifiers are not comparable:** show them and decline the numerical comparison.
- **ATTAINS lacks a key:** omit assessment context from the demo; do not use a secret in a prompt, a URL, or source control.

## Reset

The server is stateless except for the local WQP DuckDB cache. Each invocation starts a fresh stdio server. To force a fresh WQP retrieval rather than a cached result, wait for the one-hour cache TTL or remove the local cache directory outside the repository:

```bash
rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/watershed-evidence-mcp"
```

That reset only clears local cached public responses. It does not alter any upstream service.

## Inspector configuration (optional)

Use this server configuration in an MCP Inspector-compatible client, replacing the directory with the local clone path:

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

Run the same sequence above. The Python script is the canonical reproducible client path because it exercises the same MCP transport and produces the labelled packet automatically.
