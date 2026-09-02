# Experiment 37: Direct resource with explicit launchers

## Purpose

Repeat experiment 36 using `/bin/bash` and `/bin/sh` explicitly. Its shell
stalled before starting the experiment. The runtime, server, fixture, and
expected outcomes are unchanged; see experiment 36.

## Findings

The fixture initialized and stamped successfully. Native esbuild did not start:
its service process stayed at zero CPU and zero accumulated time, and even a
separate `esbuild --version` stalled. No resource was built or loaded. Repeat
with the pinned WebAssembly build of the same compiler in experiment 38.
