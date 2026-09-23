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
words remain effective across revisions. A draft never sits inside a suggestion,
and a suggestion does not propose a widget's state.

## Honor user state

The event log preserves user choices, generated options, moves, edits, and
suggestion outcomes across revisions. Leave their authored inputs unchanged
unless the content needs revision. The page directory and standalone export
preserve that state without it being copied into markup. A user's answer to a
page Ask is the exception: it shows as waiting on you, and holds your turn open,
until a stamped version's markup records it.

When incorporating a decided suggestion into surrounding prose, retain its
surviving branch and ids. A user-generated option can become an ordinary
authored option under its owning group; retain its event-supplied id and words.
Its effective id can also anchor a separate clarification thread directly.

Worker reports remain provisional until adjudicated. Write the reported state
into markup to absorb a report, or mark its element `overruled` and explain why
in the version note. An unrelated revision may leave the report standing.

To deliberately replace state established by an action, put `restated` on the
rewritten element and explain why in the version note. Without `restated`, replay
restores the user's state and `version check` refuses a conflicting version.

## Make changes easy to find

Before handing over a changed page, compare it with the last version handed to
the user, and point at its material additions on the page with a temporary
marker. For example, options added for this turn can carry a final
`<lf-chip>new this turn</lf-chip>` in their chip row, and a new section or
paragraph a `<span class="tag">new this turn</span>`. Remove the marker from the
next handed-over revision.

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

A list of work holds what is still to do. When an item of a plan, a backlog, or a
list of problems found is done, move it out of that list into a `Complete` section
at the foot, inside a collapsed `<details>` whose summary says what is done, with
the item cut down to its outcome. A widget that tracks completion itself, such as
a milestone rail, a board, or a task list, keeps its members and shows them its own
way. Material the current state replaces, such as a concluded run or a superseded
section, is removed outright rather than kept beside its successor; keep older
material only where the current work still needs its context, collapsed the same
way. Put deferred work in the list of work with enough context to resume it.

An Ask the user answered and you have acted on is finished work too. Move it
into `Complete` with the user's answer standing, and put anything still worth
asking in a new Ask under new ids. An `lf-options` group takes `settled` there,
which collapses it to the pick. The answered Ask is the record of what the user
was asked and chose, so a picked option stays under the words it was picked under;
say what came of the choice, and correct anything those words got wrong, beside
it. Keep an Ask live while it is being applied, and settle it only after the work
no longer revisits it. Keep a section live while the user is still commenting
there.

Before handing the page back, check that its status and outstanding work agree
with what you report to the user.

When one page needs several views, use one `lf-tabs` tab set and put the primary
current view first: ordering makes it
the default for a user with no saved panel or reading position, and a saved
panel or restored position takes precedence. Context an earlier run still owes
the current one goes in a collapsed `<details>` inside the relevant tab, with any
passage whose id anchors an open thread or holds a standing decision. Threads,
asks, versions, and sign-off still cover the whole page, so none of that runtime
chrome belongs inside a tab.
