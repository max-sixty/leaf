# Conversation loop

Read this before running `leaf wait`, processing a delivered batch, opening or
replying to a thread, or ending a page.

## Status and handoff

Before a handoff, run:

```bash
leaf status <page> waiting "<what you want back>"
```

The detail names the concrete answer or decision, not the fact that you are
waiting. For an informational page with no concrete ask, leave it empty; the
banner then invites the reader to select text to comment. Follow the main
skill's "Return to the user" rule for every chat message.

While the next move is yours the page is `working`, and a comment you are
answering takes a note naming its thread:

```bash
leaf status <page> working "reading the reconnect traces" --on <thread-id>
```

The note stands under the reader's own words in the panel until you answer that
thread, so a question in hand reads differently from one nobody has looked at.
It is the banner's own claim at a second seat, and one command writes both.

A `working` claim is believed while the turn that wrote it is open. The page is
told when that turn ends, so a claim nothing has renewed within a couple of
minutes of the ending stops being believed, and the banner reports the silence
instead of the work; a claim nobody renews at all ages out after about a
quarter of an hour. Each note carries the same reading at its own thread, so
one delegate still reporting keeps the banner green while another's note goes
quiet under the words it answers.

Renewing it is therefore part of the work and goes with it: a delegate outlives
the turn that started it, and no part of this session can write the claim once
the turn has ended. Give the delegate the launcher path, the page path, the
thread id, and the command above to run as it starts — soon enough to land
inside that couple of minutes — and again whenever what it is doing changes.

## Host wait loops

One unnamed `leaf wait` watches every page the host session owns. A batch begins
with `{"page": …}` and contains that page's events. Name a page only to pick up a
page this session did not serve; `leaf wait <page>` claims it.

- **Claude Code:** start `leaf wait` as a background task and end the turn. Its
  completion becomes host input. Start a fresh background wait after each batch.
- **Codex:** send the URL in an intermediate update, start `leaf wait` in unified
  exec, retain that exact session id, and keep the turn active. Poll the same
  session with empty `write_stdin` calls and long yields. Never detach the wait
  or end the turn expecting completion to start another turn. Start a fresh wait
  after each batch.

An optional Codex watcher requires the user's explicit authorization because it
creates a visible task. Its separate route is in the main skill.

`leaf wait` revives a dead server under its recorded lifetime and reports that on
stderr. Exit 2 means revival failed, every watched page is idle, or an earlier wait
of this session's still holds the watch — leave that one running. A wait that
ends on its own prints its batch or says why on stderr; one that stopped with
nothing printed was stopped by the host, so start another.

## Batch delivery and acknowledgement

Wait prints one page's unacknowledged events as JSON lines. Printing is not
receipt. The wait owner acknowledges only after the complete batch reaches its
next durable consumer.

In the direct loop, the durable consumer is model context. An adapter instead
owns its wait and acknowledgement; it acknowledges after its receiver accepts
the batch, and the receiver does not wait or acknowledge.

If wait output is truncated, acknowledge nothing and rerun with enough output
capacity for the whole batch. After the complete batch reaches its next durable
consumer, the wait owner runs `leaf ack <page> <highest-seq>` for the page the
batch's first line names. If output is lost, follow the same rule. A scalar cursor
cannot represent a missing event in the middle. Acknowledgement is monotonic and
idempotent; an event posted between wait and ack has a higher sequence and stays
pending. Until ack, wait repeats the batch. `leaf events` reads the full log
without acking it.

Treat a page-and-sequence pair already handled in this task as a retry, even if a
later delivery also includes newer events.

## Process every event

After acknowledging a direct batch, set the page `working` and address every
event the wait printed:

- **Comment:** reply in-thread and revise the page when warranted. A comment with
  `"suggestion": true` proposes exact replacement text; take it verbatim or reply
  with the reason for declining it.
- **Layer comment:** an event with `"about": "layer"` changes the relevant Leaf
  layer, followed by re-vendoring, publishing, and an in-thread reply.
- **Page action:** the reader already sees the action applied. Carry its standing
  state into the next version's markup. If you deliberately replace that state,
  use `restated` and explain why in the version note.
- **Undo:** read the named event and the undo as one act. Do not answer or record
  the withdrawn gesture. An undone answering action reopens its thread.
- **Page error:** fix the page or widget and publish the correction. The event is
  diagnostics, so do not reply unless the reader asked about it.
- **Worker report:** carry the report into markup, or mark its element
  `overruled` and state why. A page must not end with unresolved report debt.
- **Thread-widget action:** reply in that same thread. A plain options pick
  answers immediately; a `multiple` group answers only when its `answer` action
  arrives, though every toggle is delivered.
- **Done:** treat it as approval of declared sign-off, not closure of the page.

## Threads

Open a thread when the answer depends on the reader. Use a quote for a passage, a
section id for a diagram or image, and no anchor for the page as a whole:

```bash
leaf comment <page> --quote "<passage in the current page>" --text "…"
leaf comment <page> --section <element-id> --text "…"
leaf comment <page> --text "…"
```

`leaf comment` anchors in the newest published version and reads it as the user
sees it, including edits and retired content. Quote exact visible authored words
inside one widget part. The command refuses ambiguous, retired, replaced, or
cross-boundary text instead of creating a detached comment.

Use `--markup` for an inline widget such as a small `lf-options` question. Thread
markup is frozen in the log; versions neither carry nor revise it. Use a page
widget instead when the question and its answer belong in the final record.

Answer in as few words as the question takes; one sentence is a complete reply.
The panel is a narrow column, so an answer past a few sentences goes in as
separate Markdown paragraphs or a list with one point each. `--text` takes a
one-line answer; longer text comes in on stdin:

```bash
leaf reply <page> --to <thread-id> --text "Yes, and v3 already has it."

leaf reply <page> --to <thread-id> <<'EOF'
Three things put the retry on the client:

- only the client can tell a dropped connection from a slow one
- the client already holds the request body
- retrying on the server would double the write
EOF
```

Fragment links such as `[the decision](#decision)` take the reader to page
content. `--markup` adds a validated widget after reply text; its ids must be new.

The reader closes a thread by default. Resolve it yourself only when they ask or
when the subject has left the page or the work has plainly answered it. Reply
before resolving:

```bash
leaf resolve <page> --to <thread-id>
```

An acknowledged reader message still requires a reply: acknowledgement only
removes it from future batches.

## Publish the next version

Copy the latest published file to the next integer version. Edit that copy and
publish it with a brief changelog:

```bash
cp <page>/versions/v1.html <page>/versions/v2.html
leaf version publish <page> --version 2 --text "<what changed>"
```

Never rewrite a version the reader has seen. The browser follows the new version
automatically. Re-enter the host's wait loop after the batch: `waiting` when the
reader owns the next move, `working` while you continue.

## Sign-off and ending

A `done` event approves the work but does not end the page. Keep the page working
and watched while doing what approval unblocked.

To finish, handle every event in the complete delivered batch and make sure every
acknowledged thread that awaits your answer has one. Publish a final version that
honors standing decisions and reports. `leaf transcript <page>` prints record
debt on stderr and the full exchange as Markdown.

Then run:

```bash
leaf status <page> idle
```

`idle` is the explicit end of the agent side and refuses pending events or an
answered-by-reader thread still awaiting you. It removes the page from the watch;
the last idle page ends the waiter. A normal session-lifetime server process
retires when the page has no live claim, while its enabled service remains
available for a selected successor to revive; it needs no separate stop. A
standing page has a different lifetime and must not be idled merely because one
session's work is over.
