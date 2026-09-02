#!/bin/bash
set -e
cd "$(git rev-parse --show-toplevel)"
/bin/bash scripts/mcp-app/run-direct-probe.sh 55 --keep-live
# Inspect: jq . notes/mcp-apps/experiments/55/results/reference-host.json
