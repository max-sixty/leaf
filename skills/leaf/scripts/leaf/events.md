# Events and conversation

Every event carries `id`, `ts`, `author`, `kind`, `seq` (its line number in
`events.jsonl`), and `revision` (the document it was made against). An `id` is
an opaque string matched whole. The append door mints eight hex characters,
re-rolling any candidate this log already holds, so an id is unique within its
page and is not a global identifier. The kinds:

| Kind | Author | Door | Fields | Meaning |
| --- | --- | --- | --- | --- |
| `comment` | user or agent | `POST /api/event`, `leaf comment` | `text`, `drawing`, or `token`; optional `anchor`, `suggestion`, `about: "design"`, `response`, `markup` (CLI only) | opens a question, or with `token` puts a reaction mark on the anchor |
| `reply` | user or agent | `POST /api/event`, `leaf reply` | `parent`; `text` or `token`; agent `responds` or `initiates`; `awaits`, `markup`, and a replacement `anchor` or null detachment (CLI only) | answers the exact named obligation without closing its conversation; an agent reply may also replace or remove the conversation's current location |
| `edit` | agent | `leaf edit` | `message`, `text` | replaces one message's visible text; the original stays in the log |
| `conversation_title` | agent | `leaf conversation title` | `conversation`, `title` | names a conversation in the panel; latest title wins without adding a turn or settling work |
| `summary` | agent | `leaf conversation summarize` | `conversation`, `from`, `through`, `text` | replaces one contiguous range with Markdown in the thread panel; originals stay in the log and remain revealable |
| `resolve` | user or agent | `POST /api/event`, `leaf resolve` | `parent` | closes a thread |
| `unresolve` | user | `POST /api/event` | `parent` | the reader reopens a resolved thread |
| `done` | user | the banner, only on a page declaring `<meta name="lf-review" content="sign-off">` | | approval of the declared sign-off; a page that asks nothing gets no terminal control |
| `action` | user | `POST /api/event` from a widget | `widget`, `action`, `detail`, optional declared-role `references`; server-stamped `meaning` and, for a verb declaring `creates`, `generated` | the reader edited the document through the widget |
| `report` | agent or worker | `leaf report` | as `action`, validated by the widget's `x-report`; `--references` supplies its declared role map | provisional state that stands until a stamped revision answers it |
| `request` | user | `POST /api/event` from a widget | `widget`, `action`, `detail`, validated by the holder's `x-request` and its direct-child offers | a durable, non-undoable one-shot instruction to the host |
| `receipt` | agent | `leaf receipt` | `request`, `succeeded` or `failed`, `text` | exactly one terminal outcome per accepted request |
| `pickup` | page | the delivery carrier | `events`, `phase` (`queued` or `opened`), `session`, `turn` | the named reader events reached the durable Codex queue or entered an exact agent turn; idempotent per event, phase, session, and turn; never a work claim |
| `note` | agent | `leaf version stamp` | `version`, `revision`, changelog `text`, `restated`, `settles` | one public version mapped to an immutable revision, naming the decisions it took back and the reports or work it answered |
| `error` | page | the runtime | | the page reported a failure in front of the user; heard like a report, never counted against the reader |
| `undo` | user | `POST /api/event` | `undoes` | withdraws one gesture of the reader's own (`UNDOABLE_KINDS`: resolve, unresolve, action, done) |

An `anchor` names a passage by `section` and `quote`, with `prefix` and `suffix`
where neighbouring text tells two identical passages apart; a selection on
projected data names `datum` (the stable key local to its section) and, when the
projection names an external input, `source` and `data_revision`; `visual` names
a declared part of a picture and `part` the control a design comment landed on.
`response: {kind: version, verb}` on a comment says the originating widget
requires the agent to revise its declared answer state rather than reply.

A `drawing` is up to 32 freehand strokes (`strokes`, each a list of points) attached to
an ordinary comment, and may be that comment's only content. Its first stroke decides
whether it anchors on an element or on the page, and with it the browser records `box`
and `says`; `../../references/conversation-threads.md` says how to read the three. The
browser reads them off the rendered page, which holds words and geometry no file
reading can produce, so the door bounds their shape, the stroke count and 500
characters of `says`, and does not re-read them. Leaf derives the drawing's frame and
owns ink, weight, SVG construction, and replay. A drawing is immutable once sent,
follows the thread's resolution state, and is omitted from the default standalone
export with the rest of discussion chrome.

## Undo

`undo` names the gesture and nothing else; every other field is the target's to
state. It withdraws rather than deletes: nothing leaves the log, and the folds and
the thread reading drop the event, so the page is what the revision says plus
what still stands, the same reading a reload has always made and the one
`restated` writes from the author's side. `renderState` paints withdrawals and
forward changes alike, retaining the widget and its independent children. The
door refuses an `undoes` naming anything but an unwithdrawn gesture of the
reader's own. An exact control may withdraw a forward action before that action's
POST finishes: the browser derives the withdrawal immediately, keeps both gestures
in its ordered ledger, and replaces the local dependency with the accepted action id
before sending the undo. Refusal of the action discards its dependent undo; refusal
of the undo re-derives the still-standing action.

## Authorship and voice

The server stamps every browser-posted event `author=user`. `leaf comment`,
`leaf reply`, `leaf edit`, `leaf report`, `leaf receipt`, and `version stamp`
stamp `author=agent` plus the posting session's own voice: `agent`, its display
name, and `session`, its host session id. Several agent sessions can write to one
page, so the voice is read from the poster's environment rather than from the
watcher's claim record, and identity is the session id, because a display name is
anyone's to choose.

Everything downstream turns on `author`: `leaf wait` prints user events and the
banner counts them, so an agent's own comment neither wakes its own watcher nor
reads as unanswered. Either side can open a thread and either side can close one.
A note's purpose is discharged by being read, and only the reader knows that
happened, so the reader ordinarily closes a thread; `leaf resolve` is the agent's
door onto closing, and a thread the agent closed is named as such in the panel
and the transcript.

## Admission

Every event reaches the log through one door. The browser endpoint, each `leaf`
writer, the delivery carrier, and `version stamp` all append through it, under the
page transaction's lease, and nothing else appends. It admits in one order for
every kind: an accepted retry returns its own event and repeats no gesture; the
revision the event names supplies the vocabulary that admits it, so a re-vendor
cannot reinterpret a document its reader is still looking at; that vocabulary has
to declare the kind; the kind's gates run against the page and the standing log;
server-owned meaning is derived; and the finished record is checked against the
stored-record contract for its kind. A refusal says what to do about it, as a
command's exit or a final 400 — a gate is stated once and holds for every writer,
rather than for whichever one remembered it. Only the transport differs above the
door: which kinds a browser may post, which fields it may send, and how a retry is
answered.

Browser POSTs are commands. The append transaction stamps the accepted event with
server-owned `meaning`; callers cannot send it or `generated`, and retry identity
compares the original command fields rather than this enrichment. Actions and
reports record `document`, the `[owner, unit, facet]` coordinate, and `depends`,
the direct element identities named by declared state fields. Requests record
their page-revision or frozen-thread document identity. A declared
`x-awaits.answers` verb additionally records `answer`: a thread id closes that
conversation, null states an answer that leaves it open, and an absent field is
not an answer. Historical conversation folds use this coordinate even after its
widget retires. Every action at the coordinate competes: a non-answer at that
same coordinate supersedes its prior answer, while an independent facet leaves it
standing.

Dependency identities come from the fold unit, attribute-set and position record
fields, plus id or anchor identities in the verb's declared event `references` roles.
Each role carries an id or structural target record beside `detail`; admission resolves
it uniquely inside the sending page revision's authored `<main>` or the sender's one
frozen-markup fragment and checks any `{via, where}` relation. Literal detail strings do
not become dependencies by matching HTML ids. The log does not freeze ancestry:
retraction tests use the current document's containment of those identities.
Generated children retain the durable ownership established by `creates`, whose
sorted identity snapshot the server stamps in `generated`.

## Threads

An agent comment opens a question. A reply answers without closing the thread;
when its prose leaves another question for the reader, `leaf reply --awaits`
records `awaits: true`. The browser cannot write that field. A reader reply
always hands the thread back to the agent, so it needs no parallel declaration.
An agent reply records the delivery event it answers as `responds`; a proactive
`--initiates` reply records `initiates: true`. Settlement consumes this durable
scope rather than log order, so answering older work cannot erase newer reader input.
A host that settles an ask because it cannot start work records `failure`, a nonempty
host-owned code, on its reply; only the host reply writer can supply it, and the panel
draws such a reply as a receipt whose head says the message answers nothing, since
otherwise it is indistinguishable from the answer it stands in for.
When a reply carries a widget with a local `x-awaits` or `x-request.ask`
request, the widget's standing projection or lifecycle declares the request
instead; the CLI refuses a parallel `--awaits` flag on that markup. A frozen widget
whose `x-awaits.until` applies keeps the reader's Ask open until its declared
completion verb stands. Interim actions still receive delivery receipts, but
require no agent reply; completion hands the turn to the agent. Undoing that
completion returns the Ask to the reader and removes the reply obligation.

What each conversation command does for its reader, and when an agent uses it, is
`../../references/conversation-threads.md`. The door and the fold hold these rules behind
them:

- `edit` revises only a comment or reply whose recorded session matches the posting
  session, and only its `text`: markup is frozen because a reader action may already
  rest on a widget in it. The original stays in the log with its id, timestamp,
  author, thread position, and anchor; the panel, wait digests, and the transcript
  fold the latest text onto it and label it edited.
- `conversation_title` names an existing conversation with a nonblank, single-line
  plain-text title of at most 80 characters. The latest title is projected separately
  from messages into browser state and agent context; an unnamed conversation has
  a null title and the panel uses its opening text until the agent names it.
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
- A comment carrying `response: {kind: version, verb}` asks for a change to authored
  state. `leaf reply` into that thread is refused, though the reader may still write
  there, and `resolve` is accepted only once a later stamped version's authored state
  answers the originating Ask, or changes its declared answer where the Ask was
  already answered; a log action does not substitute.
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
an `x-data` input, the source id and `data_revision`. The append door checks that
the section displayed that source revision: a racing current-value replacement is
admitted as an outdated comment; a future revision, another source, or the wrong
immutable snapshot is refused. A CLI comment can still name the authored
projection seat as an element.
