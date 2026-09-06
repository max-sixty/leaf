---
name: leaf
description: Presents designs, decisions, findings, or live work as an HTML page the user can comment on and manipulate. Use for “explain this in HTML,” “write up the findings,” “show me the options,” or work whose progress or review belongs in a shared page.
allowed-tools:
  - Bash(leaf:*)
  - Bash(jq:*)
---

Present the session's subject as a live HTML page. The user comments on exact
passages, acts through the page's widgets, and follows revisions in place. With
no subject in `$ARGUMENTS`, use the work already under discussion.

Leaf's writing guidance supplies defaults only; any user-specific guidance on
tone, structure, depth, or format takes precedence.

$ARGUMENTS

## Return to the user

After first handing over a browser page's URL, repeat that exact URL every time
you return to the user in chat, including interim updates, questions, and the
final handoff. An inline MCP App has no durable URL to invent; refer to the review
and its observed mode instead. If you open its browser page, the URL rule begins then.

## Start here

Pages conventionally live at `~/.local/state/leaf/pages/<slug>/`, though every
command takes the directory explicitly. A page holds mutable `index.html`,
immutable valid revisions, event-backed stamped version aliases, the event log,
service state, and its vendored layer. Export or copy anything that must outlive
that live state.

Resolve the directory containing this `SKILL.md`, then use its
`../../bin/leaf` launcher for every command shown as `leaf`. In Claude Code that
path is `${CLAUDE_SKILL_DIR}/../../bin/leaf`, and Claude Code also puts it on
`PATH`. If the resolved file is absent, report that the plugin payload is
incomplete. A checkout keeps it at `bin/leaf`.

1. Run `leaf page init <page>`. Optional shapes need their packages named here:
   `diagram` for Mermaid, `diff` for a unified diff, `swipe` for rapid
   pass-or-keep triage, and `playground` for declarative interactive explorers, as in
   `leaf page init --package diagram --package diff <page>`. Re-running `page init`
   with the selection adds it to a page already written.
2. Read `references/page-authoring.md`, then the authoring reference each part of
   the page needs (listed under "Author a version" below). Write
   `<page>/index.html` using only the registry's vocabulary. A valid save becomes
   the active immutable revision; an invalid save leaves the last valid revision
   live and reports its diagnostic in page state and the browser.
3. Match the handoff ceremony to the page's intended lifetime, regardless of
   its shape or whether it asks a question:
   - For a quick page that will be revised or dropped after an immediate
     reaction, run `leaf version check <page>` and fix every failure. Do not
     stamp it or delay its first handoff for a browser review.
   - For a finished record that work will rely on after the conversation, run
     the pre-handover review in `references/page-authoring.md`, including
     `leaf version check <page> --render`, and fix every failure. Then stamp it
     with `leaf version stamp <page> --text "<changelog>"` before its URL first
     reaches the user.
   - A page declaring `<meta name="lf-review" content="sign-off">` is a record,
     whatever else it looks like: work will rely on the approval, and sign-off is
     offered only on a stamped version. Give it the record's ceremony before its
     URL first reaches the user.
   - If a later stamp turns a quick page into a record, run that review before
     the stamp.
4. Read `references/conversation-loop.md` and exactly one host contract:
   `references/host-claude-code.md` or `references/host-codex.md`. Set the page's
   status as the conversation reference defines, and hand over by the route the
   host contract defines. Both hosts use the full browser page by default; retain
   the exact keyed URL. Inline MCP Apps are an explicit experimental route with a
   reduced fallback.
5. Name the available gesture and finish the turn. Send the exact URL for a
   browser handoff; for an MCP App, name the review and report the observed mode
   or that rendering remains unverified.

When input arrives, read `references/event-batches.md` before processing it and
`references/conversation-threads.md` when a thread needs work; in Codex the
delivery arrives as a `leaf-delivery` element, which `references/host-codex.md`
owns. Read `references/page-checkpoints.md` before stamping or ending. Edit only
`index.html`; Leaf alone writes immutable revisions and public version mappings.

## Page contract

Unless the user specifies the page's form or depth, a Leaf is a short sequence
of visually distinct, self-contained views. Each view makes one point, shows one
state, or offers one move, so the reader can grasp it at a glance and continue;
   disclosures keep supporting detail available without putting it in that path. A
   quick-answer page puts its first Ask in the initial viewport, with the short
shared premise and alternatives it needs. A record or system page may expose the
whole state and put each Ask where that state makes it answerable. The visible
page follows the subject's shape rather than a report outline;
`references/page-authoring.md` owns the concrete choices.

A page states what is true now, not how it got there. Correct a wrong figure in
place and drop a superseded claim rather than narrating its withdrawal; the
`version stamp` changelog and the event log carry the history. Save freely as
the subject changes and stamp meaningful checkpoints. Use status detail for
progress between revisions. Keep the waiter alive while work continues so
comments can affect the next step.

## Conditional references

Read references directly from this skill directory. Every route is listed here,
so a phase does not depend on discovering a chain of references.

### Author a version

- `references/page-authoring.md`: before writing or revising any version.
- `references/authoring-asks.md`: while authoring a new, unanswered ask or
  sign-off.
- `references/authoring-revisions.md`: before changing a handed-over page,
  proposing a rewrite, using a reader-owned draft, or revising standing state.
- `references/authoring-evidence.md`: before using measured facts, diagrams,
  charts, source files, images, or before/after captures.

### First handoff

- `references/conversation-loop.md`: before a page handoff or working status.
- `references/host-claude-code.md`: before the first handoff in Claude Code or
  recovery of its direct wait loop.
- `references/host-codex.md`: before the first handoff in Codex, and for the
  delivery payload its later turns receive.

### Continue after input

- `references/event-batches.md`: after delivery and before processing its events.
- `references/conversation-threads.md`: before opening, replying to, editing, or
  resolving a thread.
- `references/page-checkpoints.md`: before stamping or ending a page.

### Serve or extend a page

- `references/serving-pages.md`: for the first handoff, `--export`, an unreachable
  URL, `--host`, a standing page, re-vendoring a served page, or resuming another
  session's page.
- `references/packages.md`: for a package-design request or an event with
  `"about": "layer"`.

### Change Leaf itself

- `references/internals/page-storage.md`: when changing page files or storage
  invariants.
- `references/internals/session-lifetime.md`: when changing work claims,
  watchers, hooks, or server lifetime.
- `references/internals/layer-registry.md`: when changing composition or the
  registry's custom vocabulary.
- `references/internals/events.md`: when changing events, undo, authorship, or
  conversation semantics.
- `references/internals/validation.md`: when changing static or browser
  validation, passages, or parsed source. These internal contracts are not for
  ordinary page use.
- `references/internals/mcp-app.md`: when changing the MCP tools, app resource,
  process-scoped page server, private result payload, or snapshot fallback.

### Use a separate Codex watcher

- `references/codex-watcher.md`: only after the user explicitly authorizes a
  visible Codex watcher task. Follow it before handing over the page.
