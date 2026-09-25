# Events and conversation

Every event carries `id`, `ts`, `author`, `kind`, and `seq` (its line number in
`events.jsonl`). Document-bound events also carry `revision`; page-owned `read`
does not. An `id` is
an opaque string matched whole. The append door mints eight hex characters,
re-rolling any candidate this log already holds, so an id is unique within its
page and is not a global identifier. The kinds:

| Kind | Author | Door | Fields | Meaning |
| --- | --- | --- | --- | --- |
| `comment` | user or agent | `POST /api/event`, `leaf comment` | `text`, `drawing`, or `token`; optional `anchor`, `suggestion`, `about: "design"`, `response`, `markup` (CLI only) | opens a question, or with `token` puts a reaction mark on the anchor |
| `reply` | user or agent | `POST /api/event`, `leaf reply` | `parent`; `text` or `token`; agent `responds` or `initiates`; `awaits`, `markup`, and a replacement `anchor` or null detachment (CLI only) | answers the exact named obligation without closing its conversation; an agent reply may also replace or remove the conversation's current location |
| `edit` | agent | `leaf edit` | `message`, `text` | replaces one message's visible text; the original stays in the log |
| `read` | user | `POST /api/event` | `messages: [{message, version}]` | records that this page's one user has read exact current or historical agent-content versions; `$events` declares it bookkeeping, so it adds no conversation turn or agent work |
| `conversation_title` | agent | `leaf conversation title` | `conversation`, `title` | names a conversation in the panel; latest title wins without adding a turn or settling work |
| `summary` | agent | `leaf conversation summarize` | `conversation`, `from`, `through`, `text` | replaces one contiguous range with Markdown in the thread panel; originals stay in the log and remain revealable |
| `resolve` | user or agent | `POST /api/event`, `leaf resolve` | `parent` | closes a thread |
| `unresolve` | user | `POST /api/event` | `parent` | the user reopens a resolved thread |
| `done` | user | the banner, only on a page declaring `<meta name="lf-review" content="sign-off">` | `version`, the stamp approved | approval of the declared sign-off; a page that asks nothing gets no terminal control |
| `action` | user | `POST /api/event` from a widget | `widget`, `action`, `detail`; server-stamped `meaning` | the user edited the document through the widget |
| `report` | agent or worker | `leaf experimental report` | as `action`, validated by an `x-state` verb declaring `writer: "agent"` | provisional state that stands until a stamped revision answers it |
| `request` | user | `POST /api/event` from a widget | `widget`, `action`, `detail`, and `source_revision` for a projected record; validated by the holder's `x-request` | a durable, non-undoable one-shot instruction to the host, seated on its admitted document, widget, and unit |
| `receipt` | agent | `leaf experimental receipt`; a host failure receipt | `request`, `succeeded` or `failed`, `text`; host `failure` with `failed` | exactly one terminal outcome per accepted request |
| `pickup` | page | the delivery carrier; a host failure receipt | `events`, `phase` (`queued`, `opened`, or `failed`), `session`, `turn`; `failure` with `failed` | the named user events reached the durable Codex queue or entered an exact agent turn, or the host gave up on them with no answer coming; idempotent per event, phase, session, and turn; never a work claim |
| `note` | agent | `leaf version stamp` | `version`, `revision`, changelog `text`, `restated`, `settles` | one public version mapped to an immutable revision, naming the decisions it took back and the reports or work it answered |
| `error` | page | the runtime | | the page reported a failure in front of the user; heard like a report, never counted against the user |
| `undo` | user | `POST /api/event` | `undoes` | withdraws one gesture of the user's own (`UNDOABLE_KINDS`: resolve, unresolve, action, done) |

An `anchor` names a passage by `section` and `quote`, with `prefix` and `suffix`
where neighbouring text tells two identical passages apart; a selection on
projected data names `datum` (the stable key local to its section) and, when the
projection names an external input, `source` and `source_revision`; `visual` names
a declared part of a picture and `part` the control a design comment landed on.

A `drawing` is up to 32 freehand strokes (`strokes`, each a list of points) attached to
an ordinary comment, and may be that comment's only content. Its first stroke decides
whether it anchors on an element or on the page, and with it the browser records `box`
and `says`; the drawing's clause in `$events.handling.comment` tells the agent how
to read the three. The
browser reads them off the rendered page, which holds words and geometry no file
reading can produce, so the door bounds their shape, the stroke count and 500
characters of `says`, and does not re-read them. Leaf derives the drawing's frame and
owns ink, weight, SVG construction, and replay. A drawing is immutable once sent,
follows the thread's resolution state.

## Undo

The user may withdraw a resolve, unresolve, action, or approval. A reaction
may also be withdrawn while unanswered and on an unresolved thread. Spoken
messages cannot be withdrawn; requests cannot be withdrawn because their external
effects may precede the receipt. An undo cannot itself be undone.

`undo` names the gesture and nothing else; every other field is the target's to
state. It withdraws rather than deletes: nothing leaves the log, and the folds and
the thread reading drop the event, so the page is what the revision says plus
what still stands, the same reading a reload has always made and the one
`restated` writes from the author's side. `renderState` paints withdrawals and
forward changes alike, retaining the widget and its independent children. The
door refuses an `undoes` naming anything but an unwithdrawn gesture of the
user's own. An exact control may withdraw a forward action before that action's
POST finishes: the browser derives the withdrawal immediately, keeps both gestures
in its ordered ledger, and replaces the local dependency with the accepted action id
before sending the undo. Refusal of the action discards its dependent undo; refusal
of the undo re-derives the still-standing action.

## Authorship and voice

The server stamps every browser-posted event `author=user`. `leaf comment`,
`leaf reply`, `leaf edit`, `leaf experimental report`, `leaf experimental receipt`,
and `version stamp` stamp `author=agent` plus the posting session's own voice: `agent`, its display
name, and `session`, its host session id. Several agent sessions can write to one
page, so the voice is read from the poster's environment rather than from the
watcher's claim record, and identity is the session id, because a display name is
anyone's to choose.

Everything downstream turns on `author`: `leaf wait` prints user events and the
banner counts only input that requires agent attention, so a `read` neither wakes
the watcher nor reads as unanswered. An agent's own comment does neither. Either
side can open a thread and either side can close one.
A note's purpose is discharged by being read, and only the user knows that
happened, so the user ordinarily closes a thread; `leaf resolve` is the agent's
door onto closing, and a thread the agent closed is named as such in the panel
and the transcript.

## Admission

`event_contracts.append_admitted` admits every writer's event under the page
transaction's lease. It returns an accepted retry without repeating the gesture;
otherwise it reads the named revision's vocabulary, checks that the kind is
declared, runs its gates against the page and standing log, derives server-owned
meaning, and validates the finished record against its stored-record contract.
Using the event's revision keeps re-vendoring from reinterpreting an open document.
A refusal returns a command error or a final HTTP 400. A fault raises instead, since
it may land either side of the append; the HTTP transport's one fault boundary
(`http.PageEndpoint._answer`) records it and answers HTTP 500 without `final`, so
the browser retries the same attempt.

Transports own only their input boundary: which kinds and fields they accept,
how they answer retries, and whether their anchors need file-side capture.

Browser POSTs are commands. The append transaction stamps the accepted event with
server-owned `meaning`; callers cannot send it, and retry identity
compares the original command fields rather than this enrichment. Meaning holds
only what a reader without the sending registry cannot recover from the event
itself. Every widget event records `scope`, `page` or `thread`, and its document
identity is read from that scope and the event's revision (`events.event_document`):
a page event's document is the revision the event names, and a thread event's is
the frozen markup that sent its widget. It also records `unit`, the fold unit or request
seat, so an action or report stands on the `[widget, unit, action]` coordinate.
Actions and reports add `depends`, the direct element identities named by the
owner, the unit, and declared state fields. An action whose admission
makes its widget's `x-awaits.answered` condition hold is that Ask's answer and
additionally records `answer`: the widget's authored `resolves`, read from the
sending document, names the thread the answer closes, and null answers without
closing one; a decision whose outcome is the widget's `x-withdrawn-as` declines and
closes none. Historical conversation folds use this coordinate even after its
widget retires. Every action at the coordinate competes: a later action of the
same verb on the same unit supersedes its prior answer, while another verb leaves
it standing. Coordinates are independent, so a position record places its unit by a
rank key rather than an index: the key means the same place whichever other units'
moves stand, and undoing or superseding one unit's move never moves another. The key
lies among the container's authored units on the revision the move was made on,
which admission records in order as `meaning.among`. The key places the unit while
a revision authors that container the same way; a revision that authors it
differently absorbs the move (`projection.move_absorbed`), and `version check`
holds its markup, and every later revision's, to the move's container and to the
nearest unit both revisions list before it unless the unit is `restated`. The
absorbed move still stands, as a written-back pick does, and it can no longer be
undone: the markup decides the order an undo would have restored. The door refuses
a move made on an older revision whose container the newest one authors
differently.

Dependency identities come from the fold unit and the attribute-set and position
record fields. Literal detail strings do not become dependencies by matching HTML ids. The log does not freeze ancestry:
retraction tests use the current document's containment of those identities.
A child a `creates` verb adds is that action's fold unit, so it stands on the action's
own coordinate until the action is undone or retracted. Admission stamps the child tag
in `meaning.creates`, and the action rests on its unit whether or not a document holds
it yet.

## Following the log

`leaf events PAGE --follow [--after SEQ]` is the log's change feed. It prints each
stored record after `SEQ` (default 0) as one JSON line, server-stamped `meaning`
included, then keeps printing each event the append door admits, flushed as it
lands. A reader drops a field or kind it does not recognise rather than refusing the
record. `seq` is the resume cursor: a reader that restarts with `--after` the last
seq it printed misses nothing and repeats nothing. SIGINT, SIGTERM, and a closed
stdout end it with exit 0. A log that is removed, replaced by another file, or
shorter than what the feed has read ends it with exit 1 and `<log> is gone` on
stderr, since its positions no longer name that log's lines. The feed wakes on the
log's file stamp at the browser news stream's `LOOK_S` cadence, so an event any
process appends reaches it the same way.

The feed carries the log only. External data under `data/` is replaced in place
with no sequence to resume from, so a reader that needs it reads `leaf page state`
or the value files directly.

## Threads

Read state is separate from thread attention. On a first visit, each agent-authored
message body, including a failure receipt or authored widget, is unread; an agent
reaction is not. The original message id names its first content version, and each
`edit` id names a new one. A version is read once a `read` event names it — the
browser posts one after presenting and exposing ordinary prose, or when the user
marks a thread read — or once the user moves in its thread after it: a reply or
reaction, a resolve or reopen, or an action or request on a widget one of the thread's
messages carries; a move the user took back does not count. A later edit is unread
even when the prior version was read. A
summary does not mark read the messages it covers. `read_state.unread_content` is the
one reading; it is published as each browser Thread's `unread` and each
conversation's `unread` in `page state`. Read records belong to the page log and apply
across tabs and document revisions; they never answer a question, settle a workflow,
or enter agent delivery. The one-user page assumption is the page's current
lifecycle, not a per-account scope.

An agent comment opens a question. A substantive reply opens or resumes the thread;
when its prose leaves another question for the user, `leaf reply --awaits`
records `awaits: true`. The browser cannot write that field. A user reply
always hands the thread back to the agent, so it needs no parallel declaration.
An agent reply records the delivery event it answers as `responds`, including a
completed delivery answer whose move was settled during the turn. A proactive
message with no response address records `initiates: true` instead. Settlement
consumes this exact identity rather than log order, so answering older work cannot
erase newer user input. A substantive reply reopens a resolved conversation;
reactions and host failure receipts leave its closure standing. A later resolution
closes the conversation again. Reopening restores its still-unanswered widget Asks,
as an explicit reopen does.
A host that gives up on a move writes the failure the move's answer takes
(`conversation.fail_answer`): a reply for a message, including one in a conversation
that asked for a version, a failed `receipt` for a request, and a failed `pickup` for
an answer to a page Ask. Each carries `failure`, a nonempty host-owned code, which
is what tells a host's failed receipt from an agent's. Only the host writer supplies
`failure`, and the panel draws such a reply as a receipt whose head says the message
answers nothing, since otherwise it is indistinguishable from the answer it stands in
for.
When a reply carries a widget with a local `x-awaits` or `x-request.ask`
request, the widget's standing projection or lifecycle declares the request
instead; the CLI refuses a parallel `--awaits` flag on that markup. A frozen widget
keeps the user's Ask open until its `x-awaits.answered` condition holds. Moves on the
widget before then have not been handed over: they carry no receipt and
require no agent reply, and the move that answers carries the receipt and hands the
turn to the agent. Undoing it returns the Ask to the user and removes the reply
obligation. A frozen widget move that answers no Ask, such as a card moved
on a board sent in a reply, keeps a delivery receipt and owes no reply, under the
rule `workflows.py` states for page moves.

An open structural Ask anywhere in an unresolved thread keeps it awaiting the
user after later prose or a settling reaction. Without one, the latest spoken
turn determines the prose obligation described above. A user reaction on that
latest request whose token declares `settles` clears the prose obligation without
resolving the thread. `served_state/conversation.py` owns this precedence.

What each conversation command does for its user, and when an agent uses it, is
`../../references/conversation-threads.md`. The door and the fold hold these rules behind
them:

- `edit` revises only a comment or reply whose recorded session matches the posting
  session, and only its `text`: markup is frozen because a user action may already
  rest on a widget in it. The original stays in the log with its id, timestamp,
  author, thread position, and anchor; the panel, wait digests, and the transcript
  fold the latest text onto it and label it edited.
- `conversation_title` names an existing conversation with a nonblank, single-line
  plain-text title of at most 80 characters. The latest title is projected separately
  from messages into browser state and agent context; an unnamed conversation has
  a null title and the panel shows three animated dots until the agent names it.
- `summary` names an inclusive `from`–`through` range of at least two spoken turns in
  one conversation; a reaction may lie inside the range but not at an endpoint. A
  later overlapping summary replaces the earlier one whole, disjoint summaries
  coexist, editing a covered message invalidates its summary, and a message appended
  after the range stays outside it. A summary answers, resolves, and settles nothing.
- An agent `reply` may carry an `anchor` captured against its `revision`, or a null
  anchor when its subject has left that revision. The fold takes the latest such value
  as the thread's current location and exposes the prior one as `detached_from` while
  detached; the root event's anchor is immutable. The transition and its explanatory
  message are one append, so the page never observes a move without the message that
  accounts for it. A thread whose root `holds` a command goal cannot move or detach.
- A message body is Markdown, stored as typed and rendered by the page's own vendored
  runtime, so the renderer and the panel's styles version together; raw HTML renders as
  its own characters. A widget in a message rides the `markup` field, whose one door is
  `leaf comment`/`leaf reply`, where it is validated against the vendored registry; the
  browser door refuses the field. The door reads a body's Markdown link and image
  destinations, in text and markup alike, and refuses a `/media/…` the page directory
  cannot answer, since the directory holds `/media/<digest>.<ext>` and nothing else.

A raster image pasted into a browser text box is stored first as content-addressed page
media. Its durable draft carries an ordinary Markdown image at
`/media/<digest>.<ext>`, while the composer projects that generated block as a removable
thumbnail. The draft and message schemas gain no attachment field: retries and delivery
preserve the exact Markdown, while each HTTP presentation scopes the canonical media
path when it renders. An abandoned draft may leave unreferenced media behind; Leaf
retains it because reachability has to include every immutable revision and event before
deletion could be safe.

## Anchors

The user selects a passage and the browser writes the anchor from the selection;
`leaf comment`, and `leaf reply` when it moves a thread, write the file-confirmable
form from a quote by reading authored HTML through `leaf.passages`. The browser's
anchor pass applies the matching rules to the DOM. Projected data has no file-side
value to quote: its browser
anchor adds the projection's section and datum key, and when `projectData` names
an `x-data` input, the source id and `source_revision`, that source's revision. The
append door checks that the section binds that source; a revision other than the
current one is admitted as a comment on a value that has since been replaced. A CLI comment can still name the authored
projection seat as an element.
