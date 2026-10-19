# Security

## Posture (hackathon prototype, public data only)

- Read-only: no write endpoints, no credential management, no user data.
- Over HTTP (`PORT` or `MCP_TRANSPORT=streamable-http`), `/mcp` has **no authentication**,
  matching the public-data pilot posture. Front it with authentication and review agency
  ATO requirements before any non-hackathon use.
- `ATTAINS_API_KEY` is the operator's api.data.gov key, supplied only as a runtime
  environment variable. Because `/mcp` is unauthenticated, any caller spends that key's
  rate quota. It is sent only as the `X-Api-Key` header and never appears in responses,
  logs, fixtures, or the container image (`.dockerignore` excludes `.env`).
- Outbound requests go only to fixed EPA/WQP origins through `JsonHttpClient`, with a 20 s
  timeout, 10 MB cap, and content-type checks. No tool accepts a caller-supplied URL.
- Run a single process: the DuckDB result cache holds a file lock. In containers the cache
  lives under `XDG_CACHE_HOME` (`/tmp/cache`) and is ephemeral.

## Reporting

Report vulnerabilities per the GSA Vulnerability Disclosure Policy.
