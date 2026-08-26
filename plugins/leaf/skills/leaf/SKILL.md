---
name: leaf
description: Presents designs, decisions, findings, or live work as an HTML page the user can comment on and manipulate. Use for “explain this in HTML,” “write up the findings,” “show me the options,” or work whose progress or review belongs in a shared page.
allowed-tools:
  - Bash(leaf:*)
---

Present the session's subject as a live HTML page. The user comments on exact
passages, acts through the page's widgets, and follows revisions in place. With
no subject in `$ARGUMENTS`, use the work already under discussion.

$ARGUMENTS

## Return to the user

Once the page has a URL, repeat that exact URL every time you return to the user
in chat, including interim updates, questions, and the final handoff.

## Page contract

The subject decides the shape. Use options for decisions, boards for movable
work, milestones for stages, metrics for measurements, and prose where no other
shape fits. What stands open in the column is what the reader has to take from
the page, and its backing sits under `<details>`. `leaf page catalog
<page>` is the authority for the vendored vocabulary and theme.

The stakes decide the ceremony. A quick page — an idea, a sketch, options put
up for the user to react to — goes out on the markup check publishing already
runs. A finished record also passes the browser gate and a read-through before
its URL first reaches the user, and a quick page that grows into the record
takes that review then. Both kinds set status and enter the wait loop.

Packages may also carry guidance for roles involved in the page. `leaf page
guidance <page>` lists the available audiences, and `leaf page guidance <page>
<audience>` prints one guide. Read the assigned audience before acting in that
role; `page catalog` already includes the `author` guide.

Every ask has a control beside its evidence. A page that needs approval declares
sign-off; an informative page does not. Publish when the subject changes and use
status detail for finer progress between versions. Keep the waiter alive while
work continues so comments can affect the next step.

## Page and launcher

Pages conventionally live at `~/.local/state/leaf/pages/<slug>/`, though every
command takes the directory explicitly. A page holds immutable versions, the
event log, service state, and its vendored layer. Export or copy anything that
must outlive that live state.

Resolve `${CLAUDE_SKILL_DIR}/../../bin/leaf` and use that launcher for every
command shown as `leaf`. Claude Code also puts it on `PATH`. If the resolved file
is absent, report that the plugin payload is incomplete. A checkout keeps it at
`plugins/leaf/bin/leaf`.

## Build and hand over

1. Run `leaf page init <page>`, then run and read
   `leaf page catalog <page>`.
2. Read `references/page-authoring.md`. Write the first version to
   `<page>/versions/v1.html` using only the catalog's tags, attributes, and
   idioms.
3. Start the service with `leaf server start <page>` and retain its exact URL.
   The key in that URL opens the page.
4. Publish with
   `leaf version publish <page> --version 1 --text "<changelog>"`. Publishing
   runs the static markup check.
5. On a finished record, run the pre-handover review in
   `references/page-authoring.md`, including
   `leaf version check <page> --render`, before the URL first reaches the
   user. A quick page goes out on the publish check alone.
6. Read `references/conversation-loop.md`. Set
   `leaf status <page> waiting "<what you want back>"`; leave the detail empty
   on an informational page with no concrete ask.
7. Send the exact URL and one sentence naming the available gesture: comment,
   use the stated control, or approve declared sign-off.
8. Enter the host wait loop defined in `references/conversation-loop.md`.

The conversation reference owns acknowledgement, event processing, later
versions, replies, sign-off, and ending. Follow it before each wait or delivered
batch and before setting the page idle. Never rewrite a version the user has
seen.

## Conditional references

Read references directly from this skill directory. They do not route to one
another.

- `references/page-authoring.md`: before writing or revising a version; its
  pre-handover review before a finished record's handoff.
- `references/conversation-loop.md`: before waiting, processing a delivered
  batch, opening or replying to a thread, or ending a page.
- `references/serving-pages.md`: for `--export`, an unreachable URL, `--host`, a
  standing page, re-vendoring a served page, or resuming another session's page.
- `references/packages.md`: for a package-design request or an event with
  `"about": "layer"`.
- `references/codex-watcher.md`: only after the user explicitly authorizes a
  visible Codex watcher task. Follow it before handing over the page.
