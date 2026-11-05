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
source's value with `leaf data set`.

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

Write new content directly. Rewrite prose the user has already seen as an
`lf-suggestion`: `lf-old` holds the current markup verbatim, `lf-new` the replacement,
and `resolves="<comment-id>"` links a requested fix to its thread. Introduce the first
suggestion in prose so the user knows they can comment on its new words too.

A suggestion is for wording the user might prefer to keep. A correction is not: when
the page got a number, a source or a unit wrong, or when work has landed, a decision
has been made or a finding no longer holds, write the correct text directly and name
the change in the version note.

Use `lf-draft` for a passage whose wording belongs to the user. Their saved words stay
in effect across revisions. Follow the `lf-draft` registry entry
for its HTML.

## Honor user state

The event log keeps the user's choices, added options, edits and suggestion outcomes,
so don't copy them into the markup. Revise your own markup when the content needs it,
keeping the meaning of the user's decisions. To withdraw a decision, follow the
registry's `$restated`.

When you move cards in a board, place each card in the column and rank `state` gives
it (`$state` defines ranks).

Take in a user's answer to a page's obligation in a stamped version. Where the widget's
`x-state` declares a `record` form, write that form: `chosen` on exactly the picked
`lf-option` elements you wrote, or the user's words as the body of a `needed`
`lf-draft`. Leave an option the user added out of the markup; the log keeps it. Where
the widget declares no form, as for an accepted suggestion or submitted playground
settings, the next stamp takes in the answer. A worker's report likewise stays provisional until the
stamped revision its `handling` asks for. When you work a decided suggestion into the
surrounding prose, keep its surviving branch and its ids.

## Make changes easy to find

Before handing over a changed page, compare it with the last version the user saw and
mark each significant addition, such as a `.tag` reading "new" beside a new section's
heading. Remove those marks in the next version you hand over.

## Keep the current page current

[SOUL.md](../SOUL.md), "Keep the page current and the record trustworthy", sets the
goal. Restructuring the page is an ordinary revision. Threads and user state follow ids
(`page-authoring.md`, "Stable anchors"), so a passage you keep keeps its id wherever it
moves, and moving it needs neither a suggestion nor `restated`.

When a revision removes a passage a thread quotes, the thread moves to the surviving
section, or is detached if the section is gone too. When you know where the subject
went, name the replacement passage (`threads.md`, "Preserve revised anchors").

A work list shows unfinished items. When an item of a plan, backlog or list of
problems is done, cut it down to its outcome and move it to the finished work,
collapsed after the open work, such as a `<details>` at the bottom or a separate tab.
A widget that tracks completion itself, such as a board or task list, keeps its
members. Remove material the current state replaces, such as a concluded run or a
superseded section; keep older material, collapsed, only where current work needs its
context. Keep deferred work in the list with enough context to resume it.

A decision the user answered and you have acted on becomes a record. Give its
`lf-options` group the `settled` attribute, which collapses it to the pick, and say
beside it what you did about the choice. Anything the choice sets in motion that
hasn't happened yet reads as decided, not under way. Keep the result and its evidence
in the current reading flow while the reader still needs them (`page-authoring.md`,
"Reading cost"); retire the superseded interaction as finished work. Pose anything
still worth asking as a new decision with new ids. Use `$restated` to withdraw the
decision and ask again.
Don't mark a decision `settled` until you have finished applying it, and keep a section
open while the user is still commenting there.

A playground whose submitted configuration you have applied becomes a record too.
Author each control at the chosen value, so the preview, Reset and the page's account
of the choice agree, and keep it and its evidence open beside what came of the choice,
since the user reads the record against that evidence. The user can still explore from
it. Keep the recorded configuration identifiable when working values change; a
changing preview shows the working configuration and is labeled accordingly.
Reset brings the preview back to the record.

The user reads threads to find out how their input was addressed. When a revision
resolves the question or completes the work discussed in an open thread, reply there
with the result and where the page shows it, so the thread is not left looking
unanswered.

Before handing the page back, check that its status, open to-dos and outstanding work
agree with what you tell the user.
