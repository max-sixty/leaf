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
source's value with `leaf data set`. `leaf page state <page> <id>` shows one widget, with
its actions, asks and workflows, or one thread with its messages.

## Publish several authored files together

When the HTML and its modules must change together, prepare a separate directory
holding `index.html` and the whole `page/` tree, with any media it uses already in the
live page. Take the current files' digest with `leaf.publishing.authored_digest` (and
the files themselves with `leaf.publishing.authored_files`), then publish:

```sh
leaf page stamp <page> --from-directory <candidate> --if-source <digest> --text 'Updated the page'
```

The stamp refuses if the page's files changed since you took the digest, and keeps the
old files if the new ones fail the check. It doesn't touch the event log or external
data.

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
in effect across revisions. The `<pre>` holds the exact Markdown, including leading
blank lines, indentation and trailing whitespace; follow the `lf-draft` registry entry
for its HTML.

## Honor user state

The event log keeps the user's choices, added options, edits and suggestion outcomes,
so don't copy them into the markup. Revise your own markup when the content needs it,
keeping the meaning of the user's decisions. To withdraw a decision, follow the
registry's `$restated`.

When you move cards in a board, place each card in the column and rank `state` gives
it (`$state` defines ranks).

Take in a user's answer to a page ask in a stamped version. Where the widget's
`x-state` declares a `record` form, write that form: `chosen` on exactly the picked
`lf-option` elements you wrote, or the user's words as the body of a `needed`
`lf-draft`. Leave an option the user added out of the markup; the log keeps it. Where
the widget declares no form, as for an accepted suggestion or submitted playground
settings, the next stamp takes in the answer. Until then the answer waits on you, as its
delivered `handling` says. A worker's report likewise stays provisional until the
stamped revision its `handling` asks for. When you work a decided suggestion into the
surrounding prose, keep its surviving branch and its ids.

## Make changes easy to find

Before handing over a changed page, compare it with the last version the user saw and
mark each significant addition, such as a `.tag` reading "new" beside a new section's
heading. Remove those marks in the next version you hand over.

## Keep the current page current

The main skill's "Keep the user current" sets the goal: the page the user returns to is
the one you would write today. Restructuring the page is an ordinary revision; write
`index.html` whole rather than as a series of edits. Threads and user state follow ids
(`page-authoring.md`, "Stable anchors"), so a passage you keep keeps its id wherever it
moves, and moving it needs neither a suggestion nor `restated`.

When a revision removes a passage a thread quotes, the thread moves to the surviving
section, or is detached if the section is gone too. When you know where the subject
went, name the replacement passage (`threads.md`, "Preserve revised anchors").

A list of work holds what is still to do. When an item of a plan, backlog or list of
problems is done, cut it down to its outcome and move it to the finished work,
collapsed after the open work, such as a `<details>` at the foot or a tab of its own.
A widget that tracks completion itself, such as a board or task list, keeps its
members. Remove material the current state replaces, such as a concluded run or a
superseded section; keep older material, collapsed, only where current work needs its
context. Keep deferred work in the list with enough context to resume it.

An ask the user answered and you have acted on is finished work too. Move it whole to
the finished work, give its `lf-options` group the `settled` attribute, which collapses
it to the pick, and say beside it what came of the choice. Pose anything still worth
asking as a new ask with new ids. Use `$restated` to withdraw the decision and ask
again. Keep an ask open while you are still applying it, and keep a section open while
the user is still commenting there.

Before handing the page back, check that its status, open to-dos and outstanding work
agree with what you tell the user.
