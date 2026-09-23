# Asks and sign-off

On a quick-answer page, open with the Ask. Put its short shared premise inside
the `lf-ask`, before the control, and put backing detail after it in a
disclosure. The first viewport should show the objective, current state, and
available move together.

On a record or system page, put each Ask where the user has just read what it
turns on, and let the page continue after it. An Ask about one item of a list
follows that item, and an Ask that turns on a claim follows the claim rather
than the backing collapsed under it. Only an Ask that turns on the whole record
comes last.

Write related, independently answerable Asks as ordinary `lf-ask` elements
in page order. They remain visible as one complete page. The user can press
`a` to reach the next open Ask and use its displayed `1`–`9` actions. If a later
Ask depends on an earlier answer, publish it in the next turn instead of authoring
every possible branch.

Each option carries its own title, one consequence, and the evidence needed to
choose it. When comparable facts help, show the same few facts across the
alternatives. For an interface or behavior choice, make the relevant interaction
work inside each option so the user can try every alternative before choosing.
Hold everything except the disputed treatment constant, and include the current or
no-treatment case as a neutral control. Put longer rationale or provenance in a
disclosure after the Ask. Use a short option that points
elsewhere only to select among sections or work items that already exist
independently of the Ask; do not create separate sections to hold its
alternatives.

`multiple` asks whether two options can both hold, not whether the user
usually picks one. A group without it enforces exclusivity by discarding: the
second press starts from an empty set, and the announcement names only the new
pick, so nothing tells the user their first answer is gone. Author the
exclusive group only where the options rule each other out; where a set is
answerable — work to start, checks to run, risks to accept — allow it.

On the page the group ends with an `Another option` cell the user writes in
(the `lf-options` entry describes it), so author the alternatives you actually
mean and no catch-all beside them: a `Something else` option takes a click where
that cell takes the answer. If an added option needs clarification, open a
separate exact-section thread anchored to its event-supplied id. When editing that
option's markup, follow `authoring-revisions.md`'s user-state rules.

Begin each `lf-ask` with one ordinary heading that states the question, so the Ask
names itself without context outside it; the `lf-ask` entry says what else that
heading does.

A page whose approval unblocks work declares:

```html
<meta name="lf-review" content="sign-off">
```

An informational page omits it. The banner offers approval only on a stamped
version that declares it, and enables it once every Ask on the page and in its
threads is answered.
