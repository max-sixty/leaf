#!/bin/bash
set -euo pipefail

usage() {
  printf '%s\n' "Usage: $0 EXPERIMENT_NUMBER [--keep-live]" >&2
  exit 2
}
[[ $# -ge 1 && $# -le 2 && $1 =~ ^[1-9][0-9]*$ ]] || usage
keep_live=false
if [[ $# == 2 ]]; then
  [[ $2 == --keep-live ]] || usage
  keep_live=true
fi

repo="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo"
results="$repo/notes/mcp-apps/experiments/$1/results"
if [[ -e "$results" ]]; then
  printf 'Results already exist: %s\nUse a new experiment number.\n' "$results" >&2
  exit 1
fi
mkdir -p "$repo/.tmp" "$results"
run_dir="$(mktemp -d "$repo/.tmp/mcp-direct-$1.XXXXXX")"
dependencies="$repo/.tmp/mcp-direct-deps-1.7.5-0.28.2"
modules="$dependencies/node_modules"
reference_sha=10195ad91851502134930e9b80ec2c04e277a720
# The reference host's absolute sendFile path rejects hidden parent directories.
# A checkout under .tmp/ or .codex/ makes its sandbox route return 404.
reference="$(mktemp -d)"
# npm workspace resolution needs the physical path (macOS /var is a symlink).
reference="$(cd "$reference" && pwd -P)"
printf '%s\n' "$run_dir" > "$results/run-dir.txt"
printf '%s\n' "$reference" > "$results/reference-dir.txt"

# Like vendor.py, pin direct npm inputs and keep fetched dependencies out of
# the plugin payload. The reference host supplies its own committed lockfile.
npm install --prefix "$dependencies" --no-save --no-package-lock --no-audit --no-fund \
  esbuild-wasm@0.28.2 @modelcontextprotocol/ext-apps@1.7.5
git -C "$reference" init --quiet
git -C "$reference" remote add origin https://github.com/modelcontextprotocol/ext-apps.git
git -C "$reference" fetch --depth 1 origin "$reference_sha"
git -C "$reference" checkout --detach "$reference_sha"
test "$(git -C "$reference" rev-parse HEAD)" = "$reference_sha"
git -C "$reference" diff --exit-code HEAD
npm --prefix "$reference" ci --no-audit --no-fund
npm --prefix "$reference" run build --workspace @modelcontextprotocol/ext-apps-basic-host

/bin/sh "$repo/bin/leaf" page init "$run_dir/page"
cp examples/design-decision.html "$run_dir/page/index.html"
/bin/sh "$repo/bin/leaf" version stamp "$run_dir/page" --text "Direct MCP resource probe"
/bin/sh "$repo/bin/leaf" status "$run_dir/page" idle "Transport probe; no agent wake attached"
shasum -a 256 scripts/mcp-app/direct-build.mjs scripts/mcp-app/direct-entry.js scripts/mcp-app/direct.py scripts/mcp-app/direct-server.mjs scripts/mcp-app/check-direct-http.mjs scripts/mcp-app/observe-direct.mjs scripts/mcp-app/run-direct-probe.sh > "$results/source.sha256"
node scripts/mcp-app/direct-build.mjs "$run_dir/page" "$modules" "$run_dir/bundle.js"
shasum -a 256 "$run_dir/bundle.js" > "$results/bundle.sha256"
server_pid=""
host_pid=""
cleanup() {
  if [ -n "$host_pid" ]; then kill "$host_pid" 2>/dev/null || true; fi
  if [ -n "$server_pid" ]; then kill "$server_pid" 2>/dev/null || true; fi
  if [ -n "$host_pid" ]; then wait "$host_pid" 2>/dev/null || true; fi
  if [ -n "$server_pid" ]; then wait "$server_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
node scripts/mcp-app/direct-server.mjs "$run_dir/page" "$run_dir/bundle.js" \
  "$modules" "$results/observations.jsonl" 3001 > "$results/mcp-server.log" 2>&1 &
server_pid=$!
(
  cd "$reference/examples/basic-host"
  export SERVERS='["http://localhost:3001/mcp"]'
  export HOST_PORT=8080 SANDBOX_PORT=8081
  exec node serve.ts
) > "$results/reference-host.log" 2>&1 &
host_pid=$!
for _ in {1..60}; do
  kill -0 "$host_pid"
  kill -0 "$server_pid"
  if curl --silent --fail http://localhost:8080/api/servers >/dev/null && curl --silent --fail http://localhost:8081/sandbox.html >/dev/null && curl --silent --fail http://localhost:3001/health > "$results/health.json"; then break; fi
  sleep 0.5
done
curl --silent --fail http://localhost:8080/api/servers >/dev/null
curl --silent --fail http://localhost:8081/sandbox.html >/dev/null
kill -0 "$host_pid"
kill -0 "$server_pid"
jq -e --arg page "$run_dir/page" '.page == $page' "$results/health.json"
node scripts/mcp-app/check-direct-http.mjs http://127.0.0.1:3001 > "$results/http-security.json"
node scripts/mcp-app/observe-direct.mjs "$run_dir/page" "$results" > "$results/reference-host.json"
printf 'Probe passed. Results: %s\n' "$results"
if $keep_live; then
  printf '%s\n' 'Preview: http://localhost:8080/?tool=leaf_direct_present&server=leaf-direct-probe&call=true' \
    'Press Ctrl-C to stop the probe servers.'
  while kill -0 "$host_pid" && kill -0 "$server_pid"; do sleep 1; done
  printf '%s\n' 'A probe server exited.' >&2
  exit 1
fi
