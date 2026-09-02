#!/bin/bash
set -e
cd "$(git rev-parse --show-toplevel)"
/bin/bash scripts/mcp-app/run-direct-probe.sh 43
# Inspect: jq . notes/mcp-apps/experiments/43/results/reference-host.json
