---
name: leaf
description: Presents designs, decisions, findings, or live work as an HTML page the user can comment on and manipulate, and processes user input delivered from an existing Leaf page. Use for “explain this in HTML,” “write up the findings,” “show me the options,” building a playground, explorer, simulator, or interactive tool, work whose progress or review belongs in a shared page, a `leaf_delivery` tool output, or a `leaf-delivery` message.
allowed-tools:
  - Bash(leaf:*)
  - Bash(jq:*)
---

You author a live HTML page for the user. They read it, comment on exact passages
and act through widgets while you revise it in place. Write the page, check it,
hand over its URL with a status saying what you want back, and wait. Answer each
delivered update on the page and in its thread, stamp checkpoints, and idle the
page when it is finished.

The input is either a subject to present or a delivery from a page already handed
over: a `leaf_delivery` tool output, a `leaf-delivery` element, or the envelope
`leaf wait` printed. A delivery starts at step 6 below; don't initialize or hand
the page over again. With no subject in `$ARGUMENTS`, present the work already
under discussion.

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

When the harness sets `$LEAF`, use that launcher for every command shown as
`leaf`. Otherwise use `../../bin/leaf` from the directory holding this
`SKILL.md`; your harness contract may name that path or put it on `PATH`. If the
file is missing, report that the plugin payload is incomplete. In a checkout the
launcher is `bin/leaf`. Pages usually live at `~/.local/state/leaf/pages/<slug>/`,
but every command takes the directory explicitly; export or copy anything that
must outlive the page directory. A command prints its result on stdout, as JSON
unless its help names another format. On stderr it prints one JSON object per
line for each refusal or note, with the words in `error` or `text`.

1. Read `references/conversation-loop.md`, "When to write", to record the work
   you take on. Run `leaf page init <page>`, adding a package when the page needs
   its vocabulary or instructions: `leaf page init --package diagram --package diff <page>`.
   `references/packages.md`, "Package reach", lists the packages. Use
   `playground` when the user tunes several values or behaviors before choosing.
   Drawn candidates the user picks among need no package, since the user selects
   the candidate itself (`references/authoring-decisions.md`). Running `page init`
   again with a package adds it to a page already written.
2. Read all of `references/page-authoring.md`, then each reference the page
   needs, listed under "Author a version" below. Choose elements and class idioms
   from the registry as it says, and read their examples and instructions first.
   Write `<page>/index.html` in the registry's vocabulary. Each valid save
   becomes the live immutable revision. An invalid save leaves the last valid one
   live and reports the error in page state and the browser. You write
   `index.html` and `page/`; only Leaf writes revisions and version mappings.
3. **Check the page.** Before you hand the page over or reply about a revision,
   run `leaf page check <page>` and fix every failure. That is the whole check for
   a quick page, one the user reacts to once and then revises or drops: hand it
   over without stamping or a browser review. It is also the whole check for a
   revision that answers a user's message, even on a record: each valid save is
   already live on the user's page, and more checking only delays the answer
   they are waiting for.
4. **Review and stamp a record.** A record is a page used beyond this
   conversation. A page with `<meta name="lf-review" content="sign-off">` is
   always one, since approval requires a stamped version. Before a record's first
   handoff, run `leaf page check <page> --render`, do the reading in
   `references/page-checkpoints.md`, "Pre-handover review", then run
   `leaf page stamp <page> --text "<changelog>"`. The render check shows that the
   page renders; the reading shows what you meant.
   `references/page-checkpoints.md`, "Stamp checkpoints", says when to stamp
   again; each later stamp repeats the render check and the reading for the views
   and On me obligations it adds. A quick page takes this review once a stamp makes it a record.
5. Read the contract that "Harness selection" below picks. Follow
   `references/conversation-loop.md`, "Status and handoff", and serve and hand
   over the page the way that contract says.
6. When a delivery arrives, read `references/event-batches.md`, the harness
   contract and, for user messages, `references/threads.md`, and answer every
   event as they say. Say what you are doing before you do it
   (`references/conversation-loop.md`, "When to write").
7. Stamp checkpoints and end the page as `references/page-checkpoints.md` says.

## Harness selection

Pick the contract for the session that owns the page:

| Session                                                                            | Contract                                 |
| ---------------------------------------------------------------------------------- | ---------------------------------------- |
| Claude Code                                                                        | `references/harness-claude-code.md`      |
| Pi                                                                                 | `references/harness-pi.md`               |
| Codex with `LEAF_CODEX_APP_SERVER`, or an App Server endpoint supplied by the user | `references/harness-codex-app-server.md` |
| Other Codex tasks, including the desktop app and IDE                               | `references/harness-codex.md`            |

The desktop Codex app's own App Server exposes no endpoint Leaf can use, so its
pages follow the ordinary Codex contract. Deliveries keep arriving under the
contract you picked. `references/codex-setup.md` owns terminal App Server setup.

## Stay responsive

`references/conversation-loop.md`, "When to write", owns the immediate reply and
work status for each user update. The parent session owns the Leaf conversation:
answer the user, keep the page current, and direct background subagents doing the
substantive research, editing and testing. Keep direct answers, small page changes,
and the review and integration of worker results with you. Having more work to do
is a reason to delegate it, while you remain available for the user's next move.

`references/conversation-loop.md`, "Long-running work", owns worker briefs,
results and work that continues beyond your turn. If subagents are unavailable,
run long operations in the background and follow your harness's delivery loop
between bounded steps.

## Page contract

Unless the user sets the page's shape or depth, a Leaf page is a short sequence
of visually distinct, self-contained views. Each view makes one point, shows one
state or offers one move, so the user takes it in at a glance and moves on;
disclosures hold supporting detail out of that path. `references/page-authoring.md`,
"Show the subject", applies SOUL.md’s "Make the work concrete and playable" principle.

The page's shape follows the subject: prose read in order, regions read side by
side on a sidebar page, or a workspace the user moves through instead of
scrolling. A Layout class on `main` sets the shape, and the page's own CSS
adjusts it. `references/page-authoring.md`, "Composing a page", owns the choice
of shape, `references/page-layout.md` each shape's geometry, and
`references/authoring-decisions.md` where each decision goes.

Include only controls and gestures that advance the user's task. Widget actions,
resolutions and sign-offs can be undone; sent words stay in the log.

## Keep the user current

Follow `references/authoring-revisions.md`, "Keep the current page current", when
work lands, a decision is made, or your understanding changes. That section owns
how finished work leaves the column and how revisions preserve user state.

## Follow the user's preferences

When the user states a preference meant for every page, save it in your
harness's memory, where later sessions read it; Leaf keeps none.

## Improve Leaf through use

When Leaf gets in your way through friction, ambiguity or a missing capability,
tell the user what you wanted to do and how the interface blocked it. Explain the
improvement and how it would help other pages, and offer to file an issue in the
Leaf repository.

## Conditional references

Read references from this skill directory. Every route is listed here, so you
never have to follow a chain of references to find one.

### Author a version

- `references/page-authoring.md`: all of it, before writing or revising any version.
- `references/page-layout.md`: before giving a page a Layout other than the reading
  column, widening or bounding a block, placing contents or notes in the margin,
  styling Leaf's controls, or showing several contributors' activity.
- `references/page-behavior.md`: before giving a page a script, a file under `page/`,
  a `page/registry.json`, or anything loaded from another server.
- `references/live-samples.md`: before letting the user operate a Leaf page inside a
  page or a thread message.
- `references/authoring-decisions.md`: when the page or your reply leaves anything for
  the user to decide or sign off, before choosing its widgets.
- `references/authoring-revisions.md`: before changing a handed-over page,
  proposing a rewrite, using a user-owned draft, or revising the page's current state.
- `references/authoring-evidence.md`: for work updates or reviews, before drawing
  a figure, or using measured facts, diagrams, charts, source files or text edits,
  images, recordings, or before/after captures.

### First handoff

- `references/conversation-loop.md`: before a page handoff, starting work on the page,
  work long enough to delegate, or asking the user to do something no widget answers.
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
  them: `references/module-reading.md` for reading the page, content helpers, obligations
  and history; `references/module-state.md` for recorded state and data;
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
