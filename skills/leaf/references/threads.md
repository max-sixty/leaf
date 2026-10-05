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
<page> <id>`, `leaf thread reply`, `edit` and `resolve`, and `leaf task open` all
take the id of any message in the thread.

Title a thread with `--title` on the command that first handles it: the `open` that
starts it, or, for an untitled thread the user opened, the reply that answers it,
which a delivered message in it asks for. Choose a few words that identify its
subject in the thread panel. A reply's `--title` names only a thread that is still
untitled: Leaf may have named it from its opening words while you worked, and that
name stands.

```bash
leaf thread open <page> --section <element-id> --title "Afternoon workshop" --text "…"
leaf thread reply <page> --title "Afternoon workshop" --text "…"
```

A delivery carries each thread's current title, null until named. Titles are plain
text, at most 80 characters. Keep the title stable; when it no longer describes the
discussion, rename it with `leaf thread edit <page> <message-id> --title "<a few
words>"`, which changes no message and adds no turn.

Use `--markup` for a small question: an `lf-ask` containing one heading and its
`lf-options` group; it follows the reply's text, and its ids must not appear in any
version or earlier message. Thread markup is frozen in the log and has no revision
boundary: every immutable historical document shows the same markup. It must therefore
validate against every pinned revision's captured registry, not only the active
registry. Use only widget vocabulary shared by those registries. If no shared widget
fits, ask in prose with `--text` (and `--awaits` on a reply), or use a page widget
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
leaf thread reply <page> --text "…"
leaf thread reply <page> < reply.md
```

A user may paste an image into any thread text box, and a delivered message that
carries one says how to read it. To send one, run `leaf page media <page> <file>` and
write the `path` it prints as an ordinary Markdown image in the message's text. The door
refuses a `/media/…` link or image the page directory cannot answer, in text as in
markup, because the log is append-only and a broken image posted to it stays broken;
a path mentioned in a sentence stays prose.

With one reply obligation in the current turn's opened delivery, Leaf infers its event
and address. When that delivery contains several, select one with `--for <event-id>`;
Leaf derives its response address and rechecks both against current state, so a
response captured before a newer user correction cannot settle the correction. When
the delivery is no longer the freshest reading, `leaf page state <page> <thread-id>` shows what
each move in the thread still owes as its workflow's `answer`. When the source
changed, the reply validates and activates it before posting, so an edit and its
answer cross one command boundary.

## Preserve revised anchors

When a revision rewrites a quoted passage, preserve every affected open thread,
including threads you are not answering this turn. `leaf page check` lists each
quote that no longer identifies one passage. Activation moves those threads to
their own surviving sections automatically, recording an anchor transition without
adding a message or answering an outstanding move. A surviving unique quote keeps
its precise attachment; repeated words require unique stored context.

Prefer the passage that replaced the quote when you know it: move the thread onto
that result in the reply reporting the change. A quote can narrow its section,
and a diagram should use its declared stable visual part. A bare replacement quote
can also move a thread whose old element the edit removes:

```bash
leaf thread reply <page> --section <element-id> --quote "<new passage>" --text "Updated this and moved the thread to the result."
leaf thread reply <page> --section <element-id> --text "Updated this and moved the thread here."
leaf thread reply <page> --section <diagram-id> --part node:<source-id> --text "Updated this node and moved the thread here."
```

When the subject itself leaves the page, detach the thread instead of moving it onto
nearby surviving content. A thread with no surviving section needs an explicit move
or detachment before that revision can activate; the check names the thread and the
reply that corrects it:

```bash
leaf thread reply <page> --detach --text "Removed this; the thread no longer has a page target."
```

The reply records the active revision and its anchor transition atomically. The opening
comment keeps its original anchor in the event log. The panel keeps a
detached thread open, its passage link marked as gone from this version, and the
**No longer here** filter lists it. `page state` reports its
null current anchor and the prior anchor as `detached_from`. A later reply may move it
to a genuine replacement. Open a new thread for a different subject.

A declared visual part is held only while a live thread's current anchor names
it, so a version may drop the part once every thread on it has moved, detached, or
been resolved, and `page check` names those three moves while one still holds it.
Move or detach rather than resolving a thread whose part you are about to remove: the
user can reopen a resolved thread, and it comes back pointing at a coordinate no
revision declares any more, while a detached thread reads as **No longer in this
version** and a later reply may still move it to a replacement.

An ordinary reply answers the thread without adding it to the outstanding Ask
list. Add `--awaits` when the reply's prose asks the user to answer:

```bash
leaf thread reply <page> --awaits --text "Which store should own it?"
```

To add an agent-initiated turn to a thread that currently owes no reply, name the
thread instead of `--for`: `leaf thread reply <page> <message-id>`. Leaf refuses
an ordinary reply this way while any event in that thread has a standing reply
obligation. Progress updates below can name the thread while its answer is due.

### Progress updates

Use `--ephemeral` for an interim update that is useful while work is underway:

```bash
leaf thread reply <page> --for <event-id> --ephemeral --text "Checking the keyboard route."
```

This posts progress without answering the input or ending its start. You can
also name the thread to post progress there. The updates stay visible until the
next non-ephemeral agent reply in that thread, then fold under “Previous updates”
without summary prose. The original messages remain available to expand and edit.
Intervening user messages remain visible; separate runs of updates fold separately.
One update can fold on its own. An explicit summary can cover those updates instead.

An ephemeral update is progress text, so it cannot carry `--awaits`, widget markup,
failure or an anchor move. Put questions and results in ordinary replies. The shared
disclosure appears in the panel and contextual thread surfaces. A completing reply
held behind a new-reply notice keeps its progress visible until the reply is shown;
originals already being read or focused stay expanded.

A widget whose registry entry declares a local `x-awaits` already joins the
page's Ask list and keeps its thread "On you" while that Ask stands. Leaf refuses
`--awaits` beside such markup; the widget's state is the one reading.

Correct one of this session's sent messages without adding another turn:

```bash
leaf thread edit <page> <comment-or-reply-id> --text "Corrected wording."
```

The page labels the message `edited`. Leaf keeps the original and every revision
in the append-only event log. Only text is revised; any widget markup stays frozen.
Every `leaf thread` write prints the records it appended, one JSON line each, as
`leaf page events` prints them; a `--title` that names the thread adds a
`thread_title` record after the message. A refusal lists the ids it knows.

An ordinary reply leaves the thread open, or reopens a resolved thread, so the user
can inspect the answer or revised page. Reactions, ephemeral updates and failure receipts do not reopen it. The user closes it by default. Resolve it yourself only when the
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

New input in a long thread may carry a suggested range to summarize. Choose whether
and when a summary would help the user navigate the discussion; the suggestion adds
no response obligation. Read the original messages with
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
leaf thread summarize <page> --from <first-message-id> --through <last-message-id> --label 'Previous updates' --text ''
```

As the discussion grows, write another summary with the desired endpoints.
An overlapping summary replaces the earlier summary; disjoint ranges can retain
separate summaries. New messages outside the endpoints remain visible. Editing a
covered message invalidates a summary containing prose so stale prose cannot hide
the correction. A fold without prose keeps the revised originals available.
