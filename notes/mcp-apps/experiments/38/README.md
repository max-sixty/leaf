# Experiment 38: Direct resource with the WASM compiler

## Purpose

Repeat experiment 37 with `esbuild-wasm@0.28.2`, since both native compiler
service startup and `--version` stalled. The Leaf fixture and MCP transport are
unchanged. The expected outcomes remain those of experiment 36.

## Findings

The dependency-install process stalled before executing npm: sampling showed
`/usr/bin/env` held at `_dyld_start` with zero accumulated CPU time. Invoking
npm's JavaScript entry with Node directly works. No MCP evidence was collected.
Experiment 39 uses that explicit entrypoint.
