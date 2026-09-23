# Conversation threads

Open a thread when the answer depends on the reader. Use a quote for a passage, a
section id for a diagram or image, a declared part for one box within a visual,
and no anchor for the page as a whole:

```bash
leaf comment <page> --quote "<passage in the current page>" --text "…"
leaf comment <page> --section <element-id> --text "…"
leaf comment <page> --section <diagram-id> --part node:<source-id> --text "…"
leaf comment <page> --text "…"
```

`leaf comment` anchors in the active revision and reads it as the user sees it,
including edits and retired content. Quote exact visible authored words inside
one widget part. The command refuses ambiguous, retired, replaced, or
cross-boundary text instead of creating a detached comment. It prints the id of
the thread it opened, which `leaf status --on`, `leaf edit --to`, and
`leaf resolve --to` take.

Give a conversation a short, descriptive title when you open it or first handle
the reader's thread. Choose a few words that identify its subject in the thread
panel. Keep the title stable; rename it only when it no longer describes the
discussion.

```bash
leaf conversation title <page> <conversation-id> --text "Afternoon workshop"
```

The conversation id is its opening comment's id, which `leaf comment` prints; a
delivery carries each conversation's current title, null until named. Titles are plain text, at most
80 characters. The same command sets or replaces the title without changing
messages or adding a conversational turn.

Use `--markup` for a small question: an `lf-ask` containing one heading and
its `lf-options` group. Thread markup is frozen in the log and has no revision
boundary: every immutable historical document shows the same markup. It must
therefore validate against every pinned revision's captured registry, not only
the active registry. Use only widget vocabulary shared by those registries. If
no shared widget fits, ask in prose with `--text` (and `--awaits` on a reply), or
use a page widget when the question and its answer belong in the final record.

The thread panel is a narrow column beside the page, so a paragraph that reads fine
in chat is a wall there. A reply says what changed or where to look: a sentence or
two, or one short paragraph or list item per point when there are several. The page
carries the evidence, and a stamp's changelog carries the full list of changes.
When a discussion produces a decision or defers work, revise the page first, then
link the outcome from the reply with a fragment link such as
`[the decision](#decision)`. When the rationale matters to a reader using the
result, keep the thread anchored to that page section. Keep the discussion active
if the outcome is not yet incorporated or the reader still owes an explicit review.

A browser comment may carry a drawing of one or more strokes that continue across the
page. A drawing whose first stroke began over or in the margin beside an addressable
element anchors there; one begun where no addressable element shares its line belongs to
the page whole. Treat it as visual evidence for that ordinary thread. Its `says` is the
page's words the drawing stood over when it was drawn, from the first word inside the
ink's extents to the last. That is the neighbourhood of the mark rather than the mark:
an arrow across a paragraph says the paragraph. It is absent where the extents hold no
words, as over a picture or in a margin. An anchored
drawing's `strokes` are offsets from that element's top-left corner, and `box` is the
element's width and height at the time, so a stroke's share of the box says which part
of a picture it marks; a page drawing has no `box`, and its strokes are offsets from the
document's origin. Use any accompanying text, and reply or revise through the same path
as any other comment.

A reader may paste an image into any thread text box; the message carries it as an
ordinary Markdown image at `/media/<digest>.<ext>`. Resolve
that path beneath the absolute page directory named by the delivered batch and inspect
the image itself before replying; alt text is a label, not evidence of what the pixels
show.

Send one the same way: run `leaf page media <page> <file>` and write the printed path as
an ordinary Markdown image in the message's text. The door refuses a `/media/…` the page
directory cannot answer, in text as in markup, because the log is append-only and a
broken image posted to it stays broken. It reads the link and image destinations the
runtime resolves, so a path written about in a sentence stays prose.

Both routes render as Markdown. `--text` is for a one-liner; write anything longer to
a file and redirect it to stdin, where its paragraphs and list items are visible as
you write them.

```bash
leaf reply <page> --text "…"
leaf reply <page> < reply.md
```

With one reply obligation in the current turn's opened delivery, Leaf infers its event
and address. When that delivery contains several, select one with `--for <event-id>`;
Leaf derives its response address and rechecks both against current state, so a response
captured before a newer reader correction cannot settle the correction. `leaf
conversation read` exposes the same response on the workflow that its current
`activity.obligations` names, when the delivery is no longer the freshest reading.
`activity.obligations` is a list of ids into `workflows`, where each move's stage and
subject are canonical and `answer` names the current writer operation.
Provisional response progress remains separately available as `response`. When the source changed, the reply
validates and activates it before posting, so an edit and its answer cross one command
boundary.

When the change leaves the same subject at a new passage, move the open thread onto
that result in the same reply. If the edit also removes the old target, name the
replacement's section; a quote can narrow that section, and a diagram should use its
declared stable visual part. A bare quote cannot license removing its old target in the
same edit, so move the thread with it first:

```bash
leaf reply <page> --section <element-id> --quote "<new passage>" --text "Updated this and moved the thread to the result."
leaf reply <page> --section <element-id> --text "Updated this and moved the thread here."
leaf reply <page> --section <diagram-id> --part node:<source-id> --text "Updated this node and moved the thread here."
```

When the subject itself leaves the page, detach the thread instead of moving it onto
nearby surviving content:

```bash
leaf reply <page> --detach --text "Removed this; the conversation no longer has a page target."
```

The reply records the active revision and its anchor transition atomically. The opening
comment keeps its original anchor in `leaf events --conversation`. The panel keeps a
detached thread open under **No longer in this version**, and `page state` reports its
null current anchor and the prior anchor as `detached_from`. A later reply may move it
to a genuine replacement. Open a new thread for a different subject. Held command-goal
threads cannot move or detach.

A thread the reader opened as a request for change, delivered as a `version`
obligation, takes no reply from you: the next stamped version is its answer. Where the
change needs clarification first, open a separate thread on the same Ask with
`leaf comment <page> --section <ask-id>`; the reader's answer hands both threads back
to you. The original stays open until authored state in a later stamped version
answers the Ask it came from, or changes the declared answer where the Ask was already
answered, and `leaf resolve` accepts it only then.

A declared visual part is held only while a live conversation's current anchor names
it, so a version may drop the part once every thread on it has moved, detached, or
been resolved, and `version check` names those three moves while one still holds it.
Move or detach rather than resolving a thread whose part you are about to remove: the
reader can reopen a resolved thread, and it comes back pointing at a coordinate no
revision declares any more, while a detached thread reads as **No longer in this
version** and a later reply may still move it to a replacement.

A fragment link takes the reader to page content, opening whatever tab or group hides
it, and the runtime marks one the current version cannot follow. `--markup` adds a
validated widget after reply text; its ids must be new.
An ordinary reply answers the thread without adding it to the outstanding Ask
list. Add `--awaits` when the reply's prose asks the reader to answer:

```bash
leaf reply <page> --awaits --text "Which store should own it?"
```

To add an agent-initiated turn to a conversation that currently owes no reply, name the
thread with `--to <message-id>` and use `--initiates` instead of `--for`. Leaf refuses
it while any event in that conversation has a standing reply obligation.

A widget whose registry entry declares a local `x-awaits` or
`x-request.ask` already joins the page's Ask list and keeps its thread "On you"
while that Ask stands. Leaf refuses `--awaits` beside such markup; the widget's
state or request lifecycle is the one reading.

Correct one of this session's sent messages without adding another turn:

```bash
leaf edit <page> --to <comment-or-reply-id> --text "Corrected wording."
```

The page labels the message `edited`. Leaf keeps the original and every revision
in the append-only event log. Only text is revised; any widget markup stays frozen.
`leaf comment`, `leaf reply`, `leaf edit` and `leaf resolve` each print one
sentence naming what they wrote; `leaf comment` adds the command that titles the
new thread. `--json` prints the posted event instead, whose
`id` is what `--to` takes here. A refusal lists the ids it knows.

An ordinary reply leaves the thread open, or reopens a resolved thread, so the reader
can inspect the answer or revised page. Reactions and failure receipts do not reopen it. The reader closes it by default. Resolve it yourself only when the
reader asks, when an event rule requires resolution, or when no review or
follow-up can change the outcome. Completing the requested work does not meet
that bar by itself; when uncertain, leave the thread open. Reply before resolving:

```bash
leaf resolve <page> --to <thread-id>
```

## What the reader has read

Each conversation in `leaf page state <page>` and `leaf conversation read` lists under
`unread` your messages the reader has not read at their current wording. A message
counts as read once its whole body has been on the reader's screen, once they mark its
thread read, or once they do something in the thread after it: reply, react, answer a
widget in it, resolve or reopen it. `leaf edit` makes a message unread again. Unread
is not a question and changes nothing about whose turn it is: a message the reader has
not read yet needs no follow-up from you, and a read one is not an answer.

## Summarize a long discussion

When delivered context suggests summarization, read the original messages with
`leaf conversation read` and select a contiguous range whose endpoints are spoken
messages rather than reactions. Summarize its decisions,
reasoning, and remaining questions. Keep the current exchange outside the range
when it is still useful to read directly. A summary helps readers navigate the
discussion; incorporate its outcomes into the document too.

```bash
leaf conversation summarize <page> <conversation-id> --from <first-message-id> --through <last-message-id> < summary.md
```

The summary replaces that range in the presentation, while the original messages
remain available to unfold. It answers no question and resolves no thread.
Use Markdown prose rather than interactive markup. Read the originals before
resummarizing; do not build a new account solely from an older summary.

As the discussion grows, write another summary with the desired endpoints.
An overlapping summary replaces the earlier summary; disjoint ranges can retain
separate summaries. New messages outside the endpoints remain visible. Editing a
covered message invalidates its summary so stale prose cannot hide the correction.
