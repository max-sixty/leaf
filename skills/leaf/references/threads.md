# Threads

Open a thread when the answer depends on the user. Anchor it with a quote for a
passage, a section id for a diagram or image, a declared part for one box within a
visual, or nothing for the page as a whole:

```bash
leaf thread open <page> --quote "<passage in the current page>" --text "…"
leaf thread open <page> --section <element-id> --text "…"
leaf thread open <page> --section <diagram-id> --part node:<source-id> --text "…"
leaf thread open <page> --text "…"
```

`leaf thread open` anchors in the active revision as the user sees it. Quote exact
words from the page's HTML that the user can see, within one widget part. The
command refuses a quote that matches more than one place, or is retired, replaced,
or crosses a boundary, rather than open a thread with no anchor. The thread's id is
the `id` of its opening comment, in the record the command prints.
`leaf page state <page> <id>`, `leaf thread reply`, `edit` and `resolve` take the
id of any message in the thread.

When the user comments on repeated words that the surrounding text cannot tell
apart, Leaf keeps the quote but not which copy they meant. The comment has
`anchor.detached: true`, and the panel's **Not located** filter lists it.

When you open a thread, title it with `--title`, a few words naming its subject in
the thread panel. When the user opens a thread, Leaf usually titles it as they post;
if it is still untitled when you answer, the event's `handling` asks you to add
`--title`.

```bash
leaf thread open <page> --section <element-id> --title "Afternoon workshop" --text "…"
leaf response reply <answer.ref> --done --title "Afternoon workshop" --text "…"
```

Titles are plain text, at most 80 characters. Keep a title stable. When it no
longer describes the discussion, rename it with
`leaf thread edit <page> <message-id> --title "<a few words>"`, which adds no
message.

Add `--markup` for an HTML fragment after the text: a native table, a bounded log, or
a small question using `lf-ask` and `lf-options`. Native HTML needs no widget
wrapper. Its ids must be new, used in no version of the page and no earlier
message. Leaf checks markup as it checks a page, and refuses document settings or a
stylesheet for the whole page. An `lf-sample` template gives the user a live
practice page in the thread (`live-samples.md`).

```bash
leaf response reply <answer.ref> --done --text "The deploy passed." --markup '<details><summary>Deploy log</summary><pre>Ready&#10;Done</pre></details>'
```

Leaf checks markup when you post it but does not draw it. If a data widget, such as a
chart, fails to draw, you get an `error` event when the user opens the thread; answer
with a corrected reply.

The thread panel is a narrow column, so a paragraph that reads fine in chat is a wall
there. Say what changed or where to look in a sentence or two, or one short item per
point; the page carries the evidence. Record a decision, result, or deferred work on
the page and link it from the reply with a fragment link such as
`[the decision](#decision)`, which opens any tab or group hiding its target. Where
the reasoning matters to someone using the result, keep the thread anchored to that
section.

A reply renders as Markdown. Use `--text` for a one-liner, and pass anything longer
on stdin from a file:

```bash
leaf response reply <answer.ref> --done --text "…"
leaf response reply <answer.ref> --done < reply.md
```

A user's message can carry a pasted image or a **Capture area** of the page; the
delivery says how to read it. To send an image, run `leaf page media <page> <file>`
and put the `path` it prints in your text as a Markdown image.

Pass a delivered answer's whole `ref` to `leaf response reply <answer.ref>`; it needs
no page path or message id. While the session it was delivered to holds the page,
`leaf page state` shows the same `ref` on the update's `answer`. A reply on a `ref`
delivered before the user's newer correction does not answer that correction.

Save any source edit before replying: the reply checks the saved `index.html` and
makes it the active revision with the answer. Rerunning an answer with the same
`ref` adds nothing; each `--ephemeral` progress line posts. When no answer is
coming, `--failure <code>` posts a failure receipt, which settles the input without
reopening a resolved thread.

When an answer has `writer: "turn"`, your turn's final text answers it (your
harness's "Replies"). Use `leaf response reply` instead when the answer needs markup,
an ask, a to-do, a title, or a moved anchor. To have a command hub worker answer,
forward it the `answer.ref` as that package's coordinator instructions say.

## Preserve revised anchors

When a revision rewrites a quoted passage, check every open thread on it, including
ones you are not answering this turn. `leaf page check` lists each open thread whose
anchor no longer resolves and where activation will move it: to its section if that
survives, otherwise detached. The move adds no message and answers nothing.

Where you know what replaced the passage, move the thread onto it in the reply that
reports the change, with `--section`, narrowed by `--quote` or, in a diagram,
`--part`:

```bash
leaf response reply <answer.ref> --done --section <element-id> --quote "<new passage>" --text "Updated this and moved the thread to the result."
leaf response reply <answer.ref> --done --section <element-id> --text "Updated this and moved the thread here."
leaf response reply <answer.ref> --done --section <diagram-id> --part node:<source-id> --text "Updated this node and moved the thread here."
```

When the subject itself leaves the page, detach the thread rather than moving it onto
nearby content:

```bash
leaf response reply <answer.ref> --done --detach --text "Removed this; the thread no longer has a page target."
```

A detached thread stays open in the panel, its passage marked as gone from this
version, and the **Not located** filter lists it. `page state` shows a null anchor,
with the old one in `detached_from`. A later reply may move it to a real replacement;
open a new thread for a different subject. Don't resolve a thread to get rid of an
anchor you removed: Leaf leaves a resolved thread's anchor as it was, so if the user
reopens it, it points at something the page no longer shows.

Every answer declares what it leaves the thread with:

- `--done`: it delivers what the message asked for.
- `--ask`: its prose asks the user something back. The reply becomes an ask,
  `reply:<message-id>` in `page state`'s `asks`, until they answer in the thread or
  you end it ([The On lists](conversation-loop.md#the-on-lists)).
- `--todo "<what you owe>"`: it promises work it does not deliver, and opens that
  to-do on the thread under the reply's id until `leaf task end <page> <reply-id>`
  ([Long-running work](conversation-loop.md#long-running-work)).

```bash
leaf response reply <answer.ref> --ask --text "Which store should own it?"
leaf response reply <answer.ref> --todo "Rebuild the banner quieter" --text "Rebuilding it; it lands in v4."
```

The answer's head shows the declaration: **Waiting on me** while its ask is open, and
**To-do open** until you end the to-do. A promise declared `--done` reads as
finished work.

To post in a thread that owes no reply, use
`leaf thread reply <page> <message-id>`. It takes the same content and anchor
options, and `--ask` or `--todo`. While the thread owes a reply, Leaf refuses an
ordinary `leaf thread reply`; answer with `leaf response reply <answer.ref>`, and
post progress on that input the same way.

### Progress messages

Use `--ephemeral` for progress while work is underway:

```bash
leaf response reply <answer.ref> --ephemeral --text "Checking the keyboard route."
```

It does not answer the update, but on an update you owe it starts the update, and
its text becomes the **Working** line in the banner, so keep it to one line
([conversation loop, "When to write"](conversation-loop.md#when-to-write)). In a
thread that owes no reply, use `leaf thread reply --ephemeral`.

The thread shows the latest progress as one dim working message above its reply box,
with its author and posting time. Progress never counts as unread. Your next ordinary
reply takes its place, with the progress folded behind it. Progress carries only text;
asks, to-dos, markup, anchor
moves and failure receipts each need a reply of their own.

A widget in a reply's markup whose registry entry declares `x-awaits` is already an
ask, and keeps its thread "My turn" until the user answers it. Leaf refuses `--ask`
on a reply that carries one.

Correct a message you or an earlier agent wrote, without adding a turn:

```bash
leaf thread edit <page> <comment-or-reply-id> --text "Corrected wording."
```

The page labels it `edited`, and the log keeps every wording. Only the text changes;
markup stays as it was sent. The user can rewrite their own messages too. That
arrives as an `edit` event with the new `text` and the `was` it replaced, and you owe
it an answer like any reply.

An ordinary reply leaves the thread open, or reopens it, so the user can inspect the
answer; the user usually resolves it. Resolve it yourself only when the user asks,
when an event's `handling` says to, or when no review or follow-up could change the
outcome, which finishing the work does not show by itself. When unsure, leave it
open. First answer any unanswered user message in it:

```bash
leaf thread resolve <page> <message-id>
```

## What the user has read

Each thread in `leaf page state <page>` and `leaf page state <page> <thread-id>`
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
with `leaf page state <page> <thread-id>` and choose a contiguous range that fits the
topic, starting and ending on spoken messages rather than reactions. Leave out
messages whose wording still matters to the current exchange. Summarize the range's
decisions, reasoning, and open questions in Markdown prose, and put its outcomes in
the page too:

```bash
leaf thread summarize <page> --from <first-message-id> --through <last-message-id> < summary.md
```

The summary replaces the range in the thread, and the originals stay available to
unfold. It answers nothing. When summarizing again, read the originals rather than
only the older summary. A recap in an ordinary reply folds nothing.

The fold is labeled “Earlier discussion” unless you set `--label`. To fold messages
without a summary, pass an empty `--text`:

```bash
leaf thread summarize <page> --from <first-message-id> --through <last-message-id> --label 'Previous progress messages' --text ''
```

A summary that overlaps an earlier one replaces it, and summaries of separate ranges
both stay. Editing a message inside a summary with prose cancels that summary, so
stale prose cannot hide the correction; a fold without prose stays.
