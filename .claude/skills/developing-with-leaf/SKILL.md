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
When a visual or content artifact would help the developer judge the work,
generally put a draft in front of them during exploration or at handoff rather
than relying on a description alone.
Preview a shipped example when the request names one or that handoff requires
interactive proof. Otherwise author or revise a page.

Before presenting a served page or visible runtime change as finished, inspect
the exact served URL. When the subject is Leaf's own interface, the demonstrated
surface must come from its owning runtime and theme through a shipped example or
fixture; page-local HTML and CSS may frame it, but must not imitate it. Call an
unimplemented imitation a sketch, not a preview. Confirm the expected content,
review the changed surface at a representative viewport, and check the browser
console. Navigate to the heading that owns the changed surface and hand off the
exact URL including its fragment. Use a stable authored heading id; if the heading
has none, add one to the source rather than relying on `lf-toc`'s position-derived
target. Keep the process alive. Use the Codex review pane when feedback belongs to
a source line.

## Preview a shipped example

1. From the repository root, start `scripts/preview.py <example>` in a
   long-running command or terminal session. Keep it alive and retain the exact
   served URL. The script watches source and runtime edits and preserves feedback
   at `.tmp/previews/<example>`. Repeating the command reuses that preview; use
   `--slot <name>` for another copy. A refused update appears in the terminal or
   the background log named at startup. Fix the input and the watcher retries.
2. In Codex, call `mcp__codex_app__open_in_codex` with that heading's fragment
   URL as a browser target and `placement: "right"`.
3. Run `<root>/bin/leaf codex start <root>/.tmp/previews/<example>` so Leaf comments return
   to the current task.
4. Tell the user to select page text or use Leaf's comment affordance for a Leaf
   thread. Codex Annotation mode creates visual comments that the user sends with
   their next chat message.

When finished with a preview, run the matching preview command with `--stop`; it
waits for the watcher and service to stop. Ctrl-C stops a foreground preview.
Changing an occupied slot to a different source or seeded history requires a new
slot; the existing page and feedback are retained.

## Compare runtime versions

Choose one authored source and serve it through two named preview slots:

```bash
scripts/preview.py --source <source.html> --runtime <baseline-root> \
  --slot baseline --background
scripts/preview.py --source <source.html> --runtime <candidate-root> \
  --slot candidate --background
```

Each command verifies the checkout launcher, prepares or resumes its independent
page, watches that runtime and source, and prints its exact URL. Exercise the same journey and viewport at
both URLs, check both browser consoles, then navigate both to the same authored
heading id and open those exact fragment URLs as Codex browser targets. Hand off
the labeled URL pair and the action that reveals the difference.

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
