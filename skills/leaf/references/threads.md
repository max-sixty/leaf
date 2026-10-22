# Threads

## Open a thread

Open a thread when the answer depends on the user, and put the question in an
`lf-ask` in its `--markup`, which keeps it on the user's On me list until they
answer; words in `--text` alone wait on nobody. Anchor it with a quote for a passage,
a section id for a diagram or image, a declared part for one box within a visual, or
nothing for the page as a whole, and name its subject in a few words with `--title`:

```bash
leaf thread open <page> --quote "<passage in the current page>" --title "Afternoon workshop" --text "…" --markup '<lf-ask id="<new-id>">…?</lf-ask>'
leaf thread open <page> --section <element-id> --text "…"
leaf thread open <page> --section <diagram-id> --part node:<source-id> --text "…"
leaf thread open <page> --text "…"
```

Quote exact words the user can see in the active revision, within one widget part.
The command refuses a quote that matches more than one place or crosses a boundary.
In a diagram part, percent-encode the whole source id: `node:Line%20Item` names
`Line Item`. The thread's id is the `id` of its opening comment;
`leaf page state <page> <id>`, `leaf thread reply`, `edit` and `resolve` take the id
of any message in it.

A title is plain text, at most 80 characters. Keep it stable, and rename it with
`leaf thread edit <page> <message-id> --title "<a few words>"` when it no longer
describes the discussion.

## Reply

Pass a delivered answer's whole `ref` to `leaf response reply <answer.ref>`; it needs
no page path or message id, and `leaf page state` shows the same `ref` on the
update's `answer`. A reply on a `ref` delivered before the user's newer correction
does not answer that correction. When an answer has `writer: "turn"`, your turn's
final text answers it (your harness's "Replies"); use `leaf response reply` instead
when the answer needs markup, a question back, a to-do, a title, or a moved anchor.
To have a command hub worker answer, forward it the `answer.ref` as that package's
coordinator instructions say. When a thread is still untitled as you answer, name
it with `--title` on the reply.

Every answer declares what it leaves the thread with, and the answer's head shows
it:

- `--done`: it delivers what the message asked for.
- `--todo "<what you owe>"`: it promises work it does not deliver, and opens that
  to-do on the thread until `leaf task end <page> <reply-id>`
  ([Long-running work](conversation-loop.md#long-running-work)). A promise declared
  `--done` reads as finished work.
- A question back in an `lf-ask` in `--markup`, with no flag. It waits on the user as
  `widget:<its id>` until their next message in the thread answers it or you end it
  ([The On lists](conversation-loop.md#the-on-lists)).

```bash
leaf response reply <answer.ref> --done --title "Afternoon workshop" --text "…"
leaf response reply <answer.ref> --text "One choice first." --markup '<lf-ask id="store-owner">Which store should own it?</lf-ask>'
leaf response reply <answer.ref> --todo "Rebuild the banner quieter" --text "Rebuilding it; it lands in v4."
```

A reply renders as Markdown in a narrow card or panel, so a paragraph that reads fine
in chat is a wall there. Say what changed or where to look in a sentence or two, or
one short item per point, and let the page carry the evidence. Record a decision,
result, or deferred work on the page and link it from the reply with a fragment link
such as `[the decision](#decision)`, which opens any tab or group hiding its target.
Where the reasoning matters to someone using the result, keep the thread anchored to
that section. Pass anything longer than a line with `--file`, or a heredoc on stdin.

`--markup` adds an HTML fragment after the text, such as a native table, a bounded
log, or a small question in `lf-ask` and `lf-options`; an `lf-sample` template gives
the user a live practice page in the thread (`live-samples.md`). A widget there that
waits on the user, such as `lf-options` or `lf-ask`, keeps the thread on their turn
until they answer it. The markup's ids must be new, used in no version of the page
and no earlier message. Leaf checks markup as it checks a page, and refuses document
settings or a stylesheet for the whole page, but it doesn't draw the markup. A data
widget, such as a chart, that fails to draw comes back as an `error` event when the
user opens the thread, and you answer it with a corrected reply.

```bash
leaf response reply <answer.ref> --done --text "The deploy passed." --markup '<details><summary>Deploy log</summary><pre>Ready&#10;Done</pre></details>'
```

To send an image, run `leaf page media <page> <file>` and put the `path` it prints in
your text as a Markdown image.

A successful answer publishes your saved `index.html` with it (the main skill's
"Check the page"). Rerunning an answer with the same `ref` adds nothing. When no
answer is coming, `--failure <code>` posts a failure receipt, which settles the input
without reopening a resolved thread.

To post in a thread that owes no reply, use `leaf thread reply <page> <message-id>`,
which takes the same content and anchor options and `--todo`. While the thread owes
a reply, Leaf refuses it; answer with `leaf response reply <answer.ref>`.

### Progress messages

`--ephemeral` posts one line of progress while work is under way, without answering
(`leaf thread reply --ephemeral` in a thread that owes no reply):

```bash
leaf response reply <answer.ref> --ephemeral --text "Checking the keyboard route."
```

On an update you owe, it starts the update, and its text becomes the **Working**
status in Leaf's panel ([conversation loop, "When to write"](conversation-loop.md#when-to-write)).
The thread shows the latest progress as one dim working message, never counted as
unread, and your answer replaces it. Progress carries only text; questions, to-dos,
markup, anchor moves and failure receipts each need a reply of their own.

### Edit and resolve

Correct a message you or an earlier agent wrote, without adding a turn:

```bash
leaf thread edit <page> <comment-or-reply-id> --text "Corrected wording."
```

The page labels it `edited` and the log keeps every wording. Only the text changes;
markup stays as it was sent.

An ordinary reply leaves the thread open, or reopens it, so the user can inspect the
answer; the user usually resolves it. Resolve it yourself only when the user asks,
when an event's `handling` says to, or when no review or follow-up could change the
outcome, which finishing the work does not show by itself. When unsure, leave it
open. First answer any unanswered user message in it:

```bash
leaf thread resolve <page> <message-id>
```

## Preserve revised anchors

When a revision rewrites a quoted passage, check every open thread on it, including
ones you are not answering this turn. `leaf page check`, and the first successful
reply on a revision, list each open thread whose anchor no longer resolves and where
the revision moves it: to its section if that survives, otherwise detached.

Where you know what replaced the passage, move the thread onto it in the reply that
reports the change, with `--section`, narrowed by `--quote` or, in a diagram,
`--part`:

```bash
leaf response reply <answer.ref> --done --section <element-id> --quote "<new passage>" --text "Updated this and moved the thread to the result."
```

When the subject itself leaves the page, detach the thread rather than moving it onto
nearby content:

```bash
leaf response reply <answer.ref> --done --detach --text "Removed this; the thread no longer has a page target."
```

A detached thread stays open in Threads, its quote marked as gone from this version;
a later reply may move it to a real replacement, and a different subject gets a new
thread. Don't resolve a thread to get rid of an anchor you removed: a resolved
thread keeps its anchor, so if the user reopens it, it points at something the page
no longer shows.

When the user comments on repeated words the surrounding text cannot tell apart,
Leaf keeps the quote but not which copy they meant: the comment has
`anchor.detached: true`, and Threads keeps it with its quote.

## What the user has read

Each thread in `leaf page state <page>` and `leaf page state <page> <thread-id>`
lists under `unread` your messages the user has not read in their current wording. A
message counts as read once its whole body has been on screen, once the user marks
the thread read, or once they act in the thread after it. `leaf thread edit` makes a
message unread again. Unread does not change whose turn it is: an unread message
needs no follow-up, and a read one is not an answer.

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
leaf thread summarize <page> --from <first-message-id> --through <last-message-id> --file summary.md
```

The summary replaces the range in the thread, with the originals available to
unfold, and answers nothing. When summarizing again, read the originals rather than
only the older summary. A recap in an ordinary reply folds nothing. To fold messages
without a summary, pass an empty `--text`, and name the fold with `--label`
(default “Earlier discussion”):

```bash
leaf thread summarize <page> --from <first-message-id> --through <last-message-id> --label 'Previous progress messages' --text ''
```

Editing a message inside a summary with prose cancels that summary, so stale prose
cannot hide the correction; a fold without prose stays.
