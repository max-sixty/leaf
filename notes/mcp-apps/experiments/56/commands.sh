#!/bin/bash
set -e
cd "$(git rev-parse --show-toplevel)"
/bin/bash scripts/mcp-app/run-direct-probe.sh 56 --keep-live
# Inspect: jq . notes/mcp-apps/experiments/56/results/reference-host.json
