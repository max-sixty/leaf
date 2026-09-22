---
name: leaf
description: Presents designs, decisions, findings, or live work as an HTML page the user can comment on and manipulate, and processes reader input delivered from an existing Leaf page. Use for “explain this in HTML,” “write up the findings,” “show me the options,” building a playground, explorer, simulator, or interactive tool, work whose progress or review belongs in a shared page, a `leaf_delivery` tool output, or a `leaf-delivery` message.
allowed-tools:
  - Bash(leaf:*)
  - Bash(jq:*)
---

Leaf presents work as a live HTML page. The user reads it in a browser, comments
on exact passages, and acts through its widgets; you revise the page in place
while they do. A page is a directory: the mutable `index.html` you write, the
immutable revision each valid save becomes, the append-only event log, service
state, and the vendored layer that draws it. A stamp names a revision as a public
version. You write the page, check it, hand its URL over with a status saying
what you want back, and wait. Each reader move comes back to you as a delivery;
you answer it on the page and in its thread, stamp checkpoints, and idle the page
when it is finished.

The input is a subject to present, or a delivery from a page already handed
over: a named `leaf_delivery` tool output, a `leaf-delivery` element, or the
envelope a `leaf wait` printed. A delivery starts at step 5 below; do
not initialize or hand the page over again. With no subject in `$ARGUMENTS`,
present the work already under discussion. Leaf's writing guidance supplies
defaults only; any user-specific guidance on tone, structure, depth, or format
takes precedence.

$ARGUMENTS

## Operate

When the host sets `$LEAF`, use that launcher for every command shown as `leaf`.
Otherwise resolve the directory containing this `SKILL.md` and use its
`../../bin/leaf` launcher; your host contract may name that path directly or put
it on `PATH`. If the resolved file is absent, report that the plugin payload is
incomplete. A checkout keeps the launcher at `bin/leaf`. Pages conventionally
live at `~/.local/state/leaf/pages/<slug>/`, though every command takes the
directory explicitly; export or copy anything that must outlive the page directory.

1. Run `leaf page init <page>`, and name a package when the page needs an
   optional shape:
   `diagram` for Mermaid, `diff` for a unified diff, `swipe` for rapid
   pass-or-keep triage, `playground` whenever the reader compares or tunes
   several values or behaviors, `visual-review` for an ordered website run with
   aligned before-and-after evidence, and `targeting` for selecting and proposing
   changes to preview elements, as in
   `leaf page init --package diagram --package diff <page>`. Re-running
   `page init` with a selection adds it to a page already written.
2. Read `references/page-authoring.md`, then the authoring reference each part
   of the page needs, listed under "Author a version" below. Write
   `<page>/index.html` in the registry's vocabulary. Each valid save becomes the
   active immutable revision; an invalid save leaves the last valid one live and
   reports its diagnostic in page state and the browser. You write `index.html` and
   `page/`; Leaf alone writes revisions and version mappings.
3. Check the page by its intended lifetime, whatever its shape and whether or
   not it asks a question. A quick page that will be revised or dropped after an
   immediate reaction needs only `leaf version check <page>`; fix every failure,
   and do not stamp it or delay its handoff for a browser review. For a finished
   record that work will rely on after the conversation, run the pre-handover
   review in `references/page-authoring.md`, including
   `leaf version check <page> --render`, then
   `leaf version stamp <page> --text "<changelog>"` before its URL first reaches
   the user. A page declaring `<meta name="lf-review" content="sign-off">`
   is a record whatever else it looks like, since sign-off is offered only on a
   stamped version. A later stamp that turns a quick page into a record takes
   that review first.
4. Read `references/conversation-loop.md` and exactly one host contract,
   `references/host-claude-code.md` or `references/host-codex.md`. Set the
   page's status as the conversation reference defines, hand over by the host's
   route, name the gesture available to the reader, and finish the turn with the
   exact URL, or with what the host contract hands over instead.
5. When a delivery arrives, run `leaf delivery claim <id>` first. Then read
   `references/event-batches.md`, the host contract, and, for reader messages,
   `references/conversation-threads.md`, and answer every event as they say.
6. Stamp checkpoints and end the page as `references/page-checkpoints.md` says.

From the first hand-over on, every chat message repeats the page's exact URL,
interim updates and questions included.

## Page contract

Using Leaf should feel like playing a game: the reader sees what the page wants
of them without reading it first, every state they reach offers a move, and a
move the page can draw shows its result at once. Sometimes the game is Snap,
where the match is there and they pick it; sometimes it is Factorio, where the
system is laid out and they move its pieces. It is never a chore.

Unless the user specifies the page's form or depth, a Leaf is a short sequence
of visually distinct, self-contained views. Each view makes one point, shows one
state, or offers one move, so the reader can grasp it at a glance and continue;
disclosures keep supporting detail available without putting it in that path.
The visible page follows the subject's shape, whether a scrolling document or a
workspace; `references/page-authoring.md` owns the concrete choices, and
`references/authoring-asks.md` owns where each Ask goes.

The page contract and widget capabilities are choices, not a checklist. Include
only controls and gestures whose results advance the reader's task. A widget
move, a resolution and a sign-off can be taken back; words and requests stand.

## Keep the reader current

By default, the document is the shared canvas and current record for the subject.
Whenever the reader returns to it, it is the page you would write today from what
you now know. Its title, lede, and headings state what is true now, and open work
and open questions stand in the column while finished work sits collapsed after
them. A reader finds each outcome in the relevant page section without
reconstructing a thread or chat. The banner says what you are doing now; threads
carry discussion and rationale.

When work lands, a decision is made, or your understanding moves, reread the whole
page and rewrite whatever the change reaches, its title, headings, and order
included. A status note added where the page already mentions the subject leaves
everything around it as it was written before the change.
`references/authoring-revisions.md` says what a rewrite carries across. The
`version stamp` changelog and the event log hold the history, so the page does not
retell it: correct a wrong figure in place and drop a superseded claim. Save
freely as the subject changes and stamp meaningful checkpoints.

While a page is live, telling its reader what you are doing takes priority over doing
it, as a UI thread handles input before background work. Put each step on the page
before starting it, and acknowledge reader input on the page before acting on it. Keep
the watcher running, and hand work longer than a few minutes to background workers
rather than waiting on it yourself, so a new comment reaches you in time to change the
next step. The page stays yours while they run. `references/conversation-loop.md` names
the surfaces, when to write each, and what a worker may touch.

## Improve Leaf through use

Leaf's agent interface is still in development, and experience making real
pages should inform it. When using Leaf exposes concrete friction, ambiguity,
or a missing capability, raise it with the user and offer to file an issue in
the Leaf repository. Agent-reported issues are welcome.

Describe the specific case: what you wanted to do and how the interface got in
the way. Then explain the general improvement and why it would make Leaf better
beyond that page.

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

- `references/conversation-loop.md`: before a page handoff, a working status, or
  work long enough to delegate.
- `references/host-claude-code.md`: before the first handoff in Claude Code or
  recovery of its direct wait loop.
- `references/host-codex.md`: before the first handoff in Codex, and for the
  delivery payload its later turns receive.

### Continue after input

- `references/event-batches.md`: after delivery and before processing its events.
- `references/conversation-threads.md`: before opening, naming, replying to,
  editing, summarizing, or resolving a thread.
- `references/page-checkpoints.md`: before stamping or ending a page.

### Serve or extend a page

- `references/serving-pages.md`: for the first handoff, `--export`, an unreachable
  URL, `--host`, a standing page, re-vendoring a served page, or resuming another
  session's page.
- `references/packages.md`: for a package-design request, a page-authored module, or
  an event with `"about": "design"`.

### Use a separate Codex watcher

- `references/codex-watcher.md`: only after the user explicitly authorizes a
  visible Codex watcher task. Follow it before handing over the page.
