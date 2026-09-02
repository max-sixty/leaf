#!/bin/bash
set -e
cd "$(git rev-parse --show-toplevel)"
/bin/bash scripts/mcp-app/run-direct-probe.sh 52
# Inspect: jq . notes/mcp-apps/experiments/52/results/reference-host.json
