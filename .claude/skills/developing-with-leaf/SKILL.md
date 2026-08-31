---
name: developing-with-leaf
description: Uses the current Leaf repository checkout to author or revise a live page, preview a shipped example, or test worktree changes in the real browser loop.
---

# Develop with the checkout's Leaf

Resolve the repository root three directories above this `SKILL.md`, then resolve
`<root>/bin/leaf` to an absolute path. Run that launcher with `--version` and
continue only when it prints the same repository root. Use the absolute launcher
throughout; a bare `leaf` command may resolve to the installed plugin instead.

Use the visible-change handoff in `<root>/CLAUDE.md` to choose a workflow.
Preview a shipped example when the request names one or that handoff requires
interactive proof. Otherwise author or revise a page.

Before presenting a served page or visible runtime change as finished, inspect
the exact served URL: confirm the expected content, review the changed surface at
a representative viewport, and check the browser console. Hand off that URL and
keep its process alive. Use the Codex review pane when feedback belongs to a
source line.

## Preview a shipped example

1. From the repository root, start `scripts/preview.py <example>` in a
   long-running command or terminal session. Keep it alive and retain the exact
   served URL. The script replaces `.tmp/preview`, so one checkout has one active
   example preview.
2. In Codex, call `mcp__codex_app__open_in_codex` with the URL as a browser
   target and `placement: "right"`.
3. Run `<root>/bin/leaf codex start <root>/.tmp/preview` so Leaf comments return
   to the current task.
4. Tell the user to select page text or use Leaf's comment affordance for a Leaf
   thread. Codex Annotation mode creates visual comments that the user sends with
   their next chat message.

## Author or revise a page

Read `<root>/skills/leaf/SKILL.md` completely and follow its authoring,
validation, handoff, and conversation-loop routes. Use the checkout launcher's
absolute path for every command written there as `leaf`, and resolve its
references from `<root>/skills/leaf/`.

`page init` vendors the checkout's runtime, theme, registry, widgets, and assets
into the page. For an existing page that must exercise the current checkout,
read `<root>/skills/leaf/references/serving-pages.md` and re-vendor it with the
checkout launcher. A served page follows that reference's stop, init, start
sequence. Fix or report a compatibility refusal without falling back to the
installed plugin.
