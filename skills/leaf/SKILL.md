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

$ARGUMENTS

## Return to the user

After first handing over the page's URL, repeat that exact URL every time you
return to the user in chat, including interim updates, questions, and the final
handoff.

## Start here

Pages conventionally live at `~/.local/state/leaf/pages/<slug>/`, though every
command takes the directory explicitly. A page holds mutable `index.html`,
immutable valid revisions, stamped versions, the event log, service state, and
its vendored layer. Export or copy anything that must outlive that live state.

Resolve the directory containing this `SKILL.md`, then use its
`../../bin/leaf` launcher for every command shown as `leaf`. In Claude Code that
path is `${CLAUDE_SKILL_DIR}/../../bin/leaf`, and Claude Code also puts it on
`PATH`. If the resolved file is absent, report that the plugin payload is
incomplete. A checkout keeps it at `bin/leaf`.

1. Run `leaf page init <page>`.
2. Read `references/page-authoring.md`, including its selective `registry.json`
   queries. Read `references/authoring-decisions.md` while authoring a new,
   unanswered ask or sign-off; read `references/authoring-revisions.md` before
   changing a handed-over page, proposing a rewrite, using a reader-owned draft,
   or carrying standing state. Read
   `references/authoring-evidence.md` only for measured, visual, source, or media
   evidence. Write `<page>/index.html` using only the registry's vocabulary. A
   valid save becomes the active immutable revision; an invalid save leaves the
   last valid revision live and reports its diagnostic in page state and the
   browser.
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
   - If a later stamp turns a quick page into a record, run that review before
     the stamp.
4. Start the service with `leaf server start <page>` and retain its exact URL.
   The key in that URL opens the page.
5. Read `references/conversation-loop.md` and exactly one host contract:
   `references/host-claude-code.md` or `references/host-codex.md`. Set the page's
   handoff status as the conversation reference defines.
6. Start the wait or delivery loop defined by the selected host contract.
7. Send the exact URL and one sentence naming the available gesture — comment,
   use the stated control, or approve declared sign-off — then finish the turn.

When input arrives, read `references/event-batches.md` before processing it and
`references/conversation-threads.md` when a thread needs work. Read
`references/page-checkpoints.md` before stamping or ending. Edit only
`index.html`; Leaf alone writes immutable revisions and versions.

## Page contract

Using Leaf should feel like playing a game. Sometimes the game is Snap, where
the reader sees the match at once and picks it; sometimes it is Factorio, where
the whole system is laid out and the reader moves its pieces. It is never a chore, so a
reader can see what the page wants of them without reading it first.

The subject decides the shape. Use options for decisions, boards for movable
work, milestones for stages, metrics for measurements, and prose where no other
shape fits. Prose connects the shapes, so keep it short. The page's
`registry.json` is the authority for the vendored vocabulary and theme; query
only the entries the page needs.

A page states what is true now, not how it got there. Correct a wrong figure in
place and drop a superseded claim rather than narrating its withdrawal — the
`version stamp` changelog and the event log carry the history, so the column does
not have to.

Packages may also carry guidance for roles involved in the page. `leaf page
guidance <page>` lists the available audiences, and `leaf page guidance <page>
<audience>` prints one guide. Read the assigned audience before acting in that
role. List the page's audiences and read `author` guidance when it is available.

Every decision has a control beside its evidence. A page that needs approval declares
sign-off; an informative page does not. Save freely as the subject changes and
stamp meaningful checkpoints. Use status detail for progress between revisions.
Keep the waiter alive while work continues so comments can affect the next step.

## Conditional references

Read references directly from this skill directory. Every route is listed here,
so a phase does not depend on discovering a chain of references.

### Author a version

- `references/page-authoring.md`: before writing or revising any version.
- `references/authoring-decisions.md`: while authoring a new, unanswered ask or
  sign-off.
- `references/authoring-revisions.md`: before changing a handed-over page,
  proposing a rewrite, using a reader-owned draft, or carrying standing state.
- `references/authoring-evidence.md`: before using measured facts, diagrams,
  charts, source files, images, or before/after captures.

### First handoff

- `references/conversation-loop.md`: before a page handoff or working status.
- `references/host-claude-code.md`: before the first handoff in Claude Code or
  recovery of its direct wait loop.
- `references/host-codex.md`: before the first handoff in Codex.

### Continue after input

- `references/event-batches.md`: after delivery and before processing its events.
- `references/conversation-threads.md`: before opening, replying to, editing, or
  resolving a thread.
- `references/page-checkpoints.md`: before stamping or ending a page.

### Serve or extend a page

- `references/serving-pages.md`: for `--export`, an unreachable URL, `--host`, a
  standing page, re-vendoring a served page, or resuming another session's page.
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

### Use a separate Codex watcher

- `references/codex-watcher.md`: only after the user explicitly authorizes a
  visible Codex watcher task. Follow it before handing over the page.
