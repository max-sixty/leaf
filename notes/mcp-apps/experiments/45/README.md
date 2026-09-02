# Experiment 45: Node MCP carrier with Leaf's Python authority

## Purpose

Repeat experiment 44 without the native Python MCP/browser dependencies that
stalled at import. The official Node MCP SDK serves the same HTML resource;
a JSON-lines worker delegates directly to PageStateService and EventEndpoint.
JavaScript Playwright drives Chrome. The resource and expected user behavior
remain those of experiment 36.

## Findings

The bundle and Node MCP server started successfully. Browser launch did not
complete before the app restart. No rendering or gesture evidence was obtained.
