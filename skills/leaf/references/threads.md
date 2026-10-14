# Threads

Open a thread when the answer depends on the user. Use a quote for a passage, a
section id for a diagram or image, a declared part for one box within a visual,
and no anchor for the page as a whole:

```bash
leaf thread open <page> --quote "<passage in the current page>" --text "…"
leaf thread open <page> --section <element-id> --text "…"
leaf thread open <page> --section <diagram-id> --part node:<source-id> --text "…"
leaf thread open <page> --text "…"
```

`leaf thread open` anchors in the active revision, as the user sees it. Quote exact
words the user can see, within one widget part. The command refuses a quote that
matches more than one place, or that is retired, replaced, or crosses a boundary,
rather than open a thread with no anchor. The thread's id is its opening comment's
`id`, in the record `leaf thread open` prints. `leaf page state
<page> <id>`, `leaf thread reply`, `edit` and `resolve` all take the id of any
message in the thread.

When the user comments on words that appear more than once, and the surrounding
text cannot tell the occurrences apart, Leaf keeps the quote but not which
occurrence they meant. The comment carries `anchor.detached: true`, its transcript
says **passage not identified**, and the panel's **Not located** filter lists it. A
thread that a revision detached is different: its current anchor is null and
`detached_from` holds the old one ("Preserve revised anchors").

When you open a thread, give it a title with `--title`, a few words that identify
its subject in the thread panel. When the user opens one, Leaf asks a small model
to title it as soon as they post. If the thread is still untitled when you answer,
the delivered message asks you to add `--title` to your reply. A reply's `--title`
applies only to an untitled thread, so a title Leaf set first stays.

```bash
leaf thread open <page> --section <element-id> --title "Afternoon workshop" --text "…"
leaf response reply <answer.ref> --done --title "Afternoon workshop" --text "…"
```

Titles are plain text, at most 80 characters. Keep the title stable; when it no longer describes the
discussion, rename it with `leaf thread edit <page> <message-id> --title "<a few
words>"`, which changes no message and adds no turn.

Use `--markup` for an HTML fragment after the message's text: a native table, a
bounded log, or a small question using `lf-ask` and `lf-options`. Native HTML needs
no widget wrapper. Its ids must be new, used in no version or earlier message.
Leaf checks markup as it checks a page, and refuses document settings or a
stylesheet for the whole page. An `lf-sample`
template in markup gives the user a live practice page in the thread
(`live-samples.md`).

```bash
leaf response reply <answer.ref> --done --text "The deploy passed." --markup '<details><summary>Deploy log</summary><pre>Ready&#10;Done</pre></details>'
```

Leaf checks markup when you post it but does not draw it then. If a data widget,
such as a chart, fails to draw, you get an `error` event when the user opens its
thread; answer with a corrected reply.

The thread panel is a narrow column over the right of the page, so a paragraph that
reads fine in chat is a wall there. A reply says what changed or where to look: a sentence or
two, or one short paragraph or list item per point when there are several. The page
carries the evidence, and a stamp's changelog carries the full list of changes.
When a discussion produces a decision, a result, or deferred work, record the outcome
on the page and link it from the reply that reports it, with a fragment link such as
`[the decision](#decision)`, which opens whatever tab or group hides its target; the
runtime marks a fragment link the current version cannot follow. When the rationale
matters to a user using the result, keep the thread anchored to that page section.
Keep the discussion active if the outcome is not yet incorporated or the user still
owes an explicit review.

A reply renders as Markdown. `--text` is for a one-liner; write anything longer to
a file and redirect it to stdin, where its paragraphs and list items are visible as
you write them.

```bash
leaf response reply <answer.ref> --done --text "…"
leaf response reply <answer.ref> --done < reply.md
```

A user may paste an image into any thread text box, or choose **Capture area** in
the page's More controls to attach a selected part of the page to an anchored
comment. A capture preserves the selected visual state as image evidence; its anchor
names the nearby page content. A delivered message that carries an image says how
to read it. To send one, run `leaf page media <page> <file>` and
write the `path` it prints as an ordinary Markdown image in the message's text. Leaf
refuses a message whose `/media/…` link or image, in text or markup, names a file the
page directory cannot serve, since a broken image posted to the log stays broken.

Every delivered answer carries an exact `ref`, specific to its delivery and page.
Pass the whole value to `leaf response reply <answer.ref>`; it needs no page path or
message id. While the session it was delivered to holds the page, `leaf page state`
shows the same `ref` on the update's `answer`. A reply on a `ref` delivered before
the user's newer correction does not answer that correction. The command refuses
if the page's log was replaced or another session has claimed the page.

The command also takes `--markup`, `--title`, `--quote`, `--section`, `--part`,
`--detach`, and `--ephemeral`, and every answer declares what it leaves the thread
with (below). Save any source edit before replying: the reply checks the saved
`index.html` and makes it the active revision along with the answer. Replying again
with the same `ref` returns the earlier record and adds no message. `--attempt`
names a retry of a progress update. When no answer is coming, `--failure <code>`
posts a failure receipt; it settles the input without reopening a resolved thread.

When an answer has `writer: "turn"`, your turn's own final text answers it, as the
selected harness contract's "Replies" describes. Use this command instead when the
answer needs markup, an ask, a to-do, a title, or a moved anchor. To have a command
hub worker answer, forward it the `answer.ref` as that package's coordinator
instructions direct.

## Preserve revised anchors

When a revision rewrites a quoted passage, take care of every open thread on it,
including threads you are not answering this turn. `leaf page check` lists each
thread whose quote no longer finds one passage. When the revision becomes active,
Leaf moves each of those threads to its section if the section survives, and
detaches it if not. This adds no message and answers nothing. A quote that still
matches one place keeps its exact anchor.

Where you know the passage that replaced the quote, move the thread onto it in the
reply that reports the change. A `--quote` can narrow the anchor within a section,
and in a diagram `--part` names a declared box. A replacement quote can also move a
thread whose old element the edit removed:

```bash
leaf response reply <answer.ref> --done --section <element-id> --quote "<new passage>" --text "Updated this and moved the thread to the result."
leaf response reply <answer.ref> --done --section <element-id> --text "Updated this and moved the thread here."
leaf response reply <answer.ref> --done --section <diagram-id> --part node:<source-id> --text "Updated this node and moved the thread here."
```

When the subject itself leaves the page, detach the thread rather than moving it
onto nearby content that survives. You can do it in the reply that reports the
removal:

```bash
leaf response reply <answer.ref> --done --detach --text "Removed this; the thread no longer has a page target."
```

A detached thread stays open in the panel, with its passage link marked as gone
from this version, and the **Not located** filter lists it. `page state` shows its
current anchor as null, with the old one in `detached_from`. A later reply may move
it to a real replacement; open a new thread for a different subject.

When a revision removes a visual part that an open thread anchors on, such as a
diagram node, move the thread to the part's replacement or detach it in the reply
that reports the change. Do not resolve it instead. A resolved thread keeps its old
anchor, so if the user reopens it, it points at a part the page no longer draws. A
detached thread shows its passage as gone, and a later reply can still move it.

An answer says what it leaves the thread with, one of three:

- `--done`: it delivers what the message asked for.
- `--ask`: its prose asks the user something back. The reply is then an ask
  under `reply:<message-id>` in `page state`'s `asks` collection, until they
  answer in the thread or you end it
  ([The On lists](conversation-loop.md#the-on-lists)).
- `--todo "<what you owe>"`: it promises work it doesn't deliver. The reply opens
  that to-do on its thread under the reply's own id, which stays on you until
  `leaf task end <page> <reply-id>` ([Long-running work](conversation-loop.md#long-running-work)).

```bash
leaf response reply <answer.ref> --ask --text "Which store should own it?"
leaf response reply <answer.ref> --todo "Rebuild the banner quieter" --text "Rebuilding it; it lands in v4."
```

The user sees the declaration on the answer itself: its head reads **Waiting on me** while
its prose ask is theirs to answer, and **To-do open** until you end the to-do. A
promise declared `--done` reads as finished work, so declare what each answer leaves.

To post in a thread that owes no reply, use
`leaf thread reply <page> <message-id>`. It takes the same content and anchor
options, and `--ask` or `--todo` when the message asks or promises. While the
thread owes a reply, Leaf refuses an ordinary `leaf thread reply`; answer with
`leaf response reply <answer.ref>` instead, and post progress on that input the
same way.

### Progress messages

Use `--ephemeral` for interim progress that is useful while work is underway:

```bash
leaf response reply <answer.ref> --ephemeral --text "Checking the keyboard route."
```

This posts progress without answering the update. On an update you owe, it also
starts the update, as `leaf task start` does: its text becomes the **Working** line
in the banner and at the foot of the thread, so keep it to one line. Make the first
one your first command after a delivery
([conversation loop, "When to write"](conversation-loop.md#when-to-write)).
`leaf thread reply --ephemeral` posts progress in a thread that owes no reply.

Until an answer comes, the thread draws progress as one dim working message above its
reply box, never as a reply, and progress never counts as unread; each new progress
message replaces its words. When your next ordinary reply in the thread arrives, it
takes the working message's place and the progress messages before it fold behind a
disclosure beside it, where the user can still expand them. So the user reads
progress as status and only your replies as words addressed to them.

A progress message carries only text, not `--ask`, `--todo`, markup, a failure, or
an anchor move. Put questions and results in ordinary replies.

A widget in a reply's markup whose registry entry declares `x-awaits` is already an
ask, and keeps its thread "My turn" until the user answers it. Leaf refuses `--ask`
on a reply that carries one.

Correct an agent-authored message, including a predecessor's, without adding another turn:

```bash
leaf thread edit <page> <comment-or-reply-id> --text "Corrected wording."
```

The page labels the message `edited`, and the log keeps every earlier wording. Only
the text changes; any markup stays as it was sent.

The user can rewrite their own messages the same way. Their rewrite is a turn rather
than a correction: it arrives as an `edit` event, with the message's new `text` and
the `was` it replaced, and you owe it an answer like any reply.

An ordinary reply leaves the thread open, or reopens a resolved thread, so the user
can inspect the answer or revised page. Reactions, progress messages and failure
receipts do not reopen it. Usually the user resolves it. Resolve it yourself only when the
user asks, when a delivered event's handling says to, as for a reaction or a
version request, or when no review or follow-up can change the outcome.
Completing the requested work does not meet that bar by itself; when uncertain,
leave the thread open. Answer any unanswered user message in the thread before
resolving it:

```bash
leaf thread resolve <page> <message-id>
```

## What the user has read

Each thread in `leaf page state <page>` and `leaf page state <page> <thread-id>` lists under
`unread` your messages the user has not read at their current wording. A message
counts as read once its whole body has been on the user's screen, once they mark its
thread read, or once they do something in the thread after it: reply, react, answer a
widget in it, resolve or reopen it. `leaf thread edit` makes a message unread again. Unread
is not a question and changes nothing about whose turn it is: a message the user has
not read yet needs no follow-up from you, and a read one is not an answer.

## Summarize a long discussion

Keep the current topic easy to find as a thread grows. Summarize earlier discussion
when the topic has moved on or settled detail obscures the current exchange. Do this
as part of answering new input, without waiting for the user to ask. Keep messages
whose individual wording or reasoning still matters to the current exchange directly
readable.

A delivery's `elided.messages` counts messages left out of your context; it folds
nothing in the browser. The thread's `summaries` lists the summaries the user sees.
Only `leaf thread summarize` folds messages for the user; a recap in an ordinary
reply leaves them all displayed.

New input in a long thread may carry `summary_hint`, a suggested range. Use it to
review the earlier discussion, choosing endpoints that fit the topic. Read the
original messages with
`leaf page state <page> <thread-id>` and select a contiguous range whose endpoints are spoken
messages rather than reactions. Summarize its decisions,
reasoning, and remaining questions. Keep the current exchange outside the range
when it is still useful to read directly. A summary helps users navigate the
discussion; incorporate its outcomes into the document too.

```bash
leaf thread summarize <page> --from <first-message-id> --through <last-message-id> < summary.md
```

The summary replaces that range in the presentation, while the original messages
remain available to unfold. It answers no question and resolves no thread.
Use Markdown prose rather than interactive markup. Read the originals before
resummarizing; do not build a new account solely from an older summary.

The disclosure defaults to “Earlier discussion”; set `--label` to name the range.
To fold messages without adding summary prose, pass an explicit empty `--text`:

```bash
leaf thread summarize <page> --from <first-message-id> --through <last-message-id> --label 'Previous progress messages' --text ''
```

As the discussion grows, write another summary. One that overlaps an earlier
summary replaces it, and summaries of separate ranges both stay. Messages outside a
summary's range stay visible. Editing a message inside a summary with prose cancels
that summary, so stale prose cannot hide the correction. A fold without prose stays,
with the edited message inside it.
