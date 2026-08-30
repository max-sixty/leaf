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
answer. In a thread the reply box is already that cell, so the group carries
none of its own.

Writing there is the reader dealing with the question, so the group stops being
one of the page's open asks and the ball is yours. Nothing is recorded by it:
the group still holds no new pick. Answer what they wrote in the authored page:
carry their words in as another option and mark the pick it settled. If the reader
explicitly rejects every option, settle the group without a pick. This thread
takes no agent reply; if the revision needs an answer first, open a separate
exact-section thread on the same Decision. Only authored state in a later version can
answer an originating open Decision, or change its declared answer when the Decision was
already answered. Reader actions before or after the proposal do not substitute
for that revision, and an unrelated version cannot close it.

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
