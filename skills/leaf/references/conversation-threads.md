# Conversation threads

Read this before opening, replying to, editing, or resolving a thread.

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
cross-boundary text instead of creating a detached comment.

Use `--markup` for a small question: an `lf-ask` containing one heading and
its `lf-options` group. Thread markup is frozen in the log; versions neither
carry nor revise it. Use a page widget instead when the question and its answer
belong in the final record.

The thread panel is a narrow column beside the page. Replies should feel light
and conversational, answer the local thread, and keep the page as the main
surface for evidence, comparisons, and detailed reasoning. Give the reader
enough context to know what changed or where to look without retelling the page.

A reader may paste an image into any thread text box. The composer shows a thumbnail,
while its message carries an ordinary Markdown image at `/media/<digest>.<ext>`. Resolve
that path beneath the absolute page directory named by the delivered batch and inspect
the image itself before replying; alt text is a label, not evidence of what the pixels
show.

`--text` takes inline text; stdin accepts Markdown:

```bash
leaf reply <page> --to <thread-id> --text "…"
leaf reply <page> --to <thread-id> < reply.md
```

When the change that answers a comment also removes or replaces its passage, move
the open thread onto the current result in the same reply. Use the same target forms
as `leaf comment`; for a diagram, prefer its declared stable visual part:

```bash
leaf reply <page> --to <thread-id> --quote "<new passage>" --text "Updated this and moved the thread to the result."
leaf reply <page> --to <thread-id> --section <element-id> --text "Updated this and moved the thread here."
leaf reply <page> --to <thread-id> --section <diagram-id> --part node:<source-id> --text "Updated this node and moved the thread here."
```

The reply records the active revision and validated replacement anchor atomically.
The opening comment keeps its original anchor in `leaf events --thread`, while the
panel, transcript, and `page state` expose the replacement as the thread's current
location. Do this only when the new target is the same subject after the change; open
a new thread for a different subject. Held command-goal threads cannot move, and a
version-response thread cannot take a reply.

Fragment links such as `[the decision](#decision)` take the reader to page
content. `--markup` adds a validated widget after reply text; its ids must be new.
An ordinary reply answers the thread without adding it to the outstanding Ask
list. Add `--awaits` when the reply's prose asks the reader to answer:

```bash
leaf reply <page> --to <thread-id> --awaits --text "Which store should own it?"
```

A widget whose registry entry declares a local `x-awaits` or
`x-request.ask` already joins the page's Ask list and keeps its
thread in "Waiting on you" while that Ask stands. Leaf refuses `--awaits`
beside such markup; the widget's state or request lifecycle is the one reading.

Correct one of this session's sent messages without adding another turn:

```bash
leaf edit <page> --to <comment-or-reply-id> --text "Corrected wording."
```

The page labels the message `edited`. Leaf keeps the original and every revision
in the append-only event log. Only text is revised; any widget markup stays frozen.
`leaf reply --json` prints the event it posted, whose `id` is what `--to` takes
here; so does the refusal, which lists the ids it knows.

An ordinary reply leaves the thread open so the reader can inspect the answer or
revised page. The reader closes it by default. Resolve it yourself only when the
reader asks, when an event rule requires resolution, or when no review or
follow-up can change the outcome. Completing the requested work does not meet
that bar by itself; when uncertain, leave the thread open. Reply before resolving:

```bash
leaf resolve <page> --to <thread-id>
```

An acknowledged reader message still requires a reply: acknowledgement only
removes it from future batches.
