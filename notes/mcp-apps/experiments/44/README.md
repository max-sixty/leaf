# Experiment 44: Direct resource with the working browser driver

## Purpose

Repeat experiment 43 with Playwright's Node executable selected explicitly.
Expected outcomes remain those of experiment 36.

## Findings

The host started, but the Python MCP process stalled loading the native
pydantic_core extension. A timed faulthandler dump isolated that import.
The Python browser driver also produced no result. Experiment 45 uses the
official Node MCP SDK and JavaScript Playwright, retaining Python only for
Leaf's existing state and event owners. No MCP UI has been observed yet.
