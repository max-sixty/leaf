# Experiment 21: Partitioned Leaf session inside MCP Apps

## Purpose

Keep Leaf's token gate intact while making its per-page browser session valid in
a third-party MCP App frame.

**Changes from experiment 20:**

- The process-scoped MCP page server sets its token cookie as
  `SameSite=None; Secure; Partitioned`.
- Its URL and declared frame origin use `localhost`, where browsers permit the
  secure loopback exception; ordinary Leaf servers remain `SameSite=Strict`.
- The host harness addresses the already-rendered Tool Input disclosure by its
  stable title instead of an emoji-split text locator.

**Expected outcomes:**

- CSS, runtime, state stream, and event POST all carry the partitioned token.
- The normal Leaf page reaches its three readiness stamps inside the MCP App.
- Inline and fullscreen measurements, accessibility, console output, and a
  keyboard choice establish the first end-to-end full-interface result.

## Findings

The tool call and app loaded with no 403 responses or other Leaf resource errors,
so the secure partitioned cookie crossed the third-party boundary that stopped
experiment 20. The harness then failed while locating the `<pre>` inside an
already-expanded Tool Input disclosure, even though the host body and
accessibility tree contained the exact submitted path. Experiment 22 records
that body-level call evidence directly and continues to Leaf readiness.
