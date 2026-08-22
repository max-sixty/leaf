---
name: leaf
description: Presents designs, decisions, findings, or live work as an HTML page the user can comment on and manipulate. Use for “explain this in HTML,” “write up the findings,” “show me the options,” or work whose progress or review belongs in a shared page.
allowed-tools:
  - Bash(leaf:*)
---

Present the session's subject as a live HTML page. The user comments on exact
passages, acts through the page's widgets, and follows published revisions in
place. With no subject in `$ARGUMENTS`, use the work already under discussion.

$ARGUMENTS

## Page shape

Three principles apply to every page:

1. **Shape follows the subject.** Use the catalog's structures for things that
   are structured: options for a decision, a board for movable work, milestones
   for stages, metrics for measurements. Prose carries only what prose adds.
2. **A page that asks leaves somewhere to answer.** Put each decision in the
   relevant interactive widget, with the evidence and alternatives beside its
   control. A sign-off page declares sign-off; an informative page does not.
3. **The page keeps up with the work.** Publish when the subject's state changes
   and use status detail for the finer grain between versions. Keep the page's
   waiter alive while work continues so comments can change the next step.

## Location and launcher

Pages conventionally live at `~/.local/state/leaf/pages/<slug>/`, but every
command takes the page directory explicitly. A page directory is live state: it
holds immutable versions, the event log, and its vendored layer. Export or copy
anything that must outlive the page as a deliverable.

Resolve `${CLAUDE_SKILL_DIR}/../../bin/leaf` and use that launcher for every
command shown as `leaf`. Claude Code also puts it on `PATH`. If the resolved file
does not exist, report that the plugin payload is incomplete; in a checkout it is
`plugins/leaf/bin/leaf`.

```bash
leaf page init <page>
leaf page catalog <page>
leaf page media <page> <file>…
leaf page state <page>
leaf version check <page> --render
leaf version publish <page> --version <n> --text "<changelog>"
leaf version export <page> -o <file>
leaf server start <page> [--host NAME] [--standing]
leaf server stop <page>
leaf status <page> working "<detail>"  # also: waiting, idle
leaf report <page> <widget> <verb> name=value…
leaf wait [<page>]
leaf ack <page> <seq>
leaf comment <page> [--quote "<passage>" | --section <id>] --text "…"
leaf reply <page> --to <id> --text "…"
leaf resolve <page> --to <id>
leaf events <page>
leaf transcript <page>
```

## Build and hand over

1. Run `leaf page init <page>`.
2. Run and read `leaf page catalog <page>` before authoring. The vendored
   registry and theme vary by page; do not invent tags, attributes, or idioms.
3. Read `references/page-authoring.md` before writing or revising any version.
   Write the first complete page to `<page>/versions/v1.html`.
4. Start the server with `leaf server start <page>` and retain the exact URL it
   prints. The key in the URL opens the page.
5. Publish with `leaf version publish <page> --version 1 --text "<changelog>"`.
   Publishing runs the static check and refuses invalid markup.
6. Before the first handoff, follow the pre-handover review in
   `references/page-authoring.md`, including
   `leaf version check <page> --render`.
7. Set `leaf status <page> waiting "<what you want back>"`. On an informational
   page with no concrete ask, leave the detail empty; the banner then invites
   the reader to select text to comment. Give the user the URL and one sentence
   naming the available gesture: comment, use a stated control, or approve a
   declared sign-off.
8. Read `references/conversation-loop.md`, then enter the host's wait loop.

Every later handoff includes the URL again. While the next move is yours, set
`working`, keep the wait alive, and publish each meaningful state change. While
the next move is the user's, set `waiting` with the concrete answer or decision
you need, or with empty detail when an informational page asks only for comments.

## Continue and finish

Before running `leaf wait`, processing any delivered batch, opening or replying
to a thread, or ending a page, follow `references/conversation-loop.md`.

The wait owner acknowledges only after a complete batch reaches its next durable
consumer. Process every event in that batch. If the page changes, copy the newest
version to the next increment, edit the copy, and publish it; never rewrite a
version the user has seen. Re-enter the wait loop after every batch.

A `done` event approves a declared sign-off; it does not end the page. Keep the
page working and watched while carrying out approved work. End only after every
delivered event is handled, every reader-owned thread that still needs your answer
has one, and the final version honors standing decisions and reports. Then run
`leaf status <page> idle`. Do not stop a normal session-lifetime server separately.

## Conditional routes

Read each reference directly from this skill directory when its condition applies.
References do not route to other references.

- `references/page-authoring.md` — before writing or revising any version and
  again before the first handoff.
- `references/conversation-loop.md` — before waiting, processing a delivered
  batch, opening or replying to a thread, or ending a page.
- `references/worker-orchestration.md` — only when other sessions report into an
  orchestrator-owned page, or when a worker receives a Leaf assignment.
- `references/serving-pages.md` — for `--export`, an unreachable URL, `--host`, a
  standing page, or resuming a page another session owned.
- `references/customizing.md` — for a layer-design request or an event with
  `"about": "layer"`.
- `references/codex-watcher.md` — only after the user explicitly authorizes a
  visible Codex watcher task. Follow it before handing over the page.
