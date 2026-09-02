#!/bin/bash
set -e
cd "$(git rev-parse --show-toplevel)"
/bin/bash scripts/mcp-app/run-direct-probe.sh 50
# Inspect: cat notes/mcp-apps/experiments/50/results/hidden-comment.json
