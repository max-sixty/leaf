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

Use `--markup` for a small question: an `lf-decision` containing one heading and
its `lf-options` group. Thread markup is frozen in the log; versions neither
carry nor revise it. Use a page widget instead when the question and its answer
belong in the final record.

Answer in as few words as the question takes; one sentence is a complete reply.
An answer the size of a page section goes into the page instead, and the reply
is a line pointing at it. The panel is a narrow column, so an answer past a few
sentences goes in as separate Markdown paragraphs or a list with one point each.
`--text` takes a one-line answer; longer text comes in on stdin:

```bash
leaf reply <page> --to <thread-id> --text "Yes, and the page already has it."

leaf reply <page> --to <thread-id> <<'EOF'
Three things put the retry on the client:

- only the client can tell a dropped connection from a slow one
- the client already holds the request body
- retrying on the server would double the write
EOF
```

Fragment links such as `[the decision](#decision)` take the reader to page
content. `--markup` adds a validated widget after reply text; its ids must be new.
An ordinary reply leaves the thread open for follow-up without counting it as an
outstanding decision. Add `--awaits` when the reply's prose asks the reader to answer:

```bash
leaf reply <page> --to <thread-id> --awaits --text "Which store should own it?"
```

A widget whose registry entry declares a local `x-awaits` or
`x-request.decision` decision already joins the page's decision list and keeps its
thread in "Waiting on you" while that decision stands. Leaf refuses `--awaits`
beside such markup; the widget's state or request lifecycle is the one reading.

Correct one of this session's sent messages without adding another turn:

```bash
leaf edit <page> --to <comment-or-reply-id> --text "Corrected wording."
```

The page labels the message `edited`. Leaf keeps the original and every revision
in the append-only event log. Only text is revised; any widget markup stays frozen.

The reader closes a thread by default. Resolve it yourself only when they ask or
when the subject has left the page or the work has plainly answered it. Reply
before resolving:

```bash
leaf resolve <page> --to <thread-id>
```

An acknowledged reader message still requires a reply: acknowledgement only
removes it from future batches.
