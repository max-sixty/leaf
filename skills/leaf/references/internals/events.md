# Events and conversation

Event kinds: comment (optional anchor {section, quote, and the neighbouring
text as prefix/suffix where there is any, which is what tells two identical
passages apart; a browser selection on projected data carries datum,
the stable key local to section, instead of treating neighbouring values as
identity; `response: {kind: version, verb}` when the originating widget requires
the agent to revise its declared answer state rather than reply), reply (parent=id),
edit (agent; message=id, replacing only that message's visible text),
resolve (parent=id), unresolve (the reader reopening a resolved thread by parent=id),
done (user sign-off; the banner offers it, and this door
takes it, only on a page declaring <meta name="lf-review" content="sign-off"> —
approval is the page's decision, and a page that asks nothing gets no terminal
control at all), action (user; a widget reporting the
user editing the document through it — widget=element id, action=verb, detail
per widget, revision the edit was made against; a verb declaring `creates`
also carries `generated`, the canonical sorted snapshot of the declared detail
map's keys), report (agent; a worker's
provisional state change on a page widget — same widget/action/detail/revision
shape as an action, validated by the widget's x-report declaration at the
`leaf report` door, and standing only until a stamped revision answers it),
request (user; a durable, non-undoable one-shot instruction whose widget,
action, typed detail, and revision are validated against the holder's
`x-request` declaration and exact direct-child offers; when that declaration has
`decision: true`, the ready lifecycle is a reader decision, acceptance hands it to the host,
and a failed receipt reopens it), receipt (agent; exactly
one terminal `succeeded` or `failed` outcome naming a prior request), note
(agent; one stamped checkpoint's public `version`, exact `revision`, and
changelog, carrying `restated`: the element ids whose decisions that revision
took back, and `settles`: the report or work targets the stamp answered), error (the page's own runtime reporting a
failure in front of the user — author=page, heard by the watcher like a report
and never counted against the reader).

undo (the reader taking a gesture back, `undoes` naming it — a resolve, an
unresolve, or an action, per UNDOABLE_KINDS) is the log's one word for that, and
it names the gesture and nothing else: every other field is the target's to
state. It withdraws rather than deletes. Nothing is removed from the log; the
folds and the thread reading simply drop the event, so the page is what the
revision says plus what still stands — the same sentence a reload has always
read, and the same one `restated` already writes from the author's side. What
the reader sees follows from that rather than from a second statement: where the
log still leaves the unit a state that can be stated, the browser states it (a
prior action's detail, or the placement the revision's markup arrived showing) so
the page moves rather than being rebuilt; where the verb records nothing, and so
no state can be stated, the browser rebuilds that widget from the revision's own
markup and replays what survives onto it. The door refuses an `undoes` naming
anything but an unwithdrawn gesture of the reader's own.

The server stamps every other
browser-posted event author=user; agent-side `leaf comment`, `leaf reply`, `leaf edit`,
`leaf report`, and `version stamp` stamp the wire
role author=claude plus the posting session's own voice: `agent`, its display name,
and `session`, its host session id. `leaf receipt` uses that same identity. Several
agent sessions can write to one page,
so the voice is read from the poster's environment rather than from the current
watcher's claim record — and identity is the session id, because a display name
is anyone's to choose and two workers may share one.

An agent comment opens a question. A reply answers without closing the thread;
when its prose leaves another question for the reader, `leaf reply --awaits`
records `awaits: true`. The browser cannot write that field. A reader reply always
hands the thread back to the agent, so it needs no parallel declaration. When a
reply carries a widget with a local `x-awaits` or `x-request.decision` request, the
widget's standing projection or lifecycle declares the request instead; the CLI
refuses a parallel `--awaits` flag on that markup.

`leaf edit` may revise only a comment or reply whose recorded session matches the
posting session. It appends rather than rewriting: the original message and every
revision remain visible in `leaf events`, while the panel, wait digests, and the
transcript fold the latest text onto the original message and label it edited.
`leaf events --thread` selects both records as the conversation's authoritative
history without adding another copy of its prose to page state. The
original id, timestamp, author, thread position, anchor, and markup remain its own.
Markup is deliberately not editable because a reader action may already rest on a
widget frozen into it.

A message body is Markdown, stored as typed and rendered by the page's own
vendored runtime — the browser is where the page's other rendering already
lives, and vendoring the renderer beside the panel's styles keeps the two
versioning together. A fragment link in a body — `[the group](#d-channel)`,
written by either author — points at an element of the page, and the browser's
own navigation carries the reader there, opening whatever tab or settled group
hides it. Two parts of that are the runtime's: handling an arrival aimed by such
a link (a ⌘-click opens a tab the browser answers before any widget has
upgraded), and marking a link this version can't follow, since a message
outlives the version it was written on. Raw HTML in a body renders as its own
characters, so text cannot inject markup. A widget in a message rides the
event's `markup` field instead, whose one door is `leaf comment`/`leaf reply`,
where it is validated against the vendored registry — the discussion-side analog
of `version check`. The browser door refuses the field, so everything in the log
under that name has been through the gate.

A browser comment carrying `response: {kind: version, verb}` is a request to change authored
state. Its exact-section view is text-only, and `leaf reply` refuses every
message in that thread. When the change needs clarification, the agent opens a
separate comment thread in the same exact-section seat. That thread carries the
version response through the stop gate while it waits on the reader; their answer
hands both back to the agent. The original remains open until authored state in a
later published version answers an originating open decision, or changes the
declared answer when the decision was already answered. Log actions do not
substitute for that version. That is also when `leaf resolve` first accepts it.

Either side can open a thread and either side can close one, and `author` is the
whole difference between them. The user selects a passage and the browser writes
the anchor from the selection; `leaf comment` writes its file-confirmable form
from a quote by reading authored HTML through `leaf.passages`. The
browser's anchor pass applies the matching rules to the DOM. Projected data has
no file-side value to quote: its browser anchor
adds the projection's section and datum key, and a CLI comment can still name the
authored projection seat as an element. Everything downstream already turns on
`author`: `leaf wait`
prints user events and the banner counts them, so Claude's own comment neither
wakes its own watcher nor reads as unanswered. Closing runs the other way round,
because a note's purpose is discharged by being read, and only the reader knows
that happened. So `leaf resolve` is the agent's door onto closing, and the
reader is still the one who ordinarily closes a thread. A thread the reader did
not close is the one settlement they cannot watch happen, so the panel and the
transcript both name the agent that did it.
