# Direct MCP Apps probe

`run-direct-probe.sh` bundles the real Leaf runtime into a `ui://` resource,
runs it in the official reference host, and checks rendering, a saved option,
an anchored comment, and `ui/message` acceptance. This does not test Codex's
inline renderer or idle wake-up.

The runner needs Node.js 24+, npm, Git, uv, jq, curl, and a browser: an installed
Chrome, or the first browser on `PATH`. `LEAF_BROWSER_EXECUTABLE`, `CHROME_PATH`, or
`CHROME_BIN` can name another Chromium executable. Initial setup
downloads the pinned SDK and bundler into `.tmp/`, and the reference host into
an OS temporary directory. The host's file-serving policy rejects hidden parent
directories, including `.codex/`; `results/reference-dir.txt` records its location.

From the checkout root, name the experiment being run:

```sh
bash scripts/mcp-app/run-direct-probe.sh 57
```

Each run creates a fresh page and writes its evidence under
`.tmp/mcp-app/experiments/<number>/results/`, replacing whatever that number
wrote before. The probe leaves the tracked tree alone: an install is the tracked
tree and nothing in one reads probe evidence. Copy into
`notes/mcp-apps/experiments/<number>/results/` the part a written-up result cites —
`reference-host.json` and `source.sha256` identify the run in a few hundred
bytes; a screenshot earns its megabyte only where the prose points at it, which
the suite holds over the archive. The runner stops its servers on completion;
`--keep-live` keeps the passing preview open until Ctrl-C. Ports 3001, 8080, and
8081 must be free.

The fixed page's runtime, theme, and default widget modules are bundled.
Version navigation, new layer assets, and dynamic external data are not yet
carried by this transport.
