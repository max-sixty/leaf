# Experiment 15: Reference-host full-page retry

## Purpose

Capture and correct the tool-call discrepancy that stopped experiment 14, then
repeat the same complete-page probe.

**Changes from experiment 14:**

- Record the reference host's selected tool, input text, and rendered call error
  before waiting for the app's nested page.
- Change no frame CSP, server lifetime, or app layout until the rejected tool
  argument is explained.

**Expected outcomes:**

- If the harness targeted the wrong control or tool, the captured host state
  identifies it and the corrected call reaches the page resource.
- If the host serializes the page input differently from stdio, the returned
  validation error identifies the concrete mismatch.
- Once the tool call succeeds, the original experiment 14 frame and interaction
  expectations run unchanged.

## Findings

The diagnostic run confirmed experiment 14's rejected `page` was a harness
race: the earlier script wrote the input while the reference host was still
initializing the tool, and `handleServerSelect` subsequently restored `{}`.

This run stopped at the next initialization boundary. Playwright began waiting
on the empty tool `<select>` before React populated its options; the timeout
snapshot then showed both visible tools and `leaf_open_page` selected. No tool
call was made, so this run still provides no loopback frame evidence. Experiment
16 waits for the expected tool options before selecting, filling, and calling.
