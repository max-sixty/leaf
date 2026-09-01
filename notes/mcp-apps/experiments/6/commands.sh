#!/bin/bash
set -e
repo="$(git rev-parse --show-toplevel)"
cd "$repo"

results="$repo/notes/mcp-apps/experiments/6/results"
run_dir="$(mktemp -d "$repo/.tmp/mcp-app-experiment-6.XXXXXX")"
reference="/tmp/leaf-mcp-apps-reference-10195ad9"
server_pid=""
host_pid=""

cleanup() {
  if [ -n "$host_pid" ]; then kill "$host_pid" 2>/dev/null || true; fi
  if [ -n "$server_pid" ]; then kill "$server_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT

mkdir -p "$results"
uv run pytest -n0 tests/test_mcp_app.py

./bin/leaf page init "$run_dir/page"
cp examples/design-decision.html "$run_dir/page/index.html"
./bin/leaf version check "$run_dir/page"

if [ ! -d "$reference/.git" ]; then
  git clone https://github.com/modelcontextprotocol/ext-apps.git "$reference"
  git -C "$reference" checkout 10195ad91851502134930e9b80ec2c04e277a720
fi
test "$(git -C "$reference" rev-parse HEAD)" = "10195ad91851502134930e9b80ec2c04e277a720"
if [ ! -d "$reference/node_modules" ]; then
  (cd "$reference" && npm ci --silent)
fi
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

uv run python notes/mcp-apps/experiments/6/observe.py "$run_dir/page" \
  >"$results/reference-host.json"

# Open the generated compact-app screenshot:
# open notes/mcp-apps/experiments/6/results/compact-ask-420x360.png
