# Events and conversation

Every event carries `id`, `ts`, `author`, `kind`, `seq` (its line number in
`events.jsonl`), and `revision` (the document it was made against). The kinds:

| Kind | Author | Door | Fields | Meaning |
| --- | --- | --- | --- | --- |
| `comment` | user or agent | `POST /api/event`, `leaf comment` | `text`, `drawing`, or `token`; optional `anchor`, `suggestion`, `about: "layer"`, `response`, `markup` (CLI only) | opens a question, or with `token` puts a reaction mark on the anchor |
| `reply` | user or agent | `POST /api/event`, `leaf reply` | `parent`; `text` or `token`; `awaits`, `markup`, and a replacement `anchor` (CLI only) | answers a thread without closing it; an anchored agent reply also moves the thread's current location |
| `edit` | agent | `leaf edit` | `message`, `text` | replaces one message's visible text; the original stays in the log |
| `resolve` | user or agent | `POST /api/event`, `leaf resolve` | `parent` | closes a thread |
| `unresolve` | user | `POST /api/event` | `parent` | the reader reopens a resolved thread |
| `done` | user | the banner, only on a page declaring `<meta name="lf-review" content="sign-off">` | | approval of the declared sign-off; a page that asks nothing gets no terminal control |
| `action` | user | `POST /api/event` from a widget | `widget`, `action`, `detail`; server-stamped `meaning` and, for a verb declaring `creates`, `generated` | the reader edited the document through the widget |
| `report` | agent or worker | `leaf report` | as `action`, validated by the widget's `x-report` | provisional state that stands until a stamped revision answers it |
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

A `drawing` is one bounded freehand stroke attached to an ordinary comment and may be
that comment's only content. When the drag starts over a semantic item or in the margin
alongside it, its element anchor remains the thread coordinate and points are CSS-pixel
offsets from that target's top-left origin. A drag starting where no item shares its line
has no anchor and its points are offsets from the document origin. Either stroke may
continue anywhere across the page. Leaf derives the stroke's frame and owns ink, weight,
SVG construction, and replay. A drawing is immutable once sent, follows the thread's
resolution state, and is omitted from the default standalone export with the rest of
discussion chrome.

## Undo

`undo` names the gesture and nothing else; every other field is the target's to
state. It withdraws rather than deletes: nothing leaves the log, and the folds and
the thread reading drop the event, so the page is what the revision says plus
what still stands, the same reading a reload has always made and the one
`restated` writes from the author's side. `renderState` paints withdrawals and
forward changes alike, retaining the widget and its independent children. The
door refuses an `undoes` naming anything but an unwithdrawn gesture of the
reader's own.

## Authorship and voice

The server stamps every browser-posted event `author=user`. `leaf comment`,
`leaf reply`, `leaf edit`, `leaf report`, `leaf receipt`, and `version stamp`
stamp `author=claude` plus the posting session's own voice: `agent`, its display
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
fields, and optional `references` detail-field declarations. Literal strings do
not become dependencies by matching HTML ids. The log does not freeze ancestry:
retraction tests use the current document's containment of those identities.
Generated children retain the durable ownership established by `creates`, whose
sorted identity snapshot the server stamps in `generated`.

## Threads

An agent comment opens a question. A reply answers without closing the thread;
when its prose leaves another question for the reader, `leaf reply --awaits`
records `awaits: true`. The browser cannot write that field. A reader reply
always hands the thread back to the agent, so it needs no parallel declaration.
When a reply carries a widget with a local `x-awaits` or `x-request.ask`
request, the widget's standing projection or lifecycle declares the request
instead; the CLI refuses a parallel `--awaits` flag on that markup.

`leaf edit` may revise only a comment or reply whose recorded session matches the
posting session. It appends rather than rewriting: the original message and every
revision remain visible in `leaf events`, while the panel, wait digests, and the
transcript fold the latest text onto the original message and label it edited.
The original id, timestamp, author, thread position, anchor, and markup remain
its own. Markup is not editable because a reader action may already rest on a
widget frozen into it.

An agent reply may carry an `anchor` captured against its `revision`. The fold uses
the latest such anchor as the thread's current location while retaining the opening
comment's anchor on the immutable root event. The anchor and explanatory reply are
one append, so the page never observes a move without the message that accounts for
it. A thread whose root `holds` a command goal cannot move, and a version-response
root takes no reply at all, because those anchors are part of the request's meaning.

A message body is Markdown, stored as typed and rendered by the page's own
vendored runtime, so the renderer and the panel's styles version together. A
fragment link in a body (`[the group](#d-channel)`) points at an element of the
page; the browser's own navigation carries the reader there, opening whatever
tab or settled group hides it, and the runtime marks a link this version can't
follow, since a message outlives the version it was written on. Raw HTML in a
body renders as its own characters. A widget in a message rides the event's
`markup` field instead, whose one door is `leaf comment`/`leaf reply`, where it
is validated against the vendored registry; the browser door refuses the field.
An agent's body is read for a `/media/…` reference at that same door, whether it
arrives as text or markup, since either names a file the page directory has to
have — and the directory holds `/media/<digest>.<ext>` and nothing else, so any
other one under that root is a file it can never answer. Text is read where the runtime resolves one — a Markdown link or image
destination — so a path quoted in prose is words, as it is in authored markup;
the browser's own paste stores the image before the reference exists.

A raster image pasted into a browser text box is stored first as content-addressed page
media. Its durable draft carries an ordinary Markdown image at
`/media/<digest>.<ext>`, while the composer projects that generated block as a removable
thumbnail. The draft and message schemas gain no attachment field: retries and delivery
preserve the exact Markdown, while each HTTP presentation scopes the canonical media
path when it renders. An abandoned draft may leave unreferenced media behind; Leaf
retains it because reachability has to include every immutable revision and event before
deletion could be safe.

A browser comment carrying `response: {kind: version, verb}` is a request to
change authored state. Its exact-section view is text-only, and `leaf reply`
refuses every message in that thread. When the change needs clarification, the
agent opens a separate comment thread in the same exact-section seat; that
thread carries the version response through the stop gate while it waits on the
reader, and their answer hands both back to the agent. The original remains open
until authored state in a later published version answers an originating open
Ask, or changes the declared answer when the Ask was already answered.
Log actions do not substitute for that version. That is also when `leaf resolve`
first accepts it.

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
