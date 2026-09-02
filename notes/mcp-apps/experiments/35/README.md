# Experiment 35: Full Leaf in Codex's browser pane

## Purpose

Test the full canonical runtime in Codex, not the comments-only MCP fallback.
Experiment 34 established the inline app's capability gate; this run changes the
presentation surface to Codex's built-in browser and retains the same page log
and detached delivery adapter.

Configuration:

- Checkout: `866891a6a655e14d8930ee5fbee24c0994a3413b`, before handoff-doc changes.
- Task: `01a054d1-f145-7bd3-979a-69e45dd5980d`.
- Fixture: `ship-review`, fresh `codex-full` preview slot.
- Browser: Codex In-app Browser, selected by the browser tool for the preview URL.
- Carrier: `leaf codex start`, with the preview owned by this task.

Expected outcomes:

- The page must render its real theme, package controls, thread panel, and
  versions. A tool success or snapshot does not satisfy that test.
- A real keyboard option change and anchored comment must append normal events
  and be accepted by the originating task's durable queue.
- The queued input must reach a later task turn. An acknowledgement alone proves
  queue acceptance, not that the task processed the input.
- A reply and source revision must become visible in the same page. Reload and
  version travel must preserve the relevant standing state.

## Findings

The preview launch and first keyboard gesture preceded this written protocol;
their exact commands are preserved in `commands.sh` and `browser.js`.

- The actual Codex browser pane rendered the canonical theme, task tree, version
  controls, and thread panel including its frozen multi-select widget. See
  `results/full-leaf-codex.png`.
- Body readiness was `data-lf-upgraded=1`, `data-lf-presented=1`; the action
  advanced `data-lf-applied` to `3`.
- Pressing Space on the second page option selected it and appended action
  `e0ecf4df96cde810366f1bbbe70b3a54`, sequence 11. Its pickup was sequence 12.
- A real text selection and Enter submitted a comment anchored to “reconnect”,
  with prefix and suffix. Comment `8dec5efbdfc8fe3869338ea2f66d16c2` is sequence
  13; its pickup is sequence 14.
- Browser warning/error logs were empty after both gestures.
- Delivery `d6d12a18-d7bf-5d97-be9a-8c8036449b94` started a later turn of the
  originating task with sequence 11. The task read that persisted batch, carried
  the choice into authored markup, and added a test-result note. The same open
  Codex tab displayed revision 2 automatically and kept the choice selected.
- The revised page passed `version check --render` in light and dark Chrome and
  was stamped v2. A reload of the actual Codex tab kept the selected choice.
- Version travel opened `/versions/v1.html?pin=` without the new result note,
  while retaining the standing choice. Selecting v2 restored the note. The tab
  was returned to the original live URL, with no warning/error logs.
- Delivery `aac11a1f-759c-5c98-9031-aa2fbca93f41` then started a separate later
  turn with comment sequence 13. The task read the exact batch and replied with
  `a691224aa4369d25198ad4000b282c07`. The actual Codex tab displayed the reply
  under the original “reconnect” anchor; see `results/returned-comment.png`.
- The final test-result note appeared through live revision 3, stamped v3.
  Final page state had no source error, pending events, unacknowledged events,
  or markup lag. The adapter remained listening and the page was left waiting.
- The focused session/MCP/layer tests passed: 254 in 83.18 seconds. The everyday
  suite passed: 791 in 238.33 seconds. Pre-commit passed after formatting the
  authored example and browser transcript; the derived corpus was regenerated.

## Conclusion

The browser-pane route runs the full canonical Leaf runtime inside Codex and
returns real gestures to the same task without a visible watcher task or an
MCP message-based wake. This run verified option and anchored-comment round
trips, source updates, replay after reload, and version travel. It did not test
every package widget or establish full inline MCP support. No runtime or
transport replacement was needed; the change is the default handoff workflow
and its evidence standard.

The handoff instruction evaluation also found that a successful tool result's
model-visible text cannot identify the rendered app mode. The revised default
uses the browser page; explicit inline experiments report the observed mode or
unverified rendering, without manually forcing the snapshot merely because the
model received text.
