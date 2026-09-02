# Experiment 42: Direct resource with the correct widget inventory

## Purpose

Repeat experiment 41 excluding `$` namespaces from the widget imports. All
other parameters and expected outcomes remain those of experiment 36.

## Findings

The 3,849,206-byte bundle includes all 15 default upgrade modules and the
canonical runtime. Host startup stalled at Bun before the reference host
listened. Its server is ordinary Express TypeScript, so experiment 43 uses
Node's built-in TypeScript support to run that same unmodified upstream file.
