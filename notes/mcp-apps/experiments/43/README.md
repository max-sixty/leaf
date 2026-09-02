# Experiment 43: Direct resource in the upstream host on Node

## Purpose

Repeat experiment 42 with Node running the unmodified upstream Express host.
This changes its launcher, not its browser code, CSP, or MCP bridge. The
expected outcomes remain those of experiment 36.

## Findings

The resource built and the unmodified upstream host started on ports 8080 and
8081. The browser observer produced no result before interruption. Experiment
44 selects the working Node executable through Playwright's supported
`PLAYWRIGHT_NODEJS_PATH` override. No rendered UI was observed in this attempt.
