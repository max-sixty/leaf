# Experiment 41: In-process resource build

## Purpose

Repeat experiment 40 without starting a compiler subprocess. Use the same
compiler version through its browser/WASM API with explicit filesystem loaders.
The runtime, fixture, and MCP behavior remain those of experiment 36.

## Findings

The in-process compiler works. It exposed a probe bug: the widget inventory
included the registry's `$keys` namespace, producing a nonexistent
`/widgets/$keys.js` import. Experiment 42 excludes layer namespaces, matching
the runtime's tag-entry traversal. No host rendering was reached here.
