#!/bin/bash
set -e
repo="$(git rev-parse --show-toplevel)"
cd "$repo"
results="$repo/notes/mcp-apps/experiments/40/results"
run_dir="$repo/.tmp/mcp-direct-39.OFIW1G"
reference="/tmp/leaf-mcp-apps-reference-10195ad9"
node_runtime="/Users/maximilian/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
mkdir -p "$results"
"$node_runtime" scripts/mcp-app/direct-build.mjs "$run_dir/page" "$run_dir/node_modules" "$run_dir/bundle.js"
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
  exec env SERVERS='["http://localhost:3001/mcp"]' /Users/maximilian/.bun/bin/bun serve.ts
) > "$results/reference-host.log" 2>&1 &
host_pid=$!
for _ in {1..60}; do
  if curl --silent --fail http://localhost:8080/api/servers >/dev/null; then break; fi
  sleep 0.5
done
curl --silent --fail http://localhost:8080/api/servers >/dev/null
uv run python notes/mcp-apps/experiments/36/observe.py "$run_dir/page" "$results" > "$results/reference-host.json"
# Inspect: jq . "$results/reference-host.json"
