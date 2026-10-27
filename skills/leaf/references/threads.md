# Threads

Open a thread when the answer depends on the user. Add `--obligation` to put the
message on their On me list until they answer. The message itself supplies the
request; no widget or markup is needed. Anchor it with a quote for a passage, a section id
for a diagram or image, a declared part for one box within a visual, or nothing for
the page as a whole:

```bash
leaf thread create <page> --quote "<passage in the current page>" --obligation --text "…?"
leaf thread create <page> --section <element-id> --text "…"
leaf thread create <page> --section <diagram-id> --part node:<source-id> --text "…"
leaf thread create <page> --obligation --text "…?"
```

For a diagram, percent-encode the entire source id in the part token:
`node:Line%20Item` names `Line Item`.

`leaf thread create` anchors in the active revision as the user sees it. Quote exact
words from the page's HTML that the user can see, within one widget part. The
command refuses a quote that matches more than one place, or is retired, replaced,
or crosses a boundary, rather than open a thread with no anchor. The thread's id is
the `id` of its opening comment, in the record the command prints.
`leaf page state <page> <message>`, `leaf thread reply`, `edit` and `resolve` take
the id of any message in the thread.

Link directly to a thread by adding `thread=<message-id>` to the page URL's query
parameters, preserving any existing access parameters: `?thread=<message-id>`, or
`&thread=<message-id>` when a query is already present. Use a URL without a fragment
to open the thread; an authored `#element-id` takes precedence and reaches that
passage. The link opens the thread's usual card or reader, including a page-level
thread with no anchor. Input during startup cancels the automatic opening.

When the user comments on repeated words that the surrounding text cannot tell
apart, Leaf keeps the quote but not which copy they meant. The comment has
`anchor.detached: true`, and Threads keeps it with the quote it was about.

When you open a thread, title it with `--title`, a few words naming its subject in
Threads. When the user opens a thread, Leaf usually titles it as they post;
if it is still untitled when you answer, the event's `handling` asks you to add
`--title`.

```bash
leaf thread create <page> --section <element-id> --title "Afternoon workshop" --text "…"
leaf thread reply <answer.ref> --done --title "Afternoon workshop" --text "…"
```

Keep a title stable. When it no
longer describes the discussion, rename it with
`leaf thread edit <page> <message> --title "<a few words>"`, which adds no
message.

Add `--markup` for an HTML fragment after the text: a native table, a bounded log, or
a small question using `lf-ask` and `lf-options`. Native HTML needs no widget
wrapper. Its ids must be new, used in no version of the page and no earlier
message. Leaf checks markup as it checks a page, and refuses document settings or a
stylesheet for the whole page. An `lf-sample` template gives the user a live
practice page in the thread (`live-samples.md`).

```bash
leaf thread reply <answer.ref> --done --text "The deploy passed." --markup '<details><summary>Deploy log</summary><pre>Ready&#10;Done</pre></details>'
```

Leaf checks markup when you post it, and draws a data widget, such as a chart or
diagram, once first: a widget that fails to draw refuses the message with its error.
Fix it and post again. Where Leaf has no browser, the failure reaches you instead as an
`error` event when the user opens the thread; answer with a corrected reply.

A thread shows in a narrow card or panel, so a paragraph that reads fine in chat is a
wall there. Say what changed or where to look in a sentence or two, or one short item per
point; the page carries the evidence. Record a decision, result, or deferred work on
the page and link it from the reply with a fragment link such as
`[the decision](#decision)`, which opens any tab or group hiding its target. Where
the reasoning matters to someone using the result, keep the thread anchored to that
section.

A reply renders as Markdown. Use `--text` for a one-liner, and `--file`, or a
heredoc on stdin, for anything longer.

To send an image, run `leaf page media <page> <file>`
and put the `path` it prints in your text as a Markdown image.

`leaf thread reply` takes either a delivered `answer.ref` or a page and message id:

```bash
leaf thread reply <answer.ref> --done --text "The deploy passed."
leaf thread reply <page> <message> --text "The monitoring window has ended."
```

Use the whole `answer.ref` when answering a delivered update or posting progress on
it. The reference identifies the page, thread and exact input being answered.
Use the page and message id to add a message when the thread owes no reply.
While the session an update was delivered to holds the page,
`leaf page state` shows the same `ref` on the update's `answer`. A reply on a `ref`
delivered before the user's newer correction does not answer that correction.

Successful answers check the saved `index.html` and make it the active revision
with the answer; the first answer on a revision also notes the advice `page check`
gives. Progress and failure reports use the active revision without checking or
publishing an in-progress draft. Rerunning an
answer with the same `ref` adds nothing.

When an answer has `writer: "turn"`, your turn's final text answers it (your harness's
"Replies"). Use `leaf thread reply` instead when the answer needs markup, a question
back, a to-do, a title, or a moved anchor. To have a command hub worker answer, forward
it the `answer.ref` as that package's coordinator instructions say.

## Preserve revised anchors

When a revision rewrites a quoted passage, check every open thread on it, including
ones you are not answering this turn. `leaf page check`, and the first successful
reply on a revision, list each open thread whose anchor no longer resolves and where the
revision moves it: to its section if that survives, otherwise detached.

Where you know what replaced the passage, move the thread onto it in the reply that
reports the change, with `--section`, narrowed by `--quote` or, in a diagram,
`--part`:

```bash
leaf thread reply <answer.ref> --done --section <element-id> --quote "<new passage>" --text "Updated this and moved the thread to the result."
```

When the subject itself leaves the page, detach the thread rather than moving it onto
nearby content:

```bash
leaf thread reply <answer.ref> --done --detach --text "Removed this; the thread no longer has a page target."
```

A detached thread stays open in Threads, its quote marked as gone from this
version. A later reply may move it to a real replacement;
open a new thread for a different subject. Don't resolve a thread to get rid of an
anchor you removed: Leaf leaves a resolved thread's anchor as it was, so if the user
reopens it, it points at something the page no longer shows.

Every answer declares whose move it leaves:

- `--obligation`: the user's. It leaves them a decision, or something to try or
  review before making one, or asks them for an answer or permission. It creates
  `message:<its id>` on On me until their next reply or a settling reaction answers
  it, or they resolve the thread, so the answer stays on their list even where the
  decision it informs is already there. A widget in `--markup` can instead register
  the answer it captures ([The On lists](conversation-loop.md#the-on-lists)).
- `--todo "<what you owe>"`: yours. It promises work it does not deliver, and opens
  that to-do on the thread under the reply's id until `leaf task end <page> <reply-id>`
  ([Long-running work](conversation-loop.md#long-running-work)).
- `--done`: nobody's. It delivers what the message asked for and leaves the user
  nothing to decide.

```bash
leaf thread reply <answer.ref> --obligation --text "Which store should own it?"
leaf thread reply <answer.ref> --todo "Rebuild the banner quieter" --text "Rebuilding it; it lands in v4."
```

The answer's head shows what it leaves: **Waiting on me** while its question is open,
and **To-do open** until you end the to-do. A promise declared `--done` reads as
finished work.

### Progress messages

Use `--ephemeral` for progress while work is underway:

```bash
leaf thread reply <answer.ref> --ephemeral --text "Checking the keyboard route."
```

It does not answer the update, so a turn whose final message is the answer still
posts that message. On an update you owe it starts the update, and
its text becomes your line in Leaf's panel status, so keep it to one line
([conversation loop, "When to write"](conversation-loop.md#when-to-write)). In a
thread that owes no reply, use `leaf thread reply <page> <message> --ephemeral`.

The thread shows the latest progress as one dim working message where you posted it,
Progress never counts as unread. Your next ordinary reply replaces the preceding
progress.
Progress carries only text;
questions, to-dos, markup, anchor moves and failure receipts each need a reply of
their own.

Any widget in a reply's markup whose registry entry declares `x-awaits`, such as an
`lf-options` or an `lf-ask`, waits on the user and keeps its thread at "Your turn"
until they answer it. A thread you open waits on nobody by itself: `--obligation` registers the
message's request without markup. A user task attached to the thread instead waits
for Done; discussing it does not complete it.

Correct a message you or an earlier agent wrote, without adding a turn:

```bash
leaf thread edit <page> <message> --text "Corrected wording."
```

The page labels it `edited`, and the log keeps every wording. Only the text changes;
markup stays as it was sent.

An ordinary reply leaves the thread open, or reopens it, so the user can inspect the
answer; the user usually resolves it. Resolve it yourself only when the user asks,
when an event's `handling` says to, or when no review or follow-up could change the
outcome, which finishing the work does not show by itself. When unsure, leave it
open. First answer any unanswered user message in it:

```bash
leaf thread resolve <page> <message>
```

## What the user has read

Each thread in `leaf page state <page>` and `leaf page state <page> <message>`
lists under `unread` your messages the user has not read in their current wording. A
message counts as read once its whole body has been on screen, once the user marks
the thread read, or once they act in the thread after it: reply, react, answer a
widget, resolve or reopen. `leaf thread edit` makes a message unread again. Unread
does not change whose turn it is: an unread message needs no follow-up, and a read
one is not an answer.

## Summarize a long discussion

When a thread's topic has moved on, or settled detail buries the current exchange,
summarize the earlier discussion as part of answering new input, without waiting to
be asked. New input may carry `summary_hint`, a suggested range. Read the originals
with `leaf page state <page> <message>` and choose a contiguous range that fits the
topic, starting and ending on spoken messages rather than reactions. Leave out
messages whose wording still matters to the current exchange. Summarize the range's
decisions, reasoning, and open questions in Markdown prose, and put its outcomes in
the page too:

```bash
leaf thread summarize <page> --from <first-message-id> --through <last-message-id> --file summary.md
```

The summary replaces the range in the thread, and the originals stay available to
unfold. It answers nothing. When summarizing again, read the originals rather than
only the older summary. A recap in an ordinary reply folds nothing.

To fold messages
without a summary, pass an empty `--text`:

```bash
leaf thread summarize <page> --from <first-message-id> --through <last-message-id> --label 'Previous progress messages' --text ''
```

Editing a message inside a summary with prose cancels that summary, so
stale prose cannot hide the correction; a fold without prose stays.
