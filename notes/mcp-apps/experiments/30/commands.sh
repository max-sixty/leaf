#!/bin/bash
set -e
repo="$(git rev-parse --show-toplevel)"
cd "$repo"

results="$repo/notes/mcp-apps/experiments/30/results"
run_dir="$(mktemp -d "$repo/.tmp/mcp-app-experiment-30.XXXXXX")"
page_dir="$run_dir/page"
reference="/tmp/leaf-mcp-apps-reference-10195ad9"
server_pid=""
host_pid=""

cleanup() {
  if [ -n "$host_pid" ]; then kill "$host_pid" 2>/dev/null || true; fi
  if [ -n "$server_pid" ]; then kill "$server_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT

mkdir -p "$results"
uv run pytest -n0 tests/test_mcp_app.py tests/test_interact_mcp.py tests/test_render_mcp.py

./bin/leaf page init "$page_dir"
cp examples/design-decision.html "$page_dir/index.html"
./bin/leaf version stamp "$page_dir" --text "Exact-origin MCP page"
shasum -a 256 skills/leaf/assets/vendor/mcp-page-app.html >"$results/bundle.sha256"

test "$(git -C "$reference" rev-parse HEAD)" = "10195ad91851502134930e9b80ec2c04e277a720"
(cd "$reference" && npm run build --workspace @modelcontextprotocol/ext-apps-basic-host >/dev/null)

uv run python notes/mcp-apps/experiments/1/serve.py >"$results/mcp-server.log" 2>&1 &
server_pid=$!
(
  cd "$reference/examples/basic-host"
  exec env SERVERS='["http://localhost:3001/mcp"]' bun --watch serve.ts
) >"$results/reference-host.log" 2>&1 &
host_pid=$!

for _ in {1..60}; do
  if curl --silent --fail http://localhost:8080/api/servers >/dev/null; then break; fi
  sleep 0.5
done
curl --silent --fail http://localhost:8080/api/servers >/dev/null

uv run python notes/mcp-apps/experiments/30/observe.py "$page_dir" \
  >"$results/reference-host.json"
