# Experiment 26: Concrete-frame accessibility probe

## Purpose

Run Axe against the concrete nested Leaf frame, following the proven compact-app
experiment pattern, and complete the durable event check.

**Changes from experiment 25:**

- Pass `page.frames[-1]` to Axe instead of a `FrameLocator`.
- Persist fullscreen dimensions before Axe runs.
- Change no Leaf implementation or browser interaction.

**Expected outcomes:**

- Inline/fullscreen measurements and the host control state survive separately.
- Axe completes against the Leaf document.
- A keyboard choice posts through Leaf's existing server and appears in the
  append-only page log.

## Findings

The full experiment completed. Inline Leaf was 1060×332 and fullscreen was
1068×806; neither had horizontal overflow, and both retained the complete
2,857px document, six headings, five representative widgets, and runtime
readiness. A Space press on Redis appended the ordinary
`session-options / choose / opt-redis` event at sequence 1.

Axe reported one moderate `region` violation, still needing its node detail.
The only console error was the reference host's missing `/favicon.ico`. The
fullscreen return control was hidden because Leaf treated a partial host-context
notification (container dimensions only) as an empty capabilities list.
Experiment 27 preserves capabilities when that field is absent and records the
full Axe report.
