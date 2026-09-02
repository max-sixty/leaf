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

From the checkout root, use a new experiment number:

```sh
bash scripts/mcp-app/run-direct-probe.sh 57
```

Each run creates a fresh page and writes its evidence under
`notes/mcp-apps/experiments/<number>/results/`. Existing results are never
overwritten. The runner stops its servers on completion; `--keep-live` keeps
the passing preview open until Ctrl-C. Ports 3001, 8080, and 8081 must be free.

The fixed page's runtime, theme, and default widget modules are bundled.
Version navigation, new layer assets, and dynamic external data are not yet
carried by this transport.
