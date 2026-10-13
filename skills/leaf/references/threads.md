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

`leaf thread open` anchors in the active revision and reads it as the user sees it,
including edits and retired content. Quote exact visible authored words inside
one widget part. The command refuses ambiguous, retired, replaced, or
cross-boundary text instead of creating a detached comment. The thread's id is its
opening comment's `id`, in the record `leaf thread open` prints. `leaf page state
<page> <id>`, `leaf thread reply`, `edit` and `resolve` all take the id of any
message in the thread.

A user's comment on repeated words whose surrounding text cannot tell the
occurrences apart keeps its quote but not which occurrence it meant. It carries `anchor.detached: true`, its transcript
says **passage not identified**, and the panel's **Not located** filter lists it. A
thread a revision detached instead has a null current anchor and its prior anchor in
`detached_from` ("Preserve revised anchors").

Title a thread with `--title` on the command that first handles it: the `open` that
starts it, or, for an untitled thread the user opened, the reply that answers it,
which a delivered message in it asks for. Choose a few words that identify its
subject in the thread panel. A reply's `--title` names only a thread that is still
untitled: Leaf may have named it from its opening words while you worked, and that
name stands.

```bash
leaf thread open <page> --section <element-id> --title "Afternoon workshop" --text "…"
leaf response reply <answer.ref> --done --title "Afternoon workshop" --text "…"
```

A delivery carries each thread's current title, null until named. Titles are plain
text, at most 80 characters. Keep the title stable; when it no longer describes the
discussion, rename it with `leaf thread edit <page> <message-id> --title "<a few
words>"`, which changes no message and adds no turn.

Use `--markup` for an HTML fragment after the message's text: a native table, a
bounded log, or a small question using `lf-ask` and `lf-options`. Native HTML needs
no widget wrapper. Its ids must not appear in any version or earlier message.
Markup passes the shared structure, vocabulary, media, and id checks; it cannot
declare document settings or add a stylesheet for the whole page. An `lf-sample`
template in markup gives the user a live practice page in the thread
(`page-authoring.md`, "Live samples").

```bash
leaf response reply <answer.ref> --done --text "The deploy passed." --markup '<details><summary>Deploy log</summary><pre>Ready&#10;Done</pre></details>'
```

Thread markup is frozen in the log and shows in every version of the page, so it
must validate against the registry each pinned revision captured, not only the active
one. Use only widget vocabulary those registries share. If no shared widget
fits, ask in prose with `--text` and `--ask`, or use a page widget
when the question and its answer belong in the final record. Markup is checked as it
is posted but not drawn, so a data widget, such as a chart, whose body does not draw
reaches you as an `error` event when the user opens its thread; answer with a corrected
reply.

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

Every delivered answer carries an exact `ref`, qualified by the delivery and its
page batch. Copy that complete value into `leaf response reply <answer.ref>`;
no page path or message id is needed. While the session it was delivered to holds
the page, the update's `answer` in `leaf page state` carries the same `ref`. A reply on a reference delivered before the
user's newer correction does not answer that correction. The command refuses when
the page's log was replaced or another session has claimed the page.

The same command supports `--markup`, `--title`, `--quote`, `--section`, `--part`,
`--detach`, and `--ephemeral`, and an answer declares what it leaves (below). Save a
source edit before replying: the reply validates the saved `index.html` and makes it
live along with the answer. Repeating an ordinary reply's reference returns its
previous record without appending another message. Use `--attempt` to name retries of
a progress update. `--failure <code>` posts a failure receipt when no answer is
coming; it settles the input without reopening a closed thread.

A delivery whose answer has `writer: "turn"` is answered by your turn's own text,
as the selected harness contract's "Replies" describes; this command still answers it
explicitly when the answer needs markup, an ask, a promised to-do, a title or a moved
anchor. To have a command hub worker answer, forward it the `answer.ref` as that
package's coordinator instructions direct.

## Preserve revised anchors

When a revision rewrites a quoted passage, preserve every affected open thread,
including threads you are not answering this turn. `leaf page check` lists each
quote that no longer identifies one passage. Activation moves those threads to
their own surviving sections automatically, recording an anchor transition without
adding a message or answering an outstanding update. A surviving unique quote keeps
its precise attachment; repeated words require unique stored context.

Prefer the passage that replaced the quote when you know it: move the thread onto
that result in the reply reporting the change. A quote can narrow its section,
and a diagram should use its declared stable visual part. A bare replacement quote
can also move a thread whose old element the edit removes:

```bash
leaf response reply <answer.ref> --done --section <element-id> --quote "<new passage>" --text "Updated this and moved the thread to the result."
leaf response reply <answer.ref> --done --section <element-id> --text "Updated this and moved the thread here."
leaf response reply <answer.ref> --done --section <diagram-id> --part node:<source-id> --text "Updated this node and moved the thread here."
```

When the subject itself leaves the page, detach the thread instead of moving it onto
nearby surviving content. Activation automatically detaches a thread with no
surviving section. You can also detach it explicitly in the reply that reports
the removal:

```bash
leaf response reply <answer.ref> --done --detach --text "Removed this; the thread no longer has a page target."
```

The reply records the active revision and its anchor transition atomically. The opening
comment keeps its original anchor in the event log. The panel keeps a
detached thread open, its passage link marked as gone from this version, and the
**Not located** filter lists it. `page state` reports its
null current anchor and the prior anchor as `detached_from`. A later reply may move it
to a genuine replacement. Open a new thread for a different subject.

A declared visual part is held only while a live thread's current anchor names
it, so a version may drop the part once every thread on it has moved, detached, or
been resolved, and `page check` names those three moves while one still holds it.
Move or detach rather than resolving a thread whose part you are about to remove: the
user can reopen a resolved thread, and it comes back pointing at a coordinate no
revision declares any more, while a detached thread reads as **No longer in this
version** and a later reply may still move it to a replacement.

An answer says what it leaves the thread with, one of three:

- `--done`: it delivers what the message asked for, and nothing stays on either queue.
- `--ask`: its prose asks the user something back. The reply is then an ask
  under `reply:<message-id>` in `page state`'s `asks` collection, until they
  answer in the thread or you end it
  ([Questions and Tasks](conversation-loop.md#questions-and-tasks)).
- `--todo "<what you owe>"`: it promises work it doesn't deliver. The reply opens
  that to-do on its thread under the reply's own id, which stays on you until
  `leaf task end <page> <reply-id>` ([Long-running work](conversation-loop.md#long-running-work)).

```bash
leaf response reply <answer.ref> --ask --text "Which store should own it?"
leaf response reply <answer.ref> --todo "Rebuild the banner quieter" --text "Rebuilding it; it lands in v4."
```

The user sees the declaration on the answer itself: its head reads **Asks you** while
its prose ask is theirs to answer, and **To-do open** until you end the to-do. A
promise declared `--done` reads as finished work, so declare what each answer leaves.

To add an agent-initiated turn to a thread that currently owes no reply, use
`leaf thread reply <page> <message-id>`. This proactive command takes the same
content and anchor options, and `--ask` or `--todo` where the turn asks or
promises. Leaf refuses an ordinary proactive reply while the
thread owes a response; copy that response's delivery reference instead.
Use the captured response reference for progress on an owed input too.

### Progress messages

Use `--ephemeral` for interim progress that is useful while work is underway:

```bash
leaf response reply <answer.ref> --ephemeral --text "Checking the keyboard route."
```

This posts progress without answering the update. Progress on an update you owe also
takes that update in hand, as `leaf task start` does, with the progress text as its
**Working** line in the banner and at the foot of the thread, so it is one line.
[Conversation loop](conversation-loop.md#when-to-write), "When to write", makes
the first one your first command after a delivery. A proactive progress message
names a thread with no response due.

Until an answer comes, the thread draws progress as that one progress line above its
reply box, never as a reply, and progress never counts as unread; each new progress
message replaces the line, and the line's disclosure shows the steps. When your next
ordinary reply in the thread arrives, it takes the line's place and the progress
messages before it fold behind a disclosure beside it, where the user can still
expand them. So the user reads progress as status and only your replies as words
addressed to them.

A progress message is progress text, so it cannot carry `--ask`, `--todo`,
markup, failure or an anchor move. Put questions and results in ordinary replies.

A widget whose registry entry declares `x-awaits` already poses an ask
and keeps its thread "My turn" while that ask awaits the user. Leaf refuses
`--ask` beside such markup; the widget's state is the one reading.

Correct an agent-authored message, including a predecessor's, without adding another turn:

```bash
leaf thread edit <page> <comment-or-reply-id> --text "Corrected wording."
```

The page labels the message `edited`. Leaf keeps the original and every revision
in the append-only event log. Only text is revised; any HTML markup stays frozen.
A committed reply or `leaf thread` write prints the records it appended, one JSON
line each, as `leaf page events` prints them. A refusal lists the ids it knows.

The user can rewrite their own messages the same way. Their rewrite is a turn rather
than a correction: it arrives as an `edit` event, with the message's new `text` and
the `was` it replaced, and you owe it an answer like any reply.

An ordinary reply leaves the thread open, or reopens a resolved thread, so the user
can inspect the answer or revised page. Reactions, progress messages and failure receipts do not reopen it. The user closes it by default. Resolve it yourself only when the
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

A delivery's `elided.messages` counts originals omitted from the agent's context;
it does not fold anything in the browser. The thread's `summaries` lists its
presentation summaries. Changing that presentation requires the summarize command
below; an ordinary reply containing a recap leaves the originals displayed.

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

As the discussion grows, write another summary with the desired endpoints.
An overlapping summary replaces the earlier summary; disjoint ranges can retain
separate summaries. New messages outside the endpoints remain visible. Editing a
covered message invalidates a summary containing prose so stale prose cannot hide
the correction. A fold without prose keeps the revised originals available.
