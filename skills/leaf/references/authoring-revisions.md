# Live revisions and reader state

Read this before changing a page that has already been handed over, proposing a
rewrite, using a reader-owned draft, or carrying standing reader state into
markup.

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

Use `lf-draft` for a passage whose wording belongs to the reader. Carry their
submitted words verbatim into the next revision. A draft never sits inside a
suggestion, and a suggestion does not propose a widget's state.

## Honor reader state

The event log outranks authored markup. The server projects every standing action
and the browser replays that view onto later revisions, but the source must
eventually record the decision so the page reads correctly without the log:

- Mark every picked option `chosen`.
- Carry an option a reader wrote in the group's last cell into the group as an
  ordinary option, preserving each id key and its words from the `choose` action's
  `detail.additions` map. It is already a recorded choice, not a comment thread. If
  it needs discussion, carry it first and open a separate thread anchored to it.
- Replace an accepted suggestion with `lf-new`; replace a rejected one with
  `lf-old`, retaining ids on surviving passages.
- Carry a reader edit verbatim.
- Carry a worker report into markup, or mark the element `overruled` with the
  reason in the version note.

To deliberately replace state established by an action, put `restated` on the
rewritten element and explain why in the version note. Without `restated`, replay
restores the user's state and `version check` refuses a conflicting version. Do
not carry a gesture withdrawn by an `undo` event.

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
or holds a standing decision survives with its id and words whatever else goes;
`version check` refuses a version that drops one. Mark a concluded `lf-options`
group `settled` when it retires inside a section that remains live.

Relocation is not revision: moving unchanged content needs neither a suggestion
nor `restated`. Keep a decision live while it is being applied, and settle it
only after the work no longer revisits it. Keep a section live while the reader
is still commenting there.
