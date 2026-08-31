# Experiment 17: Complete-page probe after slow discovery

## Purpose

Repeat experiment 16 with enough time for the reference host's MCP discovery to
populate its tool controls.

**Changes from experiment 16:**

- Increase the tool-option hydration barrier from 20 to 60 seconds.
- Leave the resource, frame CSP, server lifetime, fixture, payload assertions,
  and page measurements unchanged.

**Expected outcomes:**

- The host submits the exact page path and the app receives `leaf.page/v1`.
- The loopback frame either renders the normal Leaf runtime or yields the first
  direct evidence that a nested origin is blocked.
- A successful run measures both display modes and authors a real keyboard event
  through Leaf's ordinary HTTP endpoint.

## Findings

The 60-second barrier disproved a slow-discovery explanation. The failure
screenshot shows the fully populated tool select with `leaf_open_page` active,
while Playwright's descendant `option` locator continued to report zero. This is
a faulty harness assertion against the React-controlled select, not a host or
MCP delay. The tool was never called. Experiment 18 waits directly on the
select's value, which is the state the submission handler actually reads.
