# Live revisions and user state

## Read before editing

Run `leaf page state <page>` and read it beside the active revision's HTML, the file
`active.file` names. The HTML is what you wrote; `state` lists, by widget, each user
action still in force, and where the two differ the page shows the user's action.
`data_bindings` names each external data source and the widgets that read it; change
a source's value with `leaf data set`.

When `source.live` is false, `index.html` differs from the live revision and
`source.error` says why; reconcile the two by id and content before editing. When
`source.error` names `leaf page init`, run that command and read the state again,
since the rest of the output may be wrong until you do.

## Publish several authored files together

When the HTML and its modules must change together, prepare a separate directory
holding `index.html` and the whole `page/` tree, with any media it uses already in
the live page. Take the current files' digest with
`leaf.publishing.authored_digest`, then stamp the directory in one step; the stamp
refuses if the page's files changed since the digest, and keeps the old files if the
new ones fail the check:

```sh
leaf page stamp <page> --from-directory <candidate> --if-source <digest> --text 'Updated the page'
```

## Revisions and user-owned words

Write new content directly. Rewrite prose the user has already seen as an
`lf-suggestion`: `lf-old` holds the current markup verbatim, `lf-new` the
replacement, and `resolves="<comment-id>"` links a requested fix to its thread.
Introduce the first suggestion in prose so the user knows they can comment on its new
words too.

A suggestion is for wording the user might prefer to keep. When the page got a
number, a source or a unit wrong, or when work has landed, a decision has been made
or a finding no longer holds, write the correct text directly and name the change in
the version note.

Use `lf-draft` for a passage whose wording belongs to the user; their saved words
stay in effect across revisions, as its registry entry describes.

## Honor user state

The event log keeps the user's choices, added options, edits and suggestion
outcomes, so don't copy them into the markup. Revise your own markup when the
content needs it, keeping the meaning of the user's decisions. To withdraw a
decision, follow the registry's `$restated`. When you move cards in a board, place
each card in the column and rank `state` gives it (`$state` defines ranks).

Take in a user's answer to a page's obligation in a stamped version. Where the
widget's `x-state` declares a `record` form, write that form: `chosen` on exactly the
picked `lf-option` elements you wrote, or the user's words as the body of a `needed`
`lf-draft`. Leave an option the user added out of the markup; the log keeps it.
Where the widget declares no form, as for an accepted suggestion or submitted
playground settings, the next stamp takes in the answer. A worker's report likewise
stays provisional until the stamped revision its `handling` asks for. When you work
a decided suggestion into the surrounding prose, keep its surviving branch and its
ids.

## Make changes easy to find

Before handing over a changed page, compare it with the last version the user saw
and mark each significant addition, such as a `.tag` reading "new" beside a new
section's heading. Remove those marks in the next version you hand over.

## Keep the current page current

[SOUL.md](../SOUL.md), "Keep the page current and the record trustworthy", sets the
goal. Restructuring the page is an ordinary revision; write `index.html` whole
rather than as a series of edits. Threads and user state follow ids
(`page-authoring.md`, "Stable anchors"), so a passage you keep keeps its id wherever
it moves, and moving it needs neither a suggestion nor `restated`. When a revision
removes a passage a thread quotes, move or detach the thread (`threads.md`,
"Preserve revised anchors").

A list of work holds what is still to do. When an item of a plan, backlog or list of
problems is done, cut it down to its outcome and move it to the finished work,
collapsed after the open work, such as a `<details>` at the foot or a tab of its
own. A widget that tracks completion itself, such as a board or task list, keeps its
members. Remove material the current state replaces, such as a concluded run or a
superseded section; keep older material, collapsed, only where current work needs
its context. Keep deferred work in the list with enough context to resume it.

A decision the user answered and you have acted on becomes a record. Give its
`lf-options` group the `settled` attribute, which collapses it to the pick, and say
beside it what came of the choice. Keep the result and its evidence in the current
reading flow while the reader still needs them (`page-authoring.md`, "Reading
cost"), and retire the superseded interaction as finished work. Pose anything still
worth asking as a new decision with new ids, or use `$restated` to withdraw the
decision and ask again. Mark a decision `settled` only once you have finished
applying it, and keep a section open while the user is still commenting there.

Before handing the page back, check that its status, open to-dos and outstanding
work agree with what you tell the user.
