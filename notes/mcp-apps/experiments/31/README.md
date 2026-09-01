# Experiment 31: Installed Codex presentation boundary

## Purpose

Test whether the installed Codex host attaches registered Leaf MCP Apps, whether
it distinguishes multiple resource URIs from one MCP server, and keep resource
attachment separate from the nested page's localhost policy.

**Configuration:**

- A fresh projectless Codex task with the installed Leaf plugin from main.
- The model-visible `leaf_present` and `leaf_present_snapshot` tools.
- One older initialized page whose vendored registry omitted the current
  `pickup` event kind, followed by a freshly initialized compatible page.

**Expected outcomes:**

- A stale vendored layer produces a readable compatibility refusal.
- A compatible tool result attaches its bound MCP App resource when the task is
  viewed.
- The complete app attempts its exact localhost frame only after the host runs
  the matching full-page bundle.

## Findings

Both tools were registered against the older page, but each returned only its
generic `Error executing tool ...` text and attached no app. Replaying that page
through the shipped stdio server exposed the hidden exception: source validation
reported that `$events.kinds` omitted `pickup`, `PageStateService` returned
`browser=None`, and both presentation summaries indexed
`state["browser"]["basis"]`. The required compatibility behavior is a readable
`ToolError` that names the stale layer and the `leaf page init` repair.

Both tools then completed successfully against a freshly initialized compatible
page. `leaf_present` returned its ready-at-Draft text and
`leaf_present_snapshot` returned ready-at-r1. The first report that neither app
attached was invalid because the completed probe task was still in the
background. When the desktop navigated to that task, logs at 18:24:25–27 recorded
`sandbox_requested`, `guest_attached`, `widget_frame_committed`, and
`widget_running` for both tool call ids.

The host had logged exactly one `mcpServer/resource/read` after both calls, and
both widgets used the same server-level sandbox source,
`source-898a63e66648a40b`. Direct stdio reads showed that Leaf's two registered
URIs returned distinct, correct HTML blobs. The shared host HTML was demonstrably
the snapshot bundle: the `Leaf present snapshot` card rendered the authored
`Codex MCP Apps probe` content and controls, while the primary `Leaf present`
card showed `rundefined · event undefined` and then
`Cannot read properties of undefined (reading 'replaceAll')` when that renderer
received the full-page result.

This run proves that Codex renders Leaf Apps lazily and that the snapshot works
inline. It also proves that this host chooses or caches one UI resource per MCP
server rather than preserving Leaf's two URI bindings. The primary failed before
its nested localhost frame could be attempted, so the run gives no evidence for
or against Codex's private-network or frame policy.
