# Experiment 39: Direct resource with explicit npm entrypoint

## Purpose

Repeat experiment 38, invoking npm through Node rather than its shebang.
The expected outcomes and MCP transport are unchanged from experiment 36.

## Findings

Dependencies installed and the fixture initialized. The WASM compiler failed
under Homebrew Node 26.8.1 with `RangeError: Invalid array length` in its
stdio stream adapter, followed by `The service was stopped`. No HTML bundle was
produced. Experiment 40 uses the Codex-bundled Node runtime with these same
installed dependencies.
