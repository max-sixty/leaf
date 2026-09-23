# Live revisions and user state

## Read before editing

Run `leaf page state <page>` and read its `content` tree. Each node joins its
effective words, attributes, standing state, and data inputs with their origin.
`content_source` names the active file, mutable `edit_file`, and vocabulary file.
An authored node's `source` gives its line and column; `edit` identifies who can change it.
The tree is a reading, so effective content may differ from authored HTML. Look up
the node's `vocabulary` tag in the shared vocabulary file when needed.

When `edit.matches_active` is false, the candidate in `index.html` differs from
the live revision. Its source locations still refer to the active file; reconcile
the candidate by stable id and content before editing. `inputs` names external
values and their mutation route: `data set` for live inputs, `capture-and-rebind`
for pinned inputs. Inspect frozen conversation content with
`leaf conversation read <page> <id>`; change it through that conversation.

## Revisions and user-owned words

Fresh content is authored directly. Rewrite prose the user has already seen as
an `lf-suggestion`: `lf-old` carries the current markup verbatim, `lf-new` carries
the proposed replacement, and `resolves="<comment-id>"` connects a requested fix
to its thread. Introduce the first suggestion in prose so the user knows its
new words can also receive comments.

A suggestion is for wording the user could reasonably prefer as it stands. A
correction is not a proposal, and neither is a change in the facts. Where the page
got something wrong, such as a number, a misread source, or a unit, or where work
has landed, a decision has been made, or a finding no longer holds, rejecting the
rewrite would only restore a page that is wrong or out of date, so the user has
nothing to weigh: write the true thing straight and name the change in the version
note.

Use `lf-draft` for a passage whose wording belongs to the user. Their submitted
words remain effective across revisions.

## Honor user state

The event log preserves user choices, generated options, moves, edits, and
suggestion outcomes across revisions. Leave their authored inputs unchanged
unless the content needs revision. The page directory and standalone export
preserve that state without it being copied into markup.

A user's answer to a page Ask is the exception: it shows as waiting on you, and
holds your turn open, until a stamped version takes it in. Where the answering
widget declares a markup form for its state (its `x-state` `record`), that
version's markup has to show the answer in that form: `chosen` on exactly the
picked `lf-option` elements, with an option the user added written in as an
ordinary option under its id and words, or the user's words as the body of a
`needed` `lf-draft`. The next version you stamp takes in an answer with no such
form, such as an accepted suggestion or a playground's submitted settings.

When incorporating a decided suggestion into surrounding prose, retain its
surviving branch and ids.

A worker's report stays provisional until a stamped version answers it, as its
delivered `handling` says.

To deliberately replace state established by an action, follow the registry's
`$restated`.

## Make changes easy to find

Before handing over a changed page, compare it with the last version handed to
the user, and mark its material additions so the user finds each one without
rereading the page, such as a `.tag` reading "new" beside a new section's
heading. The marker says what changed since the user last looked, so take it off
in the next handed-over revision.

## Keep the current page current

The main skill's "Keep the user current" sets the goal: the page the user
returns to is the one you would write today. Rewriting the page to get there, its
structure included, is an ordinary revision, and when the structure changes, write
`index.html` whole rather than as a series of edits. Ids are what carry threads and
user state across a rewrite (`page-authoring.md`, "Stable anchors"), so a passage
that survives keeps its id wherever on the page it goes, and moving it needs neither
a suggestion nor `restated`. `version check` refuses a rewrite that drops an id an
open thread or the user's state still rests on, and names the way out. It does
not guard the words an open thread quotes, so leave those as they stand while the
thread is open.

A list of work holds what is still to do. When an item of a plan, a backlog, or a list
of problems found is done, move it out of that list to the finished work, which sits
collapsed after the open work, with the item cut down to its outcome, for example in a
`<details>` at the foot whose summary says what is done. A widget that tracks
completion itself, such as a milestone rail, a board, or a task list, keeps its
members and shows them its own way. Material the current state replaces, such as a
concluded run, a superseded section, or a page tab the current work no longer needs
(the `lf-tabs` entry says what of it to keep), is removed outright rather than kept
beside its successor; keep older material only where the current work still needs its
context, collapsed the same way. Put deferred work in the list of work with enough
context to resume it.

An Ask the user answered and you have acted on is finished work too. Move it whole
to the finished work with the user's answer standing, and put anything still worth
asking in a new Ask under new ids. An `lf-options` group takes `settled` there,
which collapses it to the pick. The answered Ask is the record of what the user
was asked and chose: say what came of the choice beside it, and correct its words
only as the registry's `$restated` says. Keep an Ask live while it is being
applied, and settle it only after the work no longer revisits it. Keep a section
live while the user is still commenting there.

Before handing the page back, check that its status and outstanding work agree
with what you report to the user.
