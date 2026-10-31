---
name: leaf
description: Builds an interface for the user to inspect, explore and act on their work with an agent, and responds to input from an existing Leaf page. Use for “explain this in HTML,” “write up the findings,” “show me the options,” building a playground, explorer, simulator, or interactive tool, work whose progress or review belongs in a shared page, a `leaf_delivery` tool output, or a `leaf-delivery` message.
allowed-tools:
  - Bash(leaf:*)
  - Bash(jq:*)
  - Bash(mktemp:*)
---

Develop the work with the user on a live page. They can inspect the result, try it,
comment on exact passages and steer revisions. Keep the page current, and give their
questions and changes of direction priority.

With no subject in `$ARGUMENTS`, continue the work already under discussion. A
`leaf_delivery` tool output, `leaf-delivery` element or envelope from `leaf wait`
is input from an existing page: start at **Respond to input**, using that page.

$ARGUMENTS

Read [SOUL.md](SOUL.md) before authoring or responding on a Leaf page.

## Must remember

Everything waiting on the user is an obligation on their On me list, including
each decision you leave to them that your next step doesn't depend on. Register
it before a page heading, a chat open item or a `needs input:` line mentions it.
`references/conversation-loop.md`, "The On lists", owns registration and
reconciliation.

## Author the page

Record the work you take on as `references/conversation-loop.md`, "When to write",
says. Initialize a new page with `leaf page init <page>`, adding the packages its
content needs: `leaf page init --package diagram --package diff <page>`.
`references/packages.md`, "Package reach", lists the packages. Use `playground`
when the user explores candidates or tunes a configuration before sending it; its
choices can contain the previews themselves. Simple choices use `lf-options`
(`references/authoring-on-me.md`). Running `page init` again with `--package`
replaces the page's packages, so name every package the page keeps. Personal themes
and their author instructions are discoverable with `leaf theme list`;
`references/package-themes.md`, "Personal themes", covers choosing one and how the
page captures it.

Read the applicable references under **Author a version** below. For substantial
new material, including a new section on an existing page, start an author without
inherited conversation (`fork_turns: "none"` where available). Give it the reader's
question, task, relevant facts and constraints, initial content and state, the page
registry, `references/page-authoring.md` and a fresh output directory (`mktemp -d`).
Ask it to construct the subject the page discusses, following "Develop the work",
and return finished files and captions. Keep the research history and existing page
with you. Integrate the returned material following "Composing a page" and
`references/authoring-on-me.md` for decisions left to the user. When subagents are
unavailable, build the material directly.

Follow `references/authoring-revisions.md` when changing an existing page, then
write `<page>/index.html`. Each valid save becomes a live immutable revision. An invalid save leaves the last valid one live
and reports the error in page state and the browser. You write `index.html` and
`page/`; only Leaf writes revisions and version mappings.

Choose controls whose benefit outweighs their attention and effort; remove
redundant actions before making them visually quieter. Widget actions and
resolutions can be undone; sent words stay in the log.

## Publish and review

Before the first handoff, run `leaf page check <page>` and fix every failure.
A revision answering a user's message, even on a page you review, goes straight
to the reply: the reply checks the saved edits and refuses errors. Fix any error and
reply again. Each valid save is already live, so a separate check delays the answer
the user is waiting for.

Review an important page in the browser before its first handoff and at later
checkpoints, such as an approved plan or a settled stage of work. At those later
checkpoints, reply before reviewing. Use `leaf page check <page> --render` and
`references/page-checkpoints.md`, "Pre-handover review". They find problems markup
checks can't, such as unreadable tables and broken phone layouts, but take minutes.
Give that time to pages the user relies on longer, pages with more content, and
pages with more custom layout. Weigh that against how urgently the user is waiting.
A quick page the user reacts to once and then revises or drops needs no browser
review.

A record is a page used beyond this conversation, so it is always important.
After each review of a record, run
`leaf page stamp <page> --text "<changelog>"`.
`references/page-checkpoints.md`, "Stamp checkpoints", owns its checkpoints.

Read the owning session's harness contract below and follow it with
`references/conversation-loop.md`, "Page availability and handoff", to serve and
hand over the page.

## Respond to input

Read `references/event-batches.md`, the owning session's harness contract and, for
user messages, `references/threads.md`. Answer every event as they say. Say what
you are doing before you do it (`references/conversation-loop.md`, "When to write").
Continue the existing page; it needs no new initialization or handoff.

Whenever the user returns, the page should be the one you would write today from
what you now know. When work lands, a decision is acted on or your understanding
changes, reread the whole page and bring all of it up to date in that revision,
rather than amending the sentences that mention the change: open work and open
questions fill the column, decisions you have acted on become settled records,
finished work shrinks to its outcome out of the way, and superseded material goes
(`references/authoring-revisions.md`, "Keep the current page current"). Stamp
checkpoints and end the page as `references/page-checkpoints.md` says.

## Stay responsive

The parent session owns the Leaf conversation: answer the user, keep the page
current, and direct background subagents doing substantive research, editing and
testing. Keep direct answers, small edits, and review and integration of worker
results with you. Having more work to do is a reason to
delegate it while you remain available for the user's next move.

`references/conversation-loop.md`, "Long-running work", owns worker briefs,
results and work continuing beyond your turn. If subagents are unavailable, run
long operations in the background and follow the harness delivery loop between
bounded steps.

## Commands

Run commands as `leaf` when the harness puts its launcher on `PATH`. Otherwise
use `../../bin/leaf` from the directory holding this `SKILL.md`. If the file is
missing, report that the plugin payload is incomplete. Pages usually live at
`~/.local/state/leaf/pages/<slug>/`, but every command takes the directory explicitly;
export or copy anything that must outlive the page directory.

## Harness selection

Pick the contract for the session that owns the page:

| Session     | Contract                            |
| ----------- | ----------------------------------- |
| Claude Code | `references/harness-claude-code.md` |
| Pi          | `references/harness-pi.md`          |
| Codex       | `references/harness-codex.md`       |

## Follow the user's preferences

When the user states a preference meant for every page, save it in the harness's
memory, where later sessions read it; Leaf keeps none.

## Improve Leaf through use

When Leaf blocks the work through friction, ambiguity or a missing capability,
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
- `references/turn-end-check.md`: in Claude Code, what Leaf's turn-end check asks a
  fork of your session, when one of its messages or records puzzles you.

### Serve or extend a page

- `references/serving-pages.md`: for the first handoff, `--export`, an unreachable
  URL, whether an operation changes a page's URL, `--host`, a persistent page,
  changing a served page's packages, a page a Leaf update broke, or resuming another
  session's page.
- `references/module-authoring.md`: before writing or changing a page-owned or
  package widget, or using a Leaf helper `page-behavior.md` doesn't describe in a page
  script. Then, as the behavior needs them: `references/module-reading.md` for reading the page, content helpers, obligations
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
