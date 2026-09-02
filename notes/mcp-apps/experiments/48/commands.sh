#!/bin/bash
set -e
repo="$(git rev-parse --show-toplevel)"
cd "$repo"
results="$repo/notes/mcp-apps/experiments/48/results"
run_dir="$(cat notes/mcp-apps/experiments/47/results/run-dir.txt)"
mkdir -p "$results"
node scripts/mcp-app/direct-server.mjs "$run_dir/page" "$run_dir/bundle.js" \
  "$repo/.tmp/mcp-direct-39.OFIW1G/node_modules" "$results/observations.jsonl" 3001 > "$results/mcp-server.log" 2>&1 &
server_pid=$!
(
  cd /Users/maximilian/workspace/leaf-ext-apps-reference/examples/basic-host
  export SERVERS='["http://localhost:3001/mcp"]'
  exec node serve.ts
) > "$results/reference-host.log" 2>&1 &
host_pid=$!
trap 'kill "$host_pid" "$server_pid" 2>/dev/null || true' EXIT
wait
# UI: http://localhost:8080/?tool=leaf_direct_present
# Inspect: cat notes/mcp-apps/experiments/48/results/observations.jsonl
