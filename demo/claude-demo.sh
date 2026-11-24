#!/usr/bin/env bash
# Launch Claude Code for the recorded demo: only the watershed-evidence MCP server, plus
# Read (to open large tool results Claude Code saves to disk) and Write limited to
# demo/out/ (for the evidence packet). Those are pre-approved so no permission prompt
# interrupts the recording. Run from the repository root.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p demo/out

exec claude \
  --mcp-config demo/mcp.json \
  --strict-mcp-config \
  --permission-mode default \
  --tools "Read,Write" \
  --allowedTools "mcp__watershed-evidence" "Read" "Edit(demo/out/**)" \
  --append-system-prompt "This session is being recorded as a demo of the watershed-evidence \
MCP server. Get data only from its tools. Call the tools one at a time, and after each call \
write one short line saying what it returned (counts, identifiers, value ranges), never raw \
JSON. If a tool result is saved to a file because it is large, read that file, then write \
the same one-line summary for it. When asked \
to save an evidence packet, write Markdown with these sections: Question, Scope, \
Observations (a table of the returned results with date, value, unit, and qualifier), \
Screening context, Comparison, Caveats, and Provenance (source, retrieval time, and query \
URL for every call). Keep the chat answer short, and do not mention tests, linting, or \
changed files. End your final message with a line that \
reads exactly: End of evidence summary."
