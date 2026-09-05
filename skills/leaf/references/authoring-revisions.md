# Live revisions and reader state

Read this before changing a page that has already been handed over, proposing a
rewrite, or using a reader-owned draft.

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
for pinned inputs. Inspect frozen thread content with
`leaf page state <page> --thread <id>`; change it through its conversation.

## Revisions and reader-owned words

Fresh content is authored directly. Rewrite prose the reader has already seen as
an `lf-suggestion`: `lf-old` carries the current markup verbatim, `lf-new` carries
the proposed replacement, and `resolves="<comment-id>"` connects a requested fix
to its thread. Introduce the first suggestion in prose so the reader knows its
new words can also receive comments.

A correction is not a proposal. Where the page got something wrong — a number, a
misread source, a unit — rejecting the fix would only restore the error, so the
reader has nothing to weigh: write the true thing straight and name the correction
in the version note. Suggest wording the reader could reasonably prefer as it
stands.

Use `lf-draft` for a passage whose wording belongs to the reader. Their submitted
words remain effective across revisions. A draft never sits inside a suggestion,
and a suggestion does not propose a widget's state.

## Honor reader state

The event log preserves reader choices, generated options, moves, edits, and
suggestion outcomes across revisions. Leave their authored inputs unchanged
unless the content needs revision. Copying projected state into markup is
optional; the page directory and standalone export already preserve it.

When incorporating a decided suggestion into surrounding prose, retain its
surviving branch and ids. A reader-generated option can become an ordinary
authored option under its owning group; retain its event-supplied id and words.
Its effective id can also anchor a separate clarification thread directly.

Worker reports remain provisional until adjudicated. Write the reported state
into markup to absorb a report, or mark its element `overruled` and explain why
in the version note. An unrelated revision may leave the report standing.

To deliberately replace state established by an action, put `restated` on the
rewritten element and explain why in the version note. Without `restated`, replay
restores the user's state and `version check` refuses a conflicting version.
Read the current projection before editing; an `undo` withdraws its named gesture.

## Make changes easy to find

Before handing over a changed page, compare it with the last version handed to
the reader. Make its material additions and changes clear in the page itself.
For example, options added for this turn can carry a final `<lf-chip>new this
turn</lf-chip>` in their chip row. The marker is temporary; remove it from the
next handed-over revision.

## Keep the current page current

Each active revision presents what is live now. Remove a concluded run or
superseded section instead of adding the next one beside it. Keep older material
only when the current work still needs its context; move only the needed
passages to a `Past work` section at the foot, inside a collapsed `<details>`
whose summary names what it contains. A passage whose id anchors an open thread
or holds a standing Ask survives with its id and words whatever else goes;
`version check` refuses a version that drops one. Mark a concluded `lf-options`
group `settled` when it retires inside a section that remains live.

Relocation is not revision: moving unchanged content needs neither a suggestion
nor `restated`. Keep an Ask live while it is being applied, and settle it
only after the work no longer revisits it. Keep a section live while the reader
is still commenting there.

When several workstreams are live at once, use one `lf-tabs`. Keep the shared
title and lede before it, and put the current workstream first: ordering makes it
the default for a reader with no saved panel or reading position, and a saved
panel or restored position takes precedence. Context an earlier run still owes
the current one goes in a collapsed `<details>` inside the relevant tab, with any
passage whose id anchors an open thread or holds a standing decision. Threads,
asks, versions, and sign-off still cover the whole page, so none of that runtime
chrome belongs inside a tab.
