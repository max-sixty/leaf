# Live revisions and user state

## Read before editing

Run `leaf page state <page>`, and read the active revision's HTML, the file
`active.file` names in the page directory, beside it. The HTML is what you authored;
`state` lists each user move that stands over it, by widget, with the words, choice or
position it carries, so where the two differ the page shows the move. Look up a
widget's tag in the page's `registry.json` when needed.

When `source.live` is false, the candidate in `index.html` differs from the live
revision and `source.error` says why; reconcile the candidate by stable id and content
before editing. `data_bindings` names each external source and the widgets that read
it, and `data/<source>.json` holds its value; change one with `leaf data set` or by
rewriting that file. `leaf page state <page> <id>` narrows the reading to what the id
names: a page widget's element, standing moves, Asks and workflows, or a thread's
messages with their frozen widget content, which changes only through that thread.

## Publish several authored files together

When HTML and its modules must change together, prepare a separate candidate
directory containing `index.html` and the complete `page/` tree, with its referenced
media already present in the live page. Tools read the current authored inputs with
`leaf.publishing.authored_files` and obtain their precondition through
`leaf.publishing.authored_digest`. Publish the candidate with:

```sh
leaf page stamp <page> --from-directory <candidate> --if-source <digest> --text 'Updated the page'
```

The stamp owner replaces, validates and publishes those authored inputs in one
transaction. A stale precondition refuses the replacement; a refused candidate
restores the previous inputs before the page can read them. This replacement
includes neither the event log nor external data.

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
words remain effective across revisions. The passage renders Markdown for reading;
Edit opens the exact source in the shared Markdown text field. Save records that
source as the replacement, Cancel discards the unsaved edit, and Close keeps it.
The editing controls stay inside the box; comments and receipts use annotations.
The `<pre>` holds exact Markdown, including leading blank lines, indentation, and
trailing whitespace. Follow the `lf-draft` registry entry's instructions and example
for its HTML spelling; that entry owns how the source accounts for HTML's consumed
opening newline. Enter writes a new line; ⌘/Ctrl+Enter saves the edit.

## Honor user state

The event log preserves the user's choices, added options, edits, and suggestion
outcomes. Revise their authored inputs when the content needs it, and preserve
the decision's meaning in the record. The page directory and export retain
state without copying it into markup. To withdraw a decision, follow the
registry's `$restated`.

When changing cards in a board column, place each moved card
in the column and rank that `state` names. The registry's `$state`
defines ranks. That placement becomes authored markup; later versions can
revise it.

Take in a user's answer to a page Ask in a stamped version. Where the widget's
`x-state` declares a `record` form, show that form when incorporating the answer:
`chosen` on exactly the picked `lf-option` elements, with user-added options under
their original ids and words, or the user's words as the body of a `needed`
`lf-draft`. Where it declares no form, such as an accepted suggestion or submitted
playground settings, the next stamp takes in the answer. Until then the answer
waits on you, as its delivered `handling` says.

When incorporating a decided suggestion into surrounding prose, retain its
surviving branch and ids. A worker report also stays provisional until the
stamped revision its delivered `handling` requires.

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
a suggestion nor `restated`. Revisions may remove referenced ids or
change decided wording. When a quoted passage or visual part disappears, its thread
falls back to its surviving section; when that section disappears, it detaches.
Prefer an explicit replacement passage when you know the subject's new location
(`threads.md`, "Preserve revised anchors"). The original anchor and answer remain
in the log.


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
directly when needed. Use `$restated` when the decision itself should be withdrawn
and asked again. Keep an Ask live while it is being
applied, and settle it only after the work no longer revisits it. Keep a section
live while the user is still commenting there.

Before handing the page back, check that its status, open tasks and outstanding
work agree with what you report to the user.
