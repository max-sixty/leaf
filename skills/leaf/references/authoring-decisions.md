# Decisions and sign-off

Read this while authoring a new, unanswered ask or sign-off. Read the selected
registry entries for the exact widget contracts.

## Asks and sign-off

Put each alternative's title, case, and evidence inside the option itself. When
whole page sections are the alternatives, use short option labels that point at
those sections. Allow multiple picks only when several options may stand.

On the page the group's last cell is an option the reader writes, saying
`Another option`, so author the alternatives you actually mean and no catch-all
beside them: a `Something else` option takes a click where that cell takes the
answer. Submitting the cell creates and selects a real option. It reaches you as
the group's ordinary `choose` action, with `detail.additions` mapping the complete
set of reader-added option ids to their words. In a thread the reply box already owns
free-form words, so the group carries no add cell of its own.

Carry each added option into the next authored version with its event-supplied id
and words, and mark the standing pick `chosen`. That is when the generated option
becomes an ordinary authored option. If you need clarification, first carry it,
then open a separate exact-section thread anchored to that option; do not turn the
add gesture itself into a conversation. The standing `choose` action answers the live
Decision immediately; the later authored version makes that answer self-contained
without the log. An unrelated version cannot erase it.

An ask must name itself without context outside the ask. Begin `lf-decision` with
one ordinary heading, then include any introduction or evidence and the
actionable widget. That heading is the question: it stays in the document's
hierarchy, is available to selection and comments, names the Asks tray row, and
is where `a` / `A` arrives. The nested widget still owns the answer or request
lifecycle.

Keep the author's preference in the option it belongs to as ordinary prose:
`<em>My take: this is the safest rollout.</em>` is enough. Say why when the reason
matters. Do not encode the preference as a badge, tint, ring, or option state; it
is an argument for the reader to weigh, not a decision the reader has made.

A page whose approval unblocks work declares:

```html
<meta name="lf-review" content="sign-off">
```

An informational page omits it. A `done` event approves the work and leaves the
page live while that work proceeds.
