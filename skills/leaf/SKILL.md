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

- **Everything waiting on the user is an item in their On me list**, including
  each decision you leave to them that your next step doesn't depend on. Register
  it before a page heading, a chat open item or a `needs input:` line mentions it.
  `references/conversation-loop.md`, "The On lists", says how to register each
  kind and when to reconcile the lists.

## Core principles

- **Responsive.** Responding to the user comes first, ahead of the work itself.
- **Playable.** Using Leaf should feel like playing a game. The user sees at a
  glance what each view wants of them, every state they reach offers a move, and
  a move the page can draw shows its result at once. Test a draft by reading only
  its headings, pictures and controls, the way a player takes in a board. If that
  leaves a view's point or move unclear, the view describes in words something it
  should draw or let the user do.
- **Concrete.** Show the user the thing they are judging, not a description of
  it: an interface as it looks, a behavior running, a mechanism or proposal as a
  drawing, a numeric relationship as a chart, wording as the text itself. Show
  code as text only when its wording is what the user judges. When they judge
  what code does, such as what it draws, overrides or calls, show that effect.
  Whatever the user would have to picture from your words to judge, show
  instead. Each option of an ask shows what choosing it gives them. Use words
  for what the thing can't show: the claim, the reason, the cost.
- **Current.** The page shows where the work stands now, not how it got there
  ("Keep the user current").
- **Personalized.** The user's word decides the page's content and presentation.
  Leaf's defaults apply only where they have said nothing.
- **Extensible.** Leaf has a small core and default packages. Independently
  authored packages use the same declared interfaces as the defaults.

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
   the candidate itself (`references/authoring-asks.md`). Running `page init`
   again with a package adds it to a page already written.
2. Read all of `references/page-authoring.md`, then each reference the page
   needs, listed under "Author a version" below. Choose elements and class idioms
   from the registry as it says, and read their examples and instructions first.
   Show each view's subject as **Concrete** says, so the page carries pictures:
   drawings, captures, charts or the thing running. Put the picture in the view
   that needs it; one on another page or in another section shows the user
   nothing while they judge this view. A draft of only prose, tables, lists and
   code is describing what it should show, unless the user is judging the words
   or exact values themselves, as in a text edit, a message or a lookup table.
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
   and asks it adds. A quick page takes this review once a stamp makes it a record.
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

| Session | Contract |
| --- | --- |
| Claude Code | `references/harness-claude-code.md` |
| Pi | `references/harness-pi.md` |
| Codex with `LEAF_CODEX_APP_SERVER`, or an App Server endpoint supplied by the user | `references/harness-codex-app-server.md` |
| Other Codex tasks, including the desktop app and IDE | `references/harness-codex.md` |

The desktop Codex app's own App Server exposes no endpoint Leaf can use, so its
pages follow the ordinary Codex contract. Deliveries keep arriving under the
contract you picked. `references/codex-setup.md` owns terminal App Server setup.

## Stay responsive

`references/conversation-loop.md`, "When to write", owns the immediate reply and
work status for each user update. For work that would delay the next update,
follow its "Long-running work": background workers do the work while you keep
the page and answer the user.

## Page contract

Unless the user sets the page's shape or depth, a Leaf page is a short sequence
of visually distinct, self-contained views. Each view makes one point, shows one
state or offers one move, so the user takes it in at a glance and moves on;
disclosures hold supporting detail out of that path. Each view shows its subject
as **Concrete** says (`references/page-authoring.md`, "Show the subject").

The page's shape follows the subject: prose read in order, regions read side by
side on a sidebar page, or a workspace the user moves through instead of
scrolling. A Layout class on `main` sets the shape, and the page's own CSS
adjusts it. `references/page-authoring.md`, "Composing a page", owns the choice
of shape, `references/page-layout.md` each shape's geometry, and
`references/authoring-asks.md` where each ask goes.

Include only controls and gestures that advance the user's task. Widget actions,
resolutions and sign-offs can be undone; sent words stay in the log.

## Keep the user current

By default the page is the shared canvas and current record of the subject.
Whenever the user returns, it should be the page you would write today from what
you now know. Its title, lede and headings say what is true now. The column holds
the open work and open questions, led by what waits on the user and what comes
next. Finished work, cut to its outcome, sits collapsed after them or on its own
tab, so the user finds each outcome without reconstructing a thread or chat. The
banner says what you are doing now; threads carry discussion and rationale.

When work lands, a decision is made or your understanding changes, reread the
whole page and write the page you would hand over now, instead of noting the
change where its subject is mentioned. Lead with what is still open and what the
change opens, such as the next piece of work or a decision it raises
(`references/authoring-revisions.md`, "Keep the current page current", says how
finished work leaves the column and how to keep user state). Correct wrong
figures in place and remove superseded claims; the `page stamp` changelog and
the event log keep the history. Save freely and stamp meaningful checkpoints.

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
- `references/authoring-asks.md`: when the page or your reply leaves anything for
  the user to decide or sign off, before choosing its widgets.
- `references/authoring-revisions.md`: before changing a handed-over page,
  proposing a rewrite, using a user-owned draft, or revising the page's current state.
- `references/authoring-evidence.md`: for work updates or reviews, before drawing
  a figure, or using measured facts, diagrams, charts, source files or text edits,
  images, recordings, or before/after captures.

### First handoff

- `references/conversation-loop.md`: before a page handoff, starting work on the page,
  work long enough to delegate, or asking the user to do something no ask answers.
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
  them: `references/module-reading.md` for reading the page, content helpers, asks
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
