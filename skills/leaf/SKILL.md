---
name: leaf
description: Builds an interface for the user to inspect, explore and act on their work with an agent, and responds to input from an existing Leaf page. Use for “explain this in HTML,” “write up the findings,” “show me the options,” building a playground, explorer, simulator, or interactive tool, work whose progress or review belongs in a shared page, a `leaf_delivery` tool output, or a `leaf-delivery` message.
allowed-tools:
  - Bash(leaf:*)
  - Bash(jq:*)
---

Develop material the user can judge or use directly. The user can inspect and
operate it, comment on exact passages and steer revisions.
Keep the page current and give their questions and changes of direction priority.

The input is either work to develop on a page or a delivery from a page already
handed over: a `leaf_delivery` tool output, a `leaf-delivery` element, or the
envelope `leaf wait` printed. A delivery starts at step 7 below; continue that
page rather than initializing or handing it over again. With no subject in
`$ARGUMENTS`, develop the work already under discussion.

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

Run commands as `leaf` when the harness puts its launcher on `PATH`. Otherwise
use `../../bin/leaf` from the directory holding this `SKILL.md`. If the
file is missing, report that the plugin payload is incomplete.
Pages usually live at `~/.local/state/leaf/pages/<slug>/`,
but every command takes the directory explicitly; export or copy anything that
must outlive the page directory.

1. Read `references/conversation-loop.md`, "When to write", to record the work
   you take on. Run `leaf page init <page>`, adding a package when the page needs
   its vocabulary or instructions: `leaf page init --package diagram --package diff <page>`.
   `references/packages.md`, "Package reach", lists the packages. Use
   `playground` when the user explores candidates or tunes a configuration before
   sending it; its choices can contain the previews themselves. Simple choices
   use `lf-options` (`references/authoring-on-me.md`). Running `page init`
   again with `--package` replaces the page's packages, so name every package the page keeps.
   Personal themes and their author instructions are discoverable with
   `leaf theme list`; `references/package-themes.md`, "Personal themes", covers
   choosing one for the task and how the page captures it.
2. Read `references/page-authoring.md` and choose the subject and concrete case
   the user will examine. Construct that subject in the chosen situation, then
   compose the explanation around the result. Follow
   `references/authoring-revisions.md` when changing an existing page, then write
   `<page>/index.html`. Each valid save becomes the live immutable revision. An
   invalid save leaves the last valid one live and reports the error in page state
   and the browser. You write `index.html` and `page/`; only Leaf writes revisions
   and version mappings.
3. **Check the page.** Before you first hand the page over, run
   `leaf page check <page>` and fix every failure. A revision that answers a user's
   message, even on a page you review, goes straight to the reply. The reply checks
   your saved edits and is refused over an error; fix it and reply again. Each valid
   save is already live on the user's page, so a separate check only delays the
   answer they are waiting for.
4. **Review an important page in the browser.** `leaf page check <page> --render`
   and the reading in `references/page-checkpoints.md`, "Pre-handover review",
   find what the markup check can't, such as a table squeezed to a word a line or a
   layout that breaks at phone width. They take minutes, so give them to the pages
   that matter. A page matters more the longer the user relies on it, whether past
   this conversation or through a long one, the more it holds, and the more of its
   layout you wrote yourself rather than took from the vocabulary. It matters less
   the more urgently the user is waiting for it. A quick page, one the user reacts to
   once and then revises or drops, needs no review. Review an important page before
   its first handoff and again at each checkpoint, such as the user approving a plan
   or settling a stage of the work, after the reply that answers it.
5. **Stamp a record.** A record is a page used beyond this conversation, so it is
   always important. Stamp it after each review, its first and each later one:
   `leaf page stamp <page> --text "<changelog>"`. `references/page-checkpoints.md`,
   "Stamp checkpoints", says which checkpoints a record has.
6. Read the contract that "Harness selection" below picks. Follow
   `references/conversation-loop.md`, "Page availability and handoff", and serve and hand
   over the page the way that contract says.
7. When a delivery arrives, read `references/event-batches.md`, the harness
   contract and, for user messages, `references/threads.md`, and answer every
   event as they say. Say what you are doing before you do it
   (`references/conversation-loop.md`, "When to write").
8. Stamp checkpoints and end the page as `references/page-checkpoints.md` says.

## Harness selection

Pick the contract for the session that owns the page:

| Session     | Contract                            |
| ----------- | ----------------------------------- |
| Claude Code | `references/harness-claude-code.md` |
| Pi          | `references/harness-pi.md`          |
| Codex       | `references/harness-codex.md`       |

## Stay responsive

The parent session owns the Leaf conversation:
answer the user, keep the page current, and direct background subagents doing the
substantive research, editing and testing. Keep direct answers, revisions of existing material,
and the review and integration of worker results with you. Having more work to do
is a reason to delegate it, while you remain available for the user's next move.

`references/conversation-loop.md`, "Long-running work", owns worker briefs,
results and work that continues beyond your turn. If subagents are unavailable,
run long operations in the background and follow your harness's delivery loop
between bounded steps.

## Page contract

`references/page-authoring.md` owns content, reading cost and composition. `references/page-layout.md` owns Layout geometry;
`references/authoring-on-me.md` owns the questions and choices you put to the user.

Choose controls, gestures and options whose benefit to the user's task outweighs
the attention and effort they require. Remove redundant actions before making
them visually quieter. Widget actions and resolutions can be undone;
sent words stay in the log.

## Keep the user current

Follow `references/authoring-revisions.md`, "Keep the current page current", when
work lands, a decision is made, or your understanding changes.

## Follow the user's preferences

When the user states a preference meant for every page, save it in your
harness's memory, where later sessions read it; Leaf keeps none.

## Improve Leaf through use

When Leaf gets in your way through friction, ambiguity or a missing capability,
tell the user what you wanted to do and how the interface blocked it. Explain the
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
- `references/authoring-on-me.md`: when the page or your reply leaves anything for
  the user to decide or approve an action, before choosing its widgets.
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
- `references/page-checkpoints.md`: before a pre-handover review, stamping,
  or ending a page.

### Serve or extend a page

- `references/serving-pages.md`: for the first handoff, `--export`, an unreachable
  URL, whether an operation changes a page's URL, `--host`, a persistent page,
  re-vendoring a served page, a page a Leaf update broke, or resuming another
  session's page.
- `references/module-authoring.md`: before writing or changing browser behavior in
  a page script, page-owned widget or package widget. Then, as the behavior needs
  them: `references/module-reading.md` for reading the page, content helpers, obligations
  and history; `references/module-state.md` for recorded state, data, authenticated
  HTTP connections and LLM generation;
  `references/module-input.md` for commands, focus and text entry;
  `references/module-scroll-and-motion.md` for scrolling, travel and motion; and
  `references/module-annotations.md` for margin entries, visual parts and Threads.
- `references/interface-goals.md`: before writing a widget, package CSS, or page CSS
  that adds controls or changes what moves when the page changes.
- `references/packages.md`: for package design, registry declarations, or a design
  comment whose fix belongs in a package; `references/package-themes.md` for theme
  rules; `references/package-data.md` for user state and data contracts.

### Set up a Codex connection

- `references/codex-setup.md`: when setting up a terminal App Server connection.
- `references/codex-watcher.md`: only after the user explicitly authorizes a
  visible Codex watcher task. Follow it before handing over the page.
