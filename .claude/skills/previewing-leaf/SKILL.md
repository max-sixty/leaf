---
name: previewing-leaf
description: Opens a shipped example for interactive review while developing Leaf. Use when the user asks to preview an example in Codex or comment on it with Codex or Leaf annotations.
---

# Preview a Leaf example

This workflow reviews the examples and runtime in the current Leaf checkout. A
request to use Leaf for another subject belongs to the installed Leaf skill.

1. From the repository root, start `scripts/preview.py <example>` in a
   long-running command or terminal session. Keep it alive and retain the exact
   served URL. The script replaces `.tmp/preview`, so one checkout has one active
   example preview.
2. In Codex, call `mcp__codex_app__open_in_codex` with the served URL as a browser
   target and `placement: "right"`.
3. Run `bin/leaf codex start .tmp/preview` so Leaf comments return to the current
   task.
4. Tell the user to select page text or use Leaf's comment affordance for a Leaf
   thread. Codex Annotation mode creates visual comments; the user sends those
   comments with their next chat message.

Keep the URL in the handoff. Use the Codex review pane when feedback belongs to
a source line rather than the rendered example.
