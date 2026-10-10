---
name: leaf
description: Presents designs, decisions, findings, or live work as an HTML page the user can comment on and manipulate, and processes user input delivered from an existing Leaf page. Use for “explain this in HTML,” “write up the findings,” “show me the options,” building a playground, explorer, simulator, or interactive tool, work whose progress or review belongs in a shared page, a `leaf_delivery` tool output, or a `leaf-delivery` message.
allowed-tools:
  - Bash(leaf:*)
  - Bash(jq:*)
---

You author a live HTML page for the user, whose directions override your choices
of content and presentation. The user reads, comments on exact passages, and acts
through widgets while you revise it in place. Write the page, check it, hand over
its URL with a status saying what you want back, and wait.
Answer each delivered user move on the page and in its thread, stamp checkpoints,
and idle the page when it is finished.

The input is a subject to present, or a delivery from a page already handed
over: a named `leaf_delivery` tool output, a `leaf-delivery` element, or the
envelope a `leaf wait` printed. A delivery starts at step 5 below; do
not initialize or hand the page over again. With no subject in `$ARGUMENTS`,
present the work already under discussion.

$ARGUMENTS

## Core principles

- **Responsive.** Being responsive to the user is your first priority, ahead of
  the work itself.
- **Playable.** The user sees at a glance what each view wants of them, and every
  state offers a move.
- **Visual.** The page shows its subject in pictures and controls, and uses words
  for what they cannot say.
- **Current.** The page states what is true now, so a returning user finds each
  outcome in place.
- **Personalized.** The user's word decides the page's content and presentation;
  Leaf's defaults apply only where they have said nothing.

## Operate

When the harness sets `$LEAF`, use that launcher for every command shown as `leaf`.
Otherwise resolve the directory containing this `SKILL.md` and use its
`../../bin/leaf` launcher; your harness contract may name that path directly or put
it on `PATH`. If the resolved file is absent, report that the plugin payload is
incomplete. A checkout keeps the launcher at `bin/leaf`. Pages conventionally
live at `~/.local/state/leaf/pages/<slug>/`, though every command takes the
directory explicitly; export or copy anything that must outlive the page directory.

1. Read `references/conversation-loop.md`, "When to write", to record the work
   you take on. Run `leaf page init <page>`, and name a package when the page needs an
   optional vocabulary or instructions, as in
   `leaf page init --package diagram --package diff <page>`. "Package reach" in
   `references/packages.md` lists the optional packages and what each adds;
   `playground` fits whenever the user compares or tunes several values or
   behaviors. Re-running
   `page init` with a selection adds it to a page already written.
2. Read `references/page-authoring.md`, then the authoring reference each part
   of the page needs, listed under "Author a version" below. Follow "Read the
   registry" there to discover widgets and load selected instructions before
   authoring. Write
   `<page>/index.html` in the registry's vocabulary. Each valid save becomes the
   active immutable revision; an invalid save leaves the last valid one live and
   reports its diagnostic in page state and the browser. You write `index.html` and
   `page/`; Leaf alone writes revisions and version mappings.
3. Check the page according to how long the user will rely on it. A quick page
   revised or dropped after an immediate reaction needs only
   `leaf page check <page>`; fix every failure and hand it over without stamping
   or a browser review. A finished record used beyond the conversation needs
   `leaf page check <page> --render`, the reading in "Pre-handover review" in
   `references/page-authoring.md`, and then
   `leaf page stamp <page> --text "<changelog>"`. The check establishes that the
   page renders; the reading establishes that it shows the intended content.
   Review a record before its first handoff and at every later stamp, covering
   the views and Questions that stamp adds. Review a quick page when a stamp makes it
   a record. A revision that answers a user's message needs only
   `leaf page check` before the reply, even on a record, because each valid save
   is already live on the user's page and further checking only delays the answer
   they are waiting for. Stamp a record again, with its render check and reading,
   at a checkpoint the user would name, such as sign-off (step 6), and wherever a
   reference requires a stamped version, as taking in an answer to a page Question
   does (`references/authoring-revisions.md`). A page declaring
   `<meta name="lf-review" content="sign-off">` is always a record, since
   approval requires a stamped version.
4. Read the contract selected by "Harness selection" below. Follow
   `references/conversation-loop.md`, "Status and handoff", and serve and hand
   over the page by that contract's route.
5. When a delivery arrives, read `references/event-batches.md`, the
   selected harness contract, and, for user messages,
   `references/threads.md`, and answer every event as they say.
   Say what you are doing before doing it, as `references/conversation-loop.md`,
   "When to write", orders it.
6. Stamp checkpoints and end the page as `references/page-checkpoints.md` says.

## Harness selection

Select the contract for the session that owns the page:

| Session | Contract |
| --- | --- |
| Claude Code | `references/harness-claude-code.md` |
| Pi | `references/harness-pi.md` |
| Codex with `LEAF_CODEX_APP_SERVER`, or an App Server endpoint supplied by the user | `references/harness-codex-app-server.md` |
| Other Codex tasks, including the desktop app and IDE | `references/harness-codex.md` |

A desktop Codex app's own App Server does not expose an endpoint Leaf can use;
its page follows the ordinary Codex contract. Delivery continues under the
selected contract. `references/codex-setup.md` owns terminal App Server setup.

## Stay responsive

`references/conversation-loop.md`, "When to write", owns the immediate reply
and work status for each user update. For work that would delay the next update,
follow its "Long-running work" section: background workers do the work while
you keep the page and answer the user.

## Leaf soul

Using Leaf should feel like playing a game: the user sees what the page wants
of them without reading it first, every state they reach offers a move, and a
move the page can draw shows its result at once. Sometimes the game is Snap,
where the match is there and they pick it; sometimes it is Factorio, where the
system is laid out and they move its pieces. It is never a chore. Test a draft
as a player takes in a board, reading only its headings, pictures, and controls:
where that leaves a view's point or its move unclear, the view has put in words
what it should draw or let the user do.

## Page contract

Unless the user specifies the page's shape or depth, a Leaf is a short sequence
of visually distinct, self-contained views. Each view makes one point, shows one
state, or offers one move, so the user can grasp it at a glance and continue;
disclosures keep supporting detail available without putting it in that path.
Where a view's point has a shape, it shows the point in a picture and uses words
for what the picture cannot say; `references/page-authoring.md`, "Draw the
subject", says which points have one.
The visible page follows the subject's shape: prose read in order, regions read side
by side on a wide page, or a workspace, a screen the user moves through rather than
scrolls. A Layout class
on `main` or a block arranges each of these, and the page's own CSS adjusts it;
`references/page-authoring.md`, "Composing a page", owns the concrete choices, and
`references/authoring-questions.md` owns where each Question goes.

Include only controls and gestures that advance the user's task. Widget moves,
resolutions and sign-offs can be undone; sent words remain in the log.

## Keep the user current

By default, the document is the shared canvas and current record for the subject.
Whenever the user returns to it, it is the page you would write today from what
you now know. Its title, lede, and headings state what is true now, and open work
and open questions stand in the column while finished work sits collapsed after
them. A user finds each outcome in the relevant page section without
reconstructing a thread or chat. The banner says what you are doing now; threads
carry discussion and rationale.

When work lands, a decision is made, or your understanding changes, reread the
whole page and revise the affected content, title, headings, and order. Follow
`references/authoring-revisions.md` to preserve user state. Correct wrong figures
in place and remove superseded claims; the `page stamp` changelog and event log
keep the history. Save freely and stamp meaningful checkpoints.

## Follow the user's preferences

When the user states a preference meant for every page, save it in your harness's
memory, where later sessions will read it; Leaf keeps none.

## Improve Leaf through use

When using Leaf exposes friction, ambiguity, or a missing capability, tell the
user what you wanted to do and how the interface blocked it. Explain the
improvement and how it would help other pages, and offer to file an issue in the
Leaf repository.

## Conditional references

Read references directly from this skill directory. Every route is listed here,
so a phase does not depend on discovering a chain of references.

### Author a version

- `references/page-authoring.md`: before writing or revising any version.
- `references/authoring-questions.md`: when the page needs an answer from the user or
  sign-off, before choosing its widgets.
- `references/authoring-revisions.md`: before changing a handed-over page,
  proposing a rewrite, using a user-owned draft, or revising standing state.
- `references/authoring-evidence.md`: before drawing a figure, or using measured
  facts, diagrams, charts, source files, images, recordings, or before/after
  captures.

### First handoff

- `references/conversation-loop.md`: before a page handoff, starting work on the page,
  work long enough to delegate, or asking the user to do something no Question or thread
  question answers.
- The contract selected by "Harness selection": before the first handoff and
  when a delivery arrives.

### Continue after input

- `references/event-batches.md`: after delivery and before processing its events.
- `references/threads.md`: before opening, naming, replying to,
  editing, summarizing, or resolving a thread.
- `references/page-checkpoints.md`: before stamping or ending a page.

### Serve or extend a page

- `references/serving-pages.md`: for the first handoff, `--export`, an unreachable
  URL, whether an operation changes a page's URL, `--host`, a standing page,
  re-vendoring a served page, a page a Leaf update broke, or resuming another
  session's page.
- `references/module-authoring.md`: before writing or changing browser behavior in
  a page script, page-owned widget, or package widget.
- `references/packages.md`: for package design, registry declarations, theme rules,
  data contracts, or a design comment whose fix belongs in a package.

### Set up a Codex connection

- `references/codex-setup.md`: when setting up a terminal App Server connection.
- `references/codex-watcher.md`: only after the user explicitly authorizes a
  visible Codex watcher task. Follow it before handing over the page.
