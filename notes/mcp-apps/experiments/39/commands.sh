#!/bin/bash
set -e
repo="$(git rev-parse --show-toplevel)"
cd "$repo"
results="$repo/notes/mcp-apps/experiments/39/results"
run_dir="$(mktemp -d "$repo/.tmp/mcp-direct-39.XXXXXX")"
reference="/tmp/leaf-mcp-apps-reference-10195ad9"
mkdir -p "$results"
printf '%s\n' "$run_dir" > "$results/run-dir.txt"
node /opt/homebrew/lib/node_modules/npm/bin/npm-cli.js install --prefix "$run_dir" --no-save --no-package-lock --silent esbuild-wasm@0.28.2 @modelcontextprotocol/ext-apps@1.7.5
/bin/sh "$repo/bin/leaf" page init "$run_dir/page"
cp examples/design-decision.html "$run_dir/page/index.html"
/bin/sh "$repo/bin/leaf" version stamp "$run_dir/page" --text "Direct MCP resource probe"
node scripts/mcp-app/direct-build.mjs "$run_dir/page" "$run_dir/node_modules" "$run_dir/bundle.js"
shasum -a 256 "$run_dir/bundle.js" > "$results/bundle.sha256"
server_pid=""
host_pid=""
cleanup() {
  if [ -n "$host_pid" ]; then kill "$host_pid" 2>/dev/null || true; fi
  if [ -n "$server_pid" ]; then kill "$server_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT
uv run python scripts/mcp-app/direct.py --page "$run_dir/page" --bundle "$run_dir/bundle.js" \
  --observations "$results/observations.jsonl" --http-port 3001 > "$results/mcp-server.log" 2>&1 &
server_pid=$!
(
  cd "$reference/examples/basic-host"
  exec env SERVERS='["http://localhost:3001/mcp"]' bun serve.ts
) > "$results/reference-host.log" 2>&1 &
host_pid=$!
for _ in {1..60}; do
  if curl --silent --fail http://localhost:8080/api/servers >/dev/null; then break; fi
  sleep 0.5
done
curl --silent --fail http://localhost:8080/api/servers >/dev/null
uv run python notes/mcp-apps/experiments/36/observe.py "$run_dir/page" "$results" > "$results/reference-host.json"
# Inspect: jq . "$results/reference-host.json"
