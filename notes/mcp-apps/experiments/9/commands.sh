#!/bin/bash
set -e
repo="$(git rev-parse --show-toplevel)"
cd "$repo"

results="$repo/notes/mcp-apps/experiments/9/results"
run_dir="$(mktemp -d "$repo/.tmp/mcp-app-experiment-9.XXXXXX")"
mkdir -p "$results"

./bin/leaf page init "$run_dir/page"
cp examples/design-decision.html "$run_dir/page/index.html"
./bin/leaf version check "$run_dir/page"

uv run python notes/mcp-apps/experiments/9/observe.py "$run_dir/page" \
  >"$results/stdio.json"
