# Events and threads

`events.jsonl` records every transition a page makes after its authored markup. This
file owns what each event kind means, how the append door admits an event, and how
threads fold from the log. Each kind's record schema, including what a browser may
send, is `$events.kinds` in `../../assets/registry.json`.

Every event carries `id`, `ts`, `author`, `kind`, and `seq`, its 1-based line number
in the log. The door mints `id` as eight hex characters, unique within the page and
nowhere else, so whatever keys on an event outside the page pairs the id with the
page. The user's events arrive through `POST /api/event`; the agent's through the
command named below.

| Kind | Writer | Meaning |
| --- | --- | --- |
| `comment` | user; agent, `leaf thread open` | opens a thread on its `anchor`, or on the page; with `token` in place of `text`, a reaction |
| `reply` | user; agent, `leaf thread reply` | answers the message `parent` names; with `token`, a reaction on it |
| `edit` | agent, `leaf thread edit` | replaces a message's text; the original stays in the log |
| `thread_title` | agent, `--title` on `leaf thread open`, `reply` or `edit` | names a thread; the latest wins |
| `summary` | agent, `leaf thread summarize` | shows Markdown in place of a range of a thread's messages |
| `read` | user | records the agent-content versions the user has read; bookkeeping |
| `resolve` | user; agent, `leaf thread resolve` | closes a thread |
| `unresolve` | user | reopens a thread |
| `done` | user, from the banner of a page declaring `<meta name="lf-review" content="sign-off">` | approves the stamped `version` |
| `action` | user, from a widget | changes the document through the widget |
| `report` | agent or worker, `leaf page report` | provisional widget state, under an `x-state` verb declaring `writer: "agent"` |
| `note` | agent, `leaf page stamp` | maps `version` to an immutable `revision`; `restated` names the decisions it takes back, `settles` the reports and work it answers |
| `pickup` | page, from the delivery carrier or a host's failure receipt | the named user events reached the Codex queue (`queued`), entered an agent turn (`opened`), or will get no answer (`failed`); never a work claim |
| `error` | page, from the browser runtime | a failure shown to the user; the agent hears it as a report |
| `undo` | user | withdraws the gesture `undoes` names (see "Undo") |

An event *stands* until the log withdraws it: an action until an `undo` names it or a
version note's `restated` names an element it rests on, a report until a note
`settles` it, any other gesture until an `undo` names it. This sense of *stands* is
unrelated to the glossary's **Standing** (where the user is on the page),
`dispatch.js`'s `standing` scope test, and the `standing` server lifetime.

## Anchors

An `anchor` names a passage by `section` and `quote`, with `prefix` and `suffix` where
the quote alone repeats. The browser writes it from the user's selection. The CLI
writes it from a quote read out of the authored HTML through `leaf.passages`, so it
writes only anchors the file confirms (`validation.md` owns file-side passages).

Projected data has no authored text to quote, so a selection on it names `datum`,
the rendering key within its section, and, where the section's `x-data` input is an
external source, `source` and `source_revision`, the value's revision when selected.
The door checks that the section binds that source and admits an older revision as a
comment on a replaced value. `identity` names a subject the emitter knows persists
across source replacements. `visual` names a declared part of a picture, and `part`
the control a design comment landed on.

A `drawing` is freehand strokes on a comment, and may be its only content. The
browser records with it `box` and `says`, read off the rendered page where no file
reading can reproduce them, so the door bounds their shape and does not re-read them.
`$events.handling.comment` tells the agent how to read them.

## Undo

The user may withdraw a resolve, unresolve, action, or approval
(`schema.UNDOABLE_KINDS`), and a reaction while nothing has answered it and its
thread is unresolved. A spoken message, an undo, and a move the newest revision
has absorbed ("Position moves") cannot be withdrawn. The door refuses an `undoes`
naming anything but an unwithdrawn gesture of the user's own (`events.UndoReading`).

`undo` names its gesture and nothing else. It withdraws rather than deletes: the event
stays in the log and every fold skips it, so the page shows what a reload would.
`renderState` paints a withdrawal like any other change, keeping the widget and its
independent children.

`served_state.document.browser_undo_candidates` is the one undo list. The undo key
takes back the user's newest gesture or nothing: a newer gesture it cannot take back,
such as a sent reply, ends the walk, while bookkeeping and withdrawn gestures are
skipped. A control naming one gesture, such as a widget's Undo, may withdraw an older
one. It may also withdraw an action whose POST has not returned: the browser keeps
both gestures in its ordered ledger and sends the undo once the action's id is
accepted. Refusing the action drops the undo; refusing the undo shows the action
standing again.

## Authorship and voice

The server stamps a browser-posted event `author: "user"`, or `"page"` for `error`.
The agent commands stamp `author: "agent"` and the posting session's voice, `agent`
(its display name) and `session` (its host session id), read from the poster's
environment (`host.message_identity`), since several sessions can write to one page.
The session id is the identity; a display name is anyone's to choose. Outside a host
session neither field is written. `schema.agent_name` names an agent's event
wherever it is shown, `Agent` where it has no voice, and the browser shows the served
name with no fallback of its own.

`service.requires_agent_attention` decides what the agent hears: a user event of a
kind not declared bookkeeping, and every `report` and `error`. The banner counts only
the user's.

Either side can open or close a thread. The user ordinarily closes one, since only
they know they have read it; the panel and transcript say when the agent did.

## Admission

`event_contracts.append_admitted` is the one door for every writer's event, under the
page transaction's lease. A retry whose `attempt` was accepted gets that event back.
Otherwise admission reads the vocabulary captured with the event's revision, so a
re-vendor cannot reinterpret a document the user acted on; checks that the kind is
declared; runs the kind's gates against the page and the standing log; derives
`meaning`; and validates the finished record against the kind's `record` schema.

A refusal is a command error, or a final HTTP 400. A fault raises instead, since the
append may or may not have happened; `http.PageEndpoint._answer` answers it with a
500 without `final`, and the browser retries the same attempt. Transports own only
their input boundary: which kinds and fields they accept, and how they answer a
retry.

`meaning` holds what a reader without the sending registry could not recover from
the event. Callers cannot send it, and retry identity ignores it. Every `action` and
`report` records:

- `scope`, `page` or `thread`, which with the revision names the document the widget
  was in (`events.event_document`): the revision for a page event, the frozen markup
  that sent it for a thread event.
- `unit`, the fold unit. Widget events are keyed by `[widget, unit, action]`: the
  widget, the part of its state the event changes, and the verb. The latest standing
  event at a key decides that state, and only a later action at the same key
  supersedes an answer. Thread folds keep reading a key after its widget retires.
- `depends`, the identities the event rests on: the owner, the unit, and the values
  of an attribute-set or position record field. A detail string never becomes a
  dependency by matching an HTML id. The log stores no ancestry; retraction reads the
  current document's containment of these identities.
- `answer`, on an action whose admission makes its widget's `x-awaits.answered` hold:
  the thread the answer closes, from the widget's authored `resolves` in the sending
  document, or null. An outcome equal to the widget's `x-withdrawn-as` declines and
  closes nothing.
- `creates`, the tag of the child a `creates` verb adds. The child is the action's
  unit, so it lasts as long as the action stands, whether or not a document holds it.
- `among`, on a position move.

### Position moves

A position record places its unit by a rank rather than an index, so undoing or
superseding one move never moves another unit. The rank lies among the container's
authored units on the move's revision, which admission records, in order, as
`meaning.among`.

A revision that authors the container differently absorbs the move
(`projection.move_absorbed`). `page check` holds that revision and every later one to
the move: the unit stays in the move's container, after the nearest unit both
revisions list before it, unless the revision marks it `restated`. An absorbed move
still stands, but the markup now decides its order, so it cannot be undone. The door
refuses a move made on an older revision whose container the newest one authors
differently.

## Following the log

`leaf page events PAGE --follow [--after SEQ]` prints each stored record after `SEQ`
(default 0) as one JSON line, then each event the door admits as it lands. A reader
skips a field or kind it does not recognise. `seq` is the resume cursor: restarting
with `--after` the last seq printed misses and repeats nothing. SIGINT, SIGTERM, and a
closed stdout end the feed with exit 0. A log that is removed, replaced, or shorter
than what was read ends it with exit 1 and `<log> is gone`, since its seqs no longer
name that log's lines.

The feed carries the log only. Values under `data/` are replaced in place with no
sequence, so a reader that needs them reads `leaf page state` or the value files.

## Threads

A thread is keyed by the id of the message that opened it (`events.build_threads`).
What each thread command does for the user, and when an agent uses it, is
`../../references/threads.md`.

### Read state

Reading is separate from whose turn it is: it answers nothing. `read_state.py` owns
the rule. Each agent content version, a message's own id and then each `edit` id, is
unread until a `read` event names it or the user moves in its thread after it; the
browser posts `read` once the body has been shown. The result is each thread's
`unread`, in browser state and `page state`. Read records hold across tabs and
revisions and never enter agent delivery. A page has one user for its lifetime, so a
`read` names no account.

### Turns

An agent comment asks the user. An agent reply asks when it records `awaits: true`
(`leaf thread reply --awaits`, which the browser cannot write) or carries a widget with
a local `x-awaits` Ask (below). A user reply always hands the thread to the agent.

An agent reply records the delivery event it answers as `responds`, including one
whose move was settled during the turn; a reply sent without `--for` carries none.
Settlement consumes this exact id rather than log order, so answering older work
cannot erase newer user input.

A spoken reply reopens a resolved thread and restores its unanswered widget Asks, as
an `unresolve` does; reactions and failure receipts leave it closed.

A host that gives up on a move writes the failure its answer takes
(`thread.fail_answer`): a reply carrying `failure`, a host-owned code, for a message;
a failed `pickup` for an answer to a page Ask. Only the host writes `failure`, and the
panel draws such a reply as a receipt that answers nothing.

A widget with a local `x-awaits` Ask declares its Ask itself, so the CLI refuses
`--awaits` on a reply carrying one. Frozen in the reply, it keeps the user's Ask open
until `x-awaits.answered` holds. Moves before then are not handed over: they carry no
receipt and need no reply. The move that answers carries the receipt and hands the
turn to the agent, and undoing it returns the Ask to the user. A move on a frozen
widget that answers no Ask, such as a card moved on a board, gets a delivery receipt
and owes no reply, as a page move does (`workflows.py`).

An open structural Ask anywhere in an unresolved thread keeps it awaiting the user,
whatever follows. Without one, the latest spoken turn decides, and a user reaction on
the agent's latest request whose token declares `settles` clears it without resolving
the thread. `served_state/thread.py` owns this precedence.

### Messages

- `edit` revises only the `text` of a message the posting session wrote. Markup is
  frozen, because a user action may rest on a widget in it. Readings show the latest
  text on the original message, labelled edited.
- A thread with no `thread_title` has a null `title`, and the panel falls back to a
  label of its own (`../../assets/runtime/thread/thread-card.js`).
- `summary` covers an inclusive `from`–`through` range of at least two spoken turns in
  one thread; a reaction may lie inside it but not at an endpoint. A later overlapping
  summary replaces an earlier one, disjoint ones coexist, and editing a covered
  message invalidates its summary. A summary answers, resolves, settles, and marks
  read nothing.
- An agent `reply` may move its thread with an `anchor` captured against the reply's
  revision, or detach it with a null anchor, in the same append as the message
  explaining it. The latest value is the thread's location, `detached_from` keeps
  the prior one while detached, and the opening message's anchor never changes. A
  thread whose opening comment `holds` a command goal cannot move or detach.
- A body is Markdown, stored as typed and rendered by the page's vendored runtime,
  so the renderer and the panel's styles version together; raw HTML shows as text.
  A widget rides the `markup` field, which only `leaf thread open` and
  `leaf thread reply` accept, validated against the vendored registry. Both refuse a
  Markdown link or image to a `/media/…` path the page directory cannot answer.
- An image in a message or draft is a Markdown image at `/media/<digest>.<ext>`; no
  event or draft has an attachment field. The composer stores a pasted image as page
  media and shows its Markdown as a removable thumbnail.
