---
name: leaf
description: Presents designs, decisions, findings, or live work as an HTML page the user can comment on and manipulate, and processes user input delivered from an existing Leaf page. Use for “explain this in HTML,” “write up the findings,” “show me the options,” building a playground, explorer, simulator, or interactive tool, work whose progress or review belongs in a shared page, a `leaf_delivery` tool output, or a `leaf-delivery` message.
allowed-tools:
  - Bash(leaf:*)
  - Bash(jq:*)
---

You work with the user through a live HTML page. They read it, comment on exact
passages and act through widgets while the work continues. Success means completing
the task while the user can understand and redirect the work, so their questions and
changes of direction take priority over work in progress, and the page stays current
as the work proceeds.

The input is either a subject to present or a delivery from a page already handed
over: a `leaf_delivery` tool output, a `leaf-delivery` element, or the envelope
`leaf wait` printed. A delivery starts at step 6 below; don't initialize or hand the
page over again. With no subject in `$ARGUMENTS`, present the work already under
discussion.

$ARGUMENTS

## Must remember

- **Everything waiting on the user is an obligation on their On me list**, including
  each decision you leave to them that your next step doesn't depend on. Register
  it before a page heading, a chat open item or a `needs input:` line mentions it.
  `references/conversation-loop.md`, "The On lists", says how to register each
  kind and when to reconcile the lists.

## Purpose and principles

Read [SOUL.md](SOUL.md) before authoring or responding on a Leaf page.

## Operate

When the harness sets `$LEAF`, use that launcher for every command shown as `leaf`.
Otherwise use `../../bin/leaf` from the directory holding this `SKILL.md`, or the
path your harness contract names; if the file is missing, report that the plugin
payload is incomplete. Pages usually live at `~/.local/state/leaf/pages/<slug>/`, but
every command takes the directory explicitly; export or copy anything that must
outlive it.

1. Record the work you take on (`references/conversation-loop.md`, "When to write").
   Run `leaf page init <page>`, adding `--package <name>` for each package whose
   vocabulary the page needs (`references/packages.md`, "Package reach"); running it
   again adds a package to a page already written. Use `playground` when the user
   tunes several values or behaviors before choosing. Drawn candidates the user
   picks among need no package (`references/authoring-decisions.md`).
2. Read all of `references/page-authoring.md`, then each reference the page needs
   from "Author a version" below, and write `<page>/index.html` in the registry's
   vocabulary. Each valid save becomes the live revision; an invalid save leaves the
   last valid one live and reports the error in page state and the browser. You
   write `index.html` and `page/`; only Leaf writes revisions and version mappings.
3. **Check the page.** Before you first hand the page over, run
   `leaf page check <page>` and fix every failure. For a quick page, one the user
   reacts to once and then revises or drops, that is the whole check: hand it over
   without a stamp or a browser review. After the handoff, reply about a revision as
   soon as it is saved, even on a record. The reply checks your saved edits and is
   refused over an error, so a separate check only delays the answer.
4. **Review and stamp a record.** A record is a page used beyond this conversation;
   a page with `<meta name="lf-review" content="sign-off">` is always one, since
   approval requires a stamped version. Before a record's first handoff, and when a
   stamp first makes a quick page a record, run `leaf page check <page> --render`, do
   the reading in `references/page-checkpoints.md`, "Pre-handover review", then run
   `leaf page stamp <page> --text "<changelog>"`. Its "Stamp checkpoints" says when to
   stamp again; each later stamp repeats the render check and the reading for the
   views and On me obligations it adds.
5. Read the contract that "Harness selection" below picks, and serve and hand over
   the page as it says, following `references/conversation-loop.md`, "Status and
   handoff".
6. When a delivery arrives, read `references/event-batches.md`, the harness contract
   and, for user messages, `references/threads.md`, and answer every event as they
   say. Say what you are doing before you do it
   (`references/conversation-loop.md`, "When to write").
7. Stamp checkpoints and end the page as `references/page-checkpoints.md` says.

## Harness selection

Pick the contract for the session that owns the page:

| Session     | Contract                            |
| ----------- | ----------------------------------- |
| Claude Code | `references/harness-claude-code.md` |
| Pi          | `references/harness-pi.md`          |
| Codex       | `references/harness-codex.md`       |

## Stay responsive

You own the Leaf conversation: answer the user, keep the page current, and direct
background subagents doing the substantive research, editing and testing, so you
stay available for the user's next move. Keep direct answers, small page changes,
and the review and integration of worker results with you; having more work to do
is a reason to delegate it. If subagents are unavailable, run long operations in the background and follow your harness's
delivery loop between bounded steps. `references/conversation-loop.md`,
"Long-running work", covers worker briefs and work that outlasts your turn.

## Page contract

Unless the user sets the page's shape or depth, a Leaf page is a short sequence of
visually distinct, self-contained views. Each view makes one point, shows one state
or offers one move, so the user takes it in at a glance and moves on; disclosures
hold supporting detail out of that path. The page's shape follows the subject, set
by a Layout class on `main` (`references/page-authoring.md`, "Composing a page").

Choose controls, gestures and options whose benefit to the user's task outweighs the
attention and effort they require. Remove redundant actions before making them
visually quieter. Widget actions, resolutions and sign-offs can be undone; sent
words stay in the log.

When work lands, a decision is made, or your understanding changes, revise the page
as `references/authoring-revisions.md`, "Keep the current page current", says.

## Follow the user's preferences

When the user states a preference meant for every page, save it in your harness's
memory, where later sessions read it; Leaf keeps none.

## Improve Leaf through use

When Leaf gets in your way through friction, ambiguity or a missing capability, tell
the user what you wanted to do and how the interface blocked it, explain the
improvement and how it would help other pages, and offer to file an issue in the
Leaf repository.

## Conditional references

Read references from this skill directory.

### Author a version

- `references/page-authoring.md`: all of it, before writing or revising any version.
- `references/page-layout.md`: before giving a page a Layout other than the reading
  column, widening or bounding a block, placing contents or notes in the margin,
  styling Leaf's controls, or showing several contributors' activity.
- `references/page-behavior.md`: before giving a page a script, a file under `page/`,
  a `page/registry.json`, or anything loaded from another server.
- `references/live-samples.md`: before letting the user operate a Leaf page inside a
  page or a thread message.
- `references/authoring-decisions.md`: when the page or your reply leaves anything
  for the user to decide or sign off, before choosing its widgets.
- `references/authoring-revisions.md`: before changing a handed-over page, proposing
  a rewrite, using a user-owned draft, or revising the page's current state.
- `references/authoring-evidence.md`: for work updates or reviews, before drawing a
  figure, or using measured facts, diagrams, charts, source files or text edits,
  images, recordings, or before/after captures.

### First handoff

- `references/conversation-loop.md`: before a page handoff, starting work on the
  page, work long enough to delegate, or asking the user to do something no widget
  answers.
- The contract "Harness selection" picks: before the first handoff and when a
  delivery arrives.

### Continue after input

- `references/event-batches.md`: after a delivery, before processing its events.
- `references/threads.md`: before opening, naming, replying to, editing,
  summarizing or resolving a thread.
- `references/page-checkpoints.md`: before a record's pre-handover review, stamping,
  or ending a page.

### Serve or extend a page

- `references/serving-pages.md`: for the first handoff, `--export`, an unreachable
  URL, whether an operation changes a page's URL, `--host`, a persistent page,
  re-vendoring a served page, a page a Leaf update broke, or resuming another
  session's page.
- `references/module-authoring.md`: before writing or changing browser behavior in
  a page script, page-owned widget or package widget. Then, as the behavior needs
  them: `references/module-reading.md` for reading the page, content helpers,
  obligations and history; `references/module-state.md` for recorded state and data;
  `references/module-input.md` for commands, focus and text entry;
  `references/module-scroll-and-motion.md` for scrolling, travel and motion; and
  `references/module-annotations.md` for margin entries, visual parts and Threads.
- `references/packages.md`: for package design, registry declarations, or a design
  comment whose fix belongs in a package; `references/package-themes.md` for theme
  rules; `references/package-data.md` for user state and data contracts.

### Set up a Codex connection

- `references/codex-setup.md`: when setting up a terminal App Server connection.
- `references/codex-watcher.md`: only after the user explicitly authorizes a
  visible Codex watcher task. Follow it before handing over the page.
