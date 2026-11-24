# Records Claude Code answering a bounded water-quality question through the
# watershed-evidence MCP server (the Little Miami flow in docs/little-miami-demo.md).
#
# Run from the repository root:
#
#   uv sync --locked
#   vhs demo/watershed.tape
#
# Needs vhs (with ttyd and ffmpeg) and a signed-in `claude` on PATH. Each run sends
# real model requests on your Claude account and calls live public services (WQP,
# EPA WATERS, Freshwater Explorer), so the answer and its timing vary between runs.
# Claude saves its evidence packet to demo/out/ and the tape then opens it in ranger and
# nano (both must be installed). The rendered video is written to demo/watershed-demo.mp4.
# Both outputs are git-ignored.

Output demo/watershed-demo.mp4

Require claude
Require uv
Require ranger
Require nano

Set Shell "bash"
Set FontSize 18
Set Width 1600
Set Height 1000
Set Padding 24
Set Framerate 30
Set TypingSpeed 30ms
Set Theme "Catppuccin Mocha"

# Start Claude Code off camera, with read-only nano as the editor ranger opens files in.
Hide
Type "export EDITOR=nano VISUAL='nano --view --softwrap' && rm -f demo/out/little-miami-evidence.md"
Enter
Type "clear && demo/claude-demo.sh"
Enter
Wait+Screen@60s /Claude Code v/
Sleep 5s
Show

Sleep 2s

# Show that the server is connected and what it exposes.
Type "/mcp"
Sleep 1s
Enter
Sleep 4s
Escape
Sleep 1s

Type "Is specific conductance elevated in the Little Miami River near Milford, Ohio? "
Type "Resolve the river name first, then scope to the box west -84.32, south 39.15, "
Type "east -84.27, north 39.20. Check WQP coverage there, then pull at most 50 "
Type "Specific conductance results from station USGS-03245500 for 2025 "
Type "(that station is already chosen, so skip the station inventory). "
Type "Compare them with at most 25 Freshwater Explorer predicted-background records for the box. "
Type "Keep observations and screening context separate, and cite sources. "
Type "Save the evidence packet to demo/out/little-miami-evidence.md."
Sleep 1s
Enter

# claude-demo.sh asks Claude to finish with this line, which marks the end of the turn.
Wait+Screen@8m /End of evidence summary/
Sleep 8s

# Leave Claude Code off camera, then open the saved packet in ranger.
Hide
Type "/exit"
Sleep 1s
Enter
Sleep 3s
Type "clear"
Enter
Sleep 1s
Show
Type "ranger --clean --selectfile=demo/out/little-miami-evidence.md"
Sleep 500ms
Enter
# ranger's status bar shows the folder total ("6.8K sum") once it has drawn.
Wait+Screen@20s /sum, /
Sleep 5s

# Open the packet in nano and page through it.
Type "l"
Sleep 5s
Ctrl+V
Sleep 5s
Ctrl+V
Sleep 5s
Ctrl+V
Sleep 5s
Ctrl+V
Sleep 5s
Ctrl+X
Sleep 1s
Type "q"
Sleep 1s
