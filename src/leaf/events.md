# Events and threads

Every event carries `id`, `ts`, `author`, `kind`, `seq` (its line number in
`events.jsonl`) and `attention`, which admission stamps ("Authorship and voice").
Document-bound events also carry `revision`, and an agent's event posted from a harness
session carries that session's `agent` and `session`. An `id` is an opaque string
matched whole. The append door mints eight hex characters unique within the page's log,
so an id is not a global identifier. Each kind's record schema is `$events.kinds` in
`../../browser/runtime/kernel-registry.json`; this table says what each kind means:

| Kind                                         | Author          | Door                                                                            | Fields                                                                                                                                                                 | Meaning                                                                                                                                                                                       |
| -------------------------------------------- | --------------- | ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| <a id="kind-comment"></a>`comment`           | user or agent   | `POST /api/event`, `leaf thread create`                                         | `text`, `drawing` or `token`; optional `anchor`, `suggestion`, `about: "design"`, `title`, `markup` (CLI only)                                                         | opens a thread; with `token`, puts a reaction mark on the anchor                                                                                                                              |
| <a id="kind-reply"></a>`reply`               | user or agent   | `POST /api/event`, `leaf thread reply`                                          | `parent`; `text` or `token`; `responds` on an agent's answer; `todo`, `markup` and a replacement or null `anchor` (CLI only)                                           | a message in the thread of `parent`; an agent's answer settles the update `responds` names, without closing the thread; an agent reply may also move or detach the thread                     |
| <a id="kind-edit"></a>`edit`                 | user or agent   | `POST /api/event`, `leaf thread edit`                                           | `message`, `text`; `base` (browser)                                                                                                                                    | replaces the text of a message its own author wrote; the original stays in the log ("Messages")                                                                                               |
| <a id="kind-read"></a>`read`                 | user            | `POST /api/event`                                                               | `messages: [{message, version}]`                                                                                                                                       | records the agent-content versions the user has read; bookkeeping ("Read state")                                                                                                              |
| <a id="kind-seen"></a>`seen`                 | user            | `POST /api/event`                                                               | `revision`                                                                                                                                                             | records the newest live revision a tab showed the user, as they leave; bookkeeping ("Read state")                                                                                             |
| <a id="kind-thread_title"></a>`thread_title` | agent           | `leaf thread edit --title`, or Leaf's own title request (`thread_titles.py`)    | `thread`, `title`                                                                                                                                                      | names a thread; the latest title wins                                                                                                                                                         |
| <a id="kind-reanchor"></a>`reanchor`         | page            | revision activation                                                             | `thread`, `revision`, `anchor: {section} or null`                                                                                                                      | moves an open thread whose passage or visual part no longer resolves to its surviving section, or detaches it, adding no message ("Anchors")                                                  |
| <a id="kind-summary"></a>`summary`           | agent           | `leaf thread summarize`                                                         | `thread`, `from`, `through`, `text`; optional `label`                                                                                                                  | folds a contiguous range of a thread under optional Markdown; the originals stay revealable                                                                                                   |
| <a id="kind-resolve"></a>`resolve`           | user or agent   | `POST /api/event`, `leaf thread resolve`                                        | `parent`                                                                                                                                                               | closes a thread                                                                                                                                                                               |
| <a id="kind-unresolve"></a>`unresolve`       | user            | `POST /api/event`                                                               | `parent`                                                                                                                                                               | reopens a resolved thread                                                                                                                                                                     |
| <a id="kind-action"></a>`action`             | user            | `POST /api/event` from a widget                                                 | `widget`, `action`, `detail`; server-stamped `meaning`                                                                                                                 | changes the document through the widget ("Admission")                                                                                                                                         |
| <a id="kind-report"></a>`report`             | agent or worker | `leaf page report`                                                              | `widget`, `action`, `detail`; server-stamped `meaning` (as for `action`, under an `x-state` verb declaring `writer: "agent"`)                                          | provisional widget state, in force until a stamped version settles it                                                                                                                         |
| <a id="kind-pickup"></a>`pickup`             | page            | the delivery transport, or a harness's failure receipt                          | `events`, `phase` (`queued`, `opened` or `failed`), `session`, `turn`; `failure` (when `failed`); `refs`, the `answer.ref` its delivery gave each input owed an answer | the named inputs reached the Codex queue, entered an exact agent turn, or were given up with no answer coming; idempotent per event, phase, session and turn; never a `start` (`delivery.py`) |
| <a id="kind-receipt"></a>`receipt`           | page            | delivery receipt (`delivery.receive_batch`)                                     | `through`, the seq the receipt confirms                                                                                                                                | the complete delivery of the log through `through` reached its durable consumer; the greatest `through` is the acknowledgement cursor                                                         |
| <a id="kind-note"></a>`note`                 | agent           | `leaf page stamp`                                                               | `version`, `revision`, changelog `text`, `restated`, `settles` (the `report` ids it answers and the `todo` ids its `--completes` ends)                                 | maps a public version to an immutable revision, naming the decisions it takes back                                                                                                            |
| <a id="kind-error"></a>`error`               | page            | the runtime                                                                     | `text`                                                                                                                                                                 | a failure the page reported in front of the user; the agent hears it as a report                                                                                                              |
| <a id="kind-todo"></a>`todo`                 | agent           | `leaf task create`, or a reply's `todo` (`leaf thread reply --todo`)            | `owner` (`agent`, or `user` with `--on user`); `subject` (a widget, another element, or the page); `title`; server-stamped `revision` on a widget to-do                | opens work the agent owes, or a to-do on the user (`todos.py`)                                                                                                                                |
| <a id="kind-todo_end"></a>`todo_end`         | agent or user   | `leaf task end`, or a to-do's Done (`POST /api/event`)                          | `todo`, an open to-do's id or a question's obligation id; `outcome` (`done`, `failed` or `dropped`); optional `detail`                                                 | ends a to-do, or retires a question asked in words without answering it (`todos.py`)                                                                                                          |
| <a id="kind-start"></a>`start`               | agent           | `leaf task start`, or progress posted to an owed update                         | `item`, an owed update's event id or an open to-do's; `text`, the status line; `turn`                                                                                  | takes the item in hand until it ends or a `status` follows; the newest start on an item replaces the one before (`todos.py`)                                                                  |
| <a id="kind-status"></a>`status`             | agent           | `leaf page open` and `leaf page close`, or the website harness at a turn's edge | `state` (`waiting` or `idle`)                                                                                                                                          | declares the page open for feedback or closed, and puts down every earlier start (`activity.declaration`, `todos.item_starts`)                                                                |
| <a id="kind-plan"></a>`plan`                 | agent           | `leaf task plan`                                                                | `steps`, an outline of `{depth, title, state}` or `{depth, item}`                                                                                                      | replaces the agent's plan, which arranges to-dos and obligations without owning them (`plans.py`)                                                                                             |
| <a id="kind-undo"></a>`undo`                 | user            | `POST /api/event`                                                               | `undoes`                                                                                                                                                               | withdraws one gesture of the user's own ("Undo")                                                                                                                                              |

## Anchors

An `anchor` names a passage by `section` and `quote`, with `prefix` and `suffix` where
the neighbouring text tells two identical passages apart. The browser writes it from
the user's selection. `leaf thread create`, and a reply command that moves a thread,
write it from a quote read out of the authored HTML through `leaf.passages`, so they
write only anchors the file confirms (`validation.md`, "Passages").

Projected data has no authored text to quote, so a selection on it names `datum`, the
rendering key within its section, and, where the projection names an external `x-data`
input, `source` and `source_revision`, the value's revision when selected. The door
checks that the section binds that source, and admits an older revision as a comment on
a value since replaced. `identity` names a subject the emitter knows persists across
source replacements. `visual` names a declared part of a picture, and `part` the control
or region a design comment landed on. `part` is an accessible name, not an element
identity: an authored id or a quote the file confirms locates the comment exactly, and
otherwise its section is only a description. A native editing value never becomes a
`part` or a file-readable quote. A selection whose context can't tell which of several
identical passages was meant carries `detached: true`, keeping its words without
claiming a location.

When a revision drops an open thread's passage or visual part, activation records a
`reanchor` for it (`validation.source_history.revision_reanchors`). An automatic
move never invents a passage: it falls back to the surviving section or detaches. A
reply can choose a new passage. `events.build_threads` reads the latest reply
transition or `reanchor` as the thread's location and keeps the old anchor as
`rewritten_from` or `detached_from`; the opening message keeps its quote.

A `drawing` is up to 32 freehand strokes on a comment, and may be its only content. The
browser anchors it on the element its first stroke starts on or nearest, and records
with it `box`, the frame's size, `says`, the page's words under the ink, and the
`viewport` and `scheme` of the window it was drawn in. `drawing.frame`, when present,
names the native visual under that point by a structural path inside its element, so
inserting or removing a sibling detaches it rather than retargeting it. Points are in
the frame's local coordinates (`browser/runtime/composing/drawing-record.js`). The
browser reads all of this off the rendered page, which no file reading can reproduce, so
the door bounds its shape, the stroke count and 500 characters of `says`, refuses a
drawing without an anchor or `box`, and does not re-read it. `$events.handling.comment`
tells the agent how to read a drawing, and `leaf page picture` redraws one as the user
saw it (`render_gate/picture.py`).

A note, a reply that publishes the saved source, or the first automatic `reanchor` may
carry `publication`, the exact immutable bundle name (`r<revision>-<digest>`). Only the
checked source publisher supplies it; `revisioning.py`'s header says how a publication
and the anchor moves that depend on it land together.

## Undo

The user may withdraw a resolve, unresolve, action, or Done on a to-do (the
kinds `$events.kinds` marks `undoable`), and a reaction while nothing has answered it
and its thread is unresolved. Spoken messages cannot be withdrawn. An undo cannot
itself be undone. The door refuses an `undoes` naming anything but an unwithdrawn
gesture of the user's own (`events.UndoReading`).

`undo` names its gesture and nothing else. It withdraws rather than deletes: the event
stays in the log and every fold skips it, so the page shows what the revision says
plus what is still in force, as a reload would and as `restated` does from the
author's side. A widget's `render()` paints a withdrawal like any other change,
keeping the widget and its independent children.

The page's undo key takes back the user's newest gesture or nothing: a newer gesture it
cannot take back, such as a sent reply, ends the walk, while bookkeeping and gestures
already withdrawn do not. It says what it would take back and how long ago, in every tab
and after a reload, so a gesture made weeks ago is not taken back unseen. Where the
gesture's thread or element is out of view, or the agent has picked the gesture up, the
first press opens that place and only the next press, with nothing pressed between,
withdraws it; showing writes nothing. Either way the press leaves the user at that place:
a gesture whose own landing has just carried the user off it, such as resolving a
thread, is taken in one press that returns them to its thread, while they have not
acted elsewhere since (`runtime/undo.js`). The served undo list marks `picked_up` each entry
a delivery handed into an agent's turn (`delivery.opened_input_ids`).
`runtime/undo.js` names each gesture, and the served list words an action at its head
(`GestureWords.gesture`). An exact control, such as a widget's Undo, may withdraw an
older gesture it names, and may withdraw an action whose POST has not returned: the
browser keeps both gestures in its ordered ledger and sends the undo once the action's
id is accepted. Refusing the action drops its undo, and refusing the undo restores the
action.

## Authorship and voice

The server stamps every browser-posted event `author: "user"`, or `"page"` for an
`error`. The agent's commands stamp `author: "agent"`, and admission
(`event_contracts.append_admitted`) gives an agent's event that names no voice the
posting session's: `agent`, its display name, and `session`, its harness session id. Several sessions can
write to one page, so the voice is read from the poster's environment rather than the
claim, and the session id is the identity, since a display name is anyone's to
choose. A writer speaking for another session names that voice itself, as the page
server does when it titles a thread for its claimant. A command run outside a harness
session writes neither field. Every reading
names an agent's event through `schema.agent_name`, and the browser shows that name as
served.

Admission stamps `attention` when the event changes obligations or
to-dos on the user, pending answers, work the agent has in hand and its inputs, or
widget input whose active `x-state` verb declares `attention: true` (`$state`).
`workflows.attention_reading` compares those readings before and
after the gesture, and the decision survives later replies, versions and to-do endings,
so a cancellation delivered to the agent stays input after the work it withdrew ends.
Reports and errors always carry attention, and agent messages never do. A user's edit
carries it as a reply does; read marks, and closing or reopening an answered thread that
holds no obligation, do not. `leaf wait`, delivery, pickup, the Stop guard and the idle
gate read the field through `service.requires_agent_attention`, and the pending count
counts only the user's events.

Either side can open or close a thread. A thread has served its purpose once the user
has read it, and only the user knows when that is, so the user ordinarily closes one;
the panel and the transcript say when the agent did.

## Admission

`event_contracts.append_admitted` admits every writer's event under the page
transaction's lease. A retry whose `attempt` was accepted gets that record back
without repeating the gesture, and an `attempt` the log holds for a different command
is refused (HTTP 409). Otherwise admission reads the vocabulary the event's revision
captured, so `page init` cannot reinterpret a document the user acted on; checks the
command against its kind's record schema before any gate reads its fields; allocates
the id; runs the kind's gates against the page and the current log; derives `meaning`
and `attention`; and validates the finished record against its stored schema.

A refusal (`EventRefused`) carries one finding (`findings.py`): a command error, or a
final HTTP 400 whose body carries `findings` beside the `error` the browser shows. A
fault raises instead, since the append may or may not have happened;
`http.PageEndpoint._answer` answers it with a 500 without `final`, and the browser
retries the same attempt.

Transports own only their input boundary: which kinds and fields they accept.
`thread.post_reply` matches its own `attempt` before the door by kind and response
address, so a CLI retry with reworded text returns the first reply. Attempt identity
compares every field but those the server assigns (`event_log._attempt_payload`).
`$events.ownership` names the `derived` fields only admission supplies and the
`browser_discard` fields browser ingress drops; it is fixed by the running kernel, and
no layer changes it.

`meaning` holds what a reader without the sending registry cannot recover from the
event. Every `action` and `report` records:

- `scope`, `page` or `thread`. Together with the event's revision, `scope` names the
  document the widget was in (`events.event_document`): the revision for a page event,
  the frozen markup that sent it for a thread event.
- `unit`, the fold unit. Leaf keys each widget event by `[widget, unit, action]`: the
  widget, the unit of its state the event changes, and the verb. Every action at a key
  competes, so a later action of the same verb on the same unit supersedes an earlier
  answer while another verb leaves it in force, and keys are independent. Thread folds
  keep reading a key after its widget retires.
- `depends`, the identities the event rests on: the owner, the unit, and the values of
  attribute-set and position fields. A detail string never becomes a dependency by
  matching an HTML id. The log stores no ancestry; retraction reads the current
  document's containment of these identities (`event_meaning.py`).
- `state`, the operation and detail domain the gesture was admitted under, so under a
  later layer whose domain excludes the value, the event stays in history only
  (`layer-registry.md`).
- `answer`, on an action whose admission makes its widget's `x-awaits.answered` hold:
  the thread the answer closes, from the widget's authored `resolves` in the sending
  document, or null. An outcome equal to the widget's `x-withdrawn-as` declines and
  closes nothing.
- `creates`, the tag of the child a `creates` verb adds. The child is the action's
  unit, so it lasts as long as the action does, whether or not a document holds it.
- `among`, on a position move ("Position moves").

Recorded effects own their payload schema (`registry.contract.detail_schema`), and
every payload is a closed object. Both writers share the applicability gates: selected
ids belong to the recording widget, and a position names an owned unit, an admissible
destination and a valid rank (`registry.contract.RANK`) in the named revision. Reports
name page widgets; user actions may also name widgets in frozen thread markup.

### Position moves

A position record places its unit by a rank key rather than an index, so undoing or
superseding one unit's move never moves another. The key lies among the container's
authored units on the move's revision, which admission records in order as
`meaning.among`.

A revision that authors the container differently absorbs the move
(`projection.move_absorbed`), and `page check` holds that revision and every later one
to it: the unit stays in the move's container, after the nearest unit both revisions
list before it, unless the revision marks it `restated`. An absorbed move still stands,
as a written-back pick does, but the markup now decides the order an undo would have
restored, so it can no longer be undone. The door refuses a move made on an older
revision whose container the newest one authors differently, and any move of a unit
that shows another widget's answer (`x-shows`): that widget's own action places it,
and is the one record of the answer whichever view sent it (`shown_answers.py`).

## Following the log

`leaf page events PAGE --follow [--after SEQ]` is the log's change feed. It prints each
stored record after `SEQ` (default 0) as one JSON line, `meaning` included, then each
event the door admits as it lands. A reader skips a field or kind it does not
recognise rather than refusing the record. `seq` is the resume cursor: a reader that
restarts with `--after` the last seq it printed misses nothing and repeats nothing.
SIGINT, SIGTERM and a closed stdout end the feed with exit 0. A log that is removed,
replaced or shorter than what was read ends it with exit 1 and `<log> is gone`, since
its seqs no longer name that log's lines. The feed wakes on the page's native file
subscription, so it sees an event any process appends.

The feed carries the log only. Values under `data/` are replaced in place with no
sequence, so a reader that needs them reads `leaf page state` or the publication files.

## Threads

A thread is keyed by the id of the comment that opened it (`events.build_threads`).
What each thread command does for the user, and when an agent uses it, is
`../../skills/leaf/references/threads.md`.

### Read state

Reading is separate from whose turn it is, and answers nothing. Each agent content
version, a message's own id and then each `edit` id, is unread until a `read` event
names it or the user acts in the thread after it; `read_state.py` owns which acts
count. The result is each thread's `unread`, in browser state and `page state`. A
`seen` event does the same for the page: it names the newest live revision a tab showed
the user while they were there (visible and focused), posted as they leave it, and the
newest one named is the served state's `seen`, the revision the browser marks the
page's changes since. A hosted copy serves no `seen`, since its reader is not the page's
user. Read records hold across tabs
and revisions and never enter agent delivery. A page has one user for its lifetime, so
a `read` or `seen` names no account.

### Turns

An agent comment opens a thread, and a substantive reply opens or resumes one. Either
waits on the user only through an obligation: the message's own, declared with
`--obligation` (id `message:<message>`, its text the prompt), or one a widget in its
markup declares through `x-awaits`.
An answering command declares what it leaves: `--done`, nothing further; `--todo
<title>`, a to-do on the thread for work the reply promises but does not deliver
(`todos.todo_reading`); or a message obligation or a question in its markup. The
browser cannot write `todo` or `obligation`.
A user reply always hands the thread back to the agent.

An agent reply records the delivery event it answers as `responds`, including an
answer whose update was settled during the turn; a proactive `leaf thread reply`
carries none. Settlement consumes this exact id rather than log order, so answering
older work cannot erase newer user input. A substantive reply reopens a resolved
thread and restores its unanswered widget and message obligations, as an `unresolve`
does;
reactions and failure receipts leave it closed.

A harness that gives up on an update writes the failure its answer takes
(`thread.fail_answer`): a reply for a message, or a failed `pickup` for an answer owed
to a page obligation, each carrying `failure`, a harness-owned code. Only the harness
writes `failure`, and the panel draws such a reply as a receipt that answers nothing.

A widget with a local `x-awaits` obligation in a reply's markup declares that obligation
itself. Frozen in the reply, it stays open until `x-awaits.answered` holds. Actions on
it before then are not handed
over: they carry no receipt and need no reply. The action that answers carries the
receipt and hands the turn to the agent, and undoing it returns the obligation to the
user and removes the reply obligation. An action on a frozen widget that answers no
obligation, such as a card moved on a board sent in a reply, keeps a delivery receipt
and owes no reply, as a page action does (`workflows.py`).

While a thread is open, the user's message after a state-answered obligation in it hands
that obligation to the agent, still open, until the agent answers that turn or ends the
to-do a reply promised (`obligations.thread_obligation_readings`). A thread anchored on
a page obligation does the same, so an obligation the user has commented on leaves their
On me list while the reply owed to the comment stands on the agent's, and a promised
to-do keeps that obligation the agent's even after the thread is resolved
(`obligations.anchors_with_agent`). A question asked in words (`obligation: true`)
is answered by that message instead, along with every open question before it, or by a reaction whose token
declares `settles` on the message holding it. Neither answer resolves the thread, and
the agent's `todo_end` can retire a question unanswered (`obligations.settle_by_words`).
The agent's `todo_end` also retires a frozen widget's question the user answered in
words, since no revision can write that widget's state; the delivery of the user's
reply lists such questions up its thread in `waiting` (`obligations.waiting_in_thread`).
A message asks by its words or by a widget in its markup, not both: only words answer
`obligation: true`, so beside a widget it would outlast the user's pick, and
`thread create` and `thread reply` refuse the pair.

`work_reading.WorkReading.all_obligations` is the one inventory of obligations: page
widgets', frozen widgets', message requests and user-owned tasks, with a record beside
them for each update the user handed over (`workflows.handed_over`), read after the
widget obligations it depends on. `obligations.py` owns a record's statuses
and its next actor. `$keys["x-awaits"]` in `browser/registry.json` says when a widget's
obligation exists and what its id is, and `Obligation` in
`served_state/state.schema.json` lists the served fields. `obligations.collection`
selects `all`, `user` and `unanswered` from it. To-dos are separate records, and no
to-do is made from an obligation.

### Messages

- `edit` revises only the `text` of a comment or reply its own writer wrote: the
  user's, or an agent's, including a predecessor session's. Markup is frozen, since a
  user action may rest on a widget in it, and a reaction or a bare drawing has no text
  to revise. Readings show the latest text on the original message, labelled edited,
  and the message's `edited` names that edit and the text it replaced (`was`). Text the
  message already says is refused. A browser's edit names its `base`, the id of the
  message or of its latest edit, and lands only while that is still the latest, so a
  tab cannot silently replace words another tab has since rewritten.
- An agent's `edit` corrects its words and hands nothing over. A user's `edit` is a
  turn of its own (`events.build_threads`, `revisions`): it reopens a resolved thread
  and is owed an answer, which names the edit as `responds` and the rewritten message
  as its parent. Only whose turn it is reads revisions, and every other reading reads
  the messages (`events.exchange`).
- A comment or reply's `title` names its thread atomically with the message, and
  leaves an existing name in place. `thread_title` names or renames a thread with a
  single line of plain text of at most 80 characters. An unnamed thread has a null
  title.
- `summary` covers an inclusive `from`–`through` range of at least two spoken turns in
  one thread; a reaction may lie inside it but not at an endpoint. `text` may be empty
  and `label` defaults to “Earlier discussion”. `events.active_summaries` says which
  summaries stand. A summary answers, resolves, settles and marks read nothing.
- An agent `reply` with `ephemeral: true` is progress. It carries no `responds`,
  `todo`, markup, failure or anchor transition and takes part in no turn, settlement or
  reopening. Posted to an update the agent owes, it carries `start: {item, turn?}`, so
  progress history and work in hand are one fact (`todos.start_reading`). The next
  ordinary agent reply in its thread completes it (`events.progress_completions`), and
  the browser and transcript then hide it.
- An agent `reply` may move its thread with an `anchor` captured against its revision,
  or detach it with a null anchor, in the same append as the message explaining it. A
  thread whose opening comment `holds` a command goal cannot move or detach.
- A body is Markdown, stored as typed and rendered by the serving Leaf's runtime, so
  the renderer and the panel's styles version together; raw HTML shows as text. A
  widget rides the `markup` field, which only `leaf thread create` and the reply commands
  accept, validated against the page's registry. The door refuses a Markdown link or
  image, in text or markup, to a `/media/…` path the page directory cannot answer.
- A raster image pasted into a browser text box is stored first as page media, and the
  draft holds an ordinary Markdown image at `/media/<digest>.<ext>`; no draft or event
  has an attachment field. An abandoned draft may leave unreferenced media, which Leaf
  keeps, since deleting it safely would mean proving no immutable revision or event
  refers to it.
