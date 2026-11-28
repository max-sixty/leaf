# Live revisions and user state

## Read before editing

Run `leaf page state <page>` and read it beside the active revision's HTML, the file
`active.file` names. The HTML is what you wrote; `state` lists, by widget, each user
action still in force, and where the two differ the page shows the user's action.

When `source.live` is false, `index.html` differs from the live revision and
`source.error` says why; reconcile the two by id and content before editing. When
`source.error` names `leaf page init`, run that command and read the state again, since
the rest of the output may be wrong until you do.

`data_bindings` names each external data source and the widgets that read it; change a
source's value with `leaf data set`. `files` names each file the page's editors edit, by
its binding: the label the page shows and the path to write it at.

Read the author instructions for the page's packages and the widgets you are revising
(`page-authoring.md`, "Read the registry"). They own how each widget keeps the user's
answer and presents it after you have acted on it.

## Publish several authored files together

When the HTML and its modules must change together, save `source.digest` from
`leaf page state <page>` before copying or editing the files. It identifies the
current `index.html` and complete `page/` tree, including an invalid source save.
Prepare a separate directory holding the replacement `index.html` and whole `page/`
tree, with any media it uses already in the live page, then publish:

```sh
leaf page stamp <page> --replace <candidate> <digest> --text 'Updated the page'
```

A successful stamp adds its version note while preserving the existing event history
and external data.

## Revisions and user-owned words

A suggestion is for wording the user has seen and might prefer to keep, such as a
passage they approved. Write one as an `lf-suggestion`, following its instructions for
markup and linking a requested fix to its thread, and introduce the first in prose so
the user knows they can comment on its new words too. Write new content and any other
rewrite, such as a correction, directly, and name a rewrite in the version note.

Put a passage whose wording belongs to the user in a draft they edit, such as
`lf-draft`. Their saved words stay in effect across revisions. Follow its registry
entry for its HTML.

## Honor user state

The event log keeps the user's choices, added options, edits and suggestion outcomes,
so don't copy them into the markup. Revise your own markup when the content needs it,
keeping the meaning of the user's decisions. To ask the user again about a decision,
follow the registry's `$restated`.

Take in a user's answer to a page's obligation in a stamped version. Where the widget's
`verbs` declares a `record` form, write that form as its author instructions
describe. Where it declares no form, the next stamp takes in the answer. Preserve the
user's decisions and the ids of content you retain. A worker's report likewise stays
provisional until the stamped revision its `handling` asks for.

## Make changes easy to find

Before handing over a changed page, compare it with the last version the user saw and
mark each significant addition, such as a `.lf-tag` reading "new" beside a new section's
heading. Remove those marks in the next version you hand over.

## Keep the current page current

[SOUL.md](../SOUL.md), "Keep the page current and the record trustworthy", sets the
goal: the page is the one you would write now for a reader arriving now. It leads with
where the work stands and what waits on the user, keeps open only what that reader
needs for the current work, however true the rest remains, and shows each result on
something that still exists. The rest goes, such as a concluded run, a superseded
section or material about something since removed, or is collapsed where the current
work still rests on it. Restructuring the page is an ordinary revision. Threads and
user state follow ids (`page-authoring.md`, "Stable anchors"), so a passage you keep
keeps its id wherever it moves, and moving it needs neither a suggestion nor
`restated`.

When a revision removes a passage a thread quotes, `threads.md`, "Preserve revised
anchors", says where the thread goes and how to move it onto the passage's replacement.

A work list shows unfinished items. When an item of a plan, backlog or list of
problems is done, cut it down to its outcome and move it to the finished work,
collapsed after the open work, such as a `<details>` at the bottom or a separate tab.
A widget that tracks completion itself, such as a board or task list, keeps its
members. Keep deferred work in the list with enough context to resume it.

A decision the user answered and you have acted on becomes a record. Present it as
the widget's instructions describe, and say beside it what you did about the choice.
Anything the choice sets in motion that hasn't happened yet reads as decided, not
under way. Keep the result and its evidence
in the current reading flow while the reader still needs them (`page-authoring.md`,
"Reading cost"); retire the superseded interaction as finished work. Pose anything
still worth asking as a new decision with new ids. Use `$restated` to ask about the
decision again.
Keep a section open while the user is still commenting there.

The user reads threads to find out how their input was addressed. When a revision
resolves the question or completes the work discussed in an open thread, reply there
with the result and where the page shows it, so the thread is not left looking
unanswered.

Before handing the page back, check that its status, open to-dos and outstanding work
agree with what you tell the user.
