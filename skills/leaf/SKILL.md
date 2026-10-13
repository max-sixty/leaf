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
Answer each delivered update on the page and in its thread, stamp checkpoints,
and idle the page when it is finished.

Anything you need from the user must appear in **Questions**. Zero Questions
means you need nothing from them now. Before handing over or waiting, read
`leaf page state <page>` and reconcile `queues.questions` and
`queues.tasks` with the work and decisions still open.
`references/conversation-loop.md`, "Questions and Tasks", owns what appears there
and how to register each request.

The input is a subject to present, or a delivery from a page already handed
over: a named `leaf_delivery` tool output, a `leaf-delivery` element, or the
envelope a `leaf wait` printed. A delivery starts at step 6 below; do
not initialize or hand the page over again. With no subject in `$ARGUMENTS`,
present the work already under discussion.

$ARGUMENTS

## Core principles

- **Responsive.** Being responsive to the user is your first priority, ahead of
  the work itself.
- **Playable.** Using Leaf should feel like playing a game: the user sees at a
  glance what each view wants of them, every state they reach offers a move, and a
  move the page can draw shows its result at once. Test a draft by reading only its
  headings, pictures, and controls, as a player takes in a board: where that leaves
  a view's point or its move unclear, the view has put in words what it should draw
  or let the user do.
- **Concrete.** The page puts the thing itself in front of the user, wherever they
  judge it: an interface as it looks, a behavior running, a proposal sketched, a
  numeric relationship as a chart, code or wording as the text itself. Whatever the
  user would have to picture from your words to judge, show instead; each option of
  an ask shows what choosing it gives them. Words carry what the thing cannot show:
  the claim, the reason, the cost.
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
   `playground` fits whenever the user tunes several values or behaviors before
   choosing; candidates the user picks among as drawn need no package, since the
   user selects the candidate itself (`references/authoring-asks.md`). Re-running
   `page init` with a selection adds it to a page already written.
2. Read `references/page-authoring.md`, then the authoring reference each part
   of the page needs, listed under "Author a version" below. Follow "Read the
   registry" there to select elements and class idioms and read their examples
   and selected instructions before authoring. Write
   `<page>/index.html` in the registry's vocabulary. Each valid save becomes the
   active immutable revision; an invalid save leaves the last valid one live and
   reports its diagnostic in page state and the browser. You write `index.html` and
   `page/`; Leaf alone writes revisions and version mappings.
3. **Check the page.** Before you hand the page over or reply about a revision,
   run `leaf page check <page>` and fix every failure. That is the whole check for a quick page, one the user reacts to once
   and then revises or drops: hand it over without stamping or a browser review. It
   is also the whole check for a revision that answers a user's message, even on a
   record, because each valid save is already live on the user's page and further
   checking only delays the answer they are waiting for.
4. **Review and stamp a record.** A record is a page used beyond this
   conversation. A page declaring `<meta name="lf-review" content="sign-off">` is
   always one, since approval requires a stamped version. Before a record's first
   handoff, run `leaf page check <page> --render`, do the reading in
   `references/page-authoring.md`, "Pre-handover review", and then run
   `leaf page stamp <page> --text "<changelog>"`. The render check establishes that
   the page renders; the reading establishes that it shows the intended content.
   `references/page-checkpoints.md`, "Stamp checkpoints", says when to stamp again;
   each later stamp repeats the render check and the reading for the views and asks
   it adds. A quick page takes this review when a stamp makes it a record.
5. Read the contract selected by "Harness selection" below. Follow
   `references/conversation-loop.md`, "Status and handoff", and serve and hand
   over the page by that contract's route.
6. When a delivery arrives, read `references/event-batches.md`, the
   selected harness contract, and, for user messages,
   `references/threads.md`, and answer every event as they say.
   Say what you are doing before doing it, as `references/conversation-loop.md`,
   "When to write", orders it.
7. Stamp checkpoints and end the page as `references/page-checkpoints.md` says.

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

## Page contract

Unless the user specifies the page's shape or depth, a Leaf is a short sequence
of visually distinct, self-contained views. Each view makes one point, shows one
state, or offers one move, so the user can grasp it at a glance and continue;
disclosures keep supporting detail available without putting it in that path.
Each view shows its subject as **Concrete** says; `references/page-authoring.md`,
"Show the subject", says which form each kind of subject takes.
The visible page follows the subject's shape: prose read in order, regions read side
by side on a sidebar page, or a workspace, a screen the user moves through rather than
scrolls. A Layout class
on `main` sets each of these shapes, and the page's own CSS adjusts it;
`references/page-authoring.md`, "Composing a page", owns the concrete choices, and
`references/authoring-asks.md` owns where each ask goes.

Include only controls and gestures that advance the user's task. Widget actions,
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
- `references/authoring-asks.md`: when the page needs an answer from the user or
  sign-off, before choosing its widgets.
- `references/authoring-revisions.md`: before changing a handed-over page,
  proposing a rewrite, using a user-owned draft, or revising the page's current state.
- `references/authoring-evidence.md`: for work updates or reviews, before drawing
  a figure, or using measured facts, diagrams, charts, source files or text edits,
  images, recordings, or before/after captures.

### First handoff

- `references/conversation-loop.md`: before a page handoff, starting work on the page,
  work long enough to delegate, or asking the user to do something no ask answers.
- The contract selected by "Harness selection": before the first handoff and
  when a delivery arrives.

### Continue after input

- `references/event-batches.md`: after delivery and before processing its events.
- `references/threads.md`: before opening, naming, replying to,
  editing, summarizing, or resolving a thread.
- `references/page-checkpoints.md`: before stamping or ending a page.

### Serve or extend a page

- `references/serving-pages.md`: for the first handoff, `--export`, an unreachable
  URL, whether an operation changes a page's URL, `--host`, a persistent page,
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
