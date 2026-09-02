# Experiment 40: Direct resource with bundled Node

## Purpose

Repeat experiment 39's build and host check with the Codex-bundled Node runtime.
Reuse its initialized fixture and pinned dependencies; no browser interaction
has yet touched the fixture. Expected outcomes are unchanged from experiment 36.

## Findings

The bundled Node executable also stalled before producing its version or
starting the build. No MCP evidence was collected. Experiment 41 uses the
working Homebrew Node with the compiler's in-process browser/WASM API, avoiding
native subprocess startup and the Node stdio adapter entirely.
