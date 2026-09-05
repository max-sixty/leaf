# Asks and sign-off

Read this while authoring a new, unanswered ask or sign-off. Read the selected
registry entries for the exact widget contracts.

## Asks and sign-off

On a quick-answer page, open with the Ask. Put its short shared premise inside
the `lf-ask`, before the control, and put backing detail after it in a
disclosure. The first viewport should show the objective, current state, and
available move together.

On a record or system page, put each Ask where the reader has just read what it
turns on, and let the page continue after it. An Ask about one item of a list
follows that item, and an Ask that turns on a claim follows the claim rather
than the backing collapsed under it. Only an Ask that turns on the whole record
comes last.

Write related, independently answerable Asks as ordinary `lf-ask` elements
in page order. They remain visible as one complete page. The reader can press
`a` to reach the next open Ask and use its displayed `1`–`9` actions. If a later
Ask depends on an earlier answer, publish it in the next turn instead of authoring
every possible branch.

Each option carries its own title, one consequence, and the evidence needed to
choose it. When comparable facts help, show the same few facts across the
alternatives. For an interface or behavior choice, make the relevant interaction
work inside each option so the reader can try every alternative before choosing.
Hold everything except the disputed treatment constant, and include the current or
no-treatment case as a neutral control. Put longer rationale or provenance in a
disclosure after the Ask. Use a short option that points
elsewhere only to select among sections or work items that already exist
independently of the Ask; do not create separate sections to hold its
alternatives. Allow multiple picks only when several options may stand.

On the page the group's last cell is an option the reader writes, saying
`Another option`, so author the alternatives you actually mean and no catch-all
beside them: a `Something else` option takes a click where that cell takes the
answer. Submitting the cell creates and selects a real option. It reaches you as
the group's ordinary `choose` action, with `detail.additions` mapping the complete
set of reader-added option ids to their words. In a thread the reply box already owns
free-form words, so the group carries no add cell of its own.

The standing `choose` action answers the Ask immediately and preserves
generated options across revisions. If an added option needs clarification,
open a separate exact-section thread anchored to its event-supplied id. When
editing that option's markup, follow `authoring-revisions.md`'s reader-state rules.

An ask must name itself without context outside the ask. Begin `lf-ask` with
one ordinary heading, then include any introduction or evidence and the
actionable widget. That heading is the question: it stays in the document's
hierarchy, is available to selection and comments, names the Asks tray row, and
is where `a` / `A` arrives. The nested widget still owns the answer or request
lifecycle.

The author's preferred option may end its chip row with an ordinary tinted chip,
such as `<lf-chip tone="ok">recommended</lf-chip>`. Keep the reason in that option
as ordinary prose, such as `<em>My take: this is the safest rollout.</em>`. The chip
is advice; `chosen` alone records the reader's pick.

A page whose approval unblocks work declares:

```html
<meta name="lf-review" content="sign-off">
```

An informational page omits it. A `done` event approves the work and leaves the
page live while that work proceeds.
