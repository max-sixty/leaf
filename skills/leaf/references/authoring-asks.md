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

Every Ask is an `lf-ask`: `version check` refuses a widget that takes an answer
anywhere else. Write related, independently answerable Asks as separate `lf-ask`
elements in page order. They remain visible as one complete page. The user can press
`a` to reach the next open Ask and use its displayed `1`–`9` actions. If a later
Ask depends on an earlier answer, publish it in the next turn instead of authoring
every possible branch.

For an interface or behavior choice, make the relevant interaction work inside
each option so the user can try every alternative before choosing. For a choice
between arrangements, structures, or mechanisms that nothing can run yet, draw each
option inside it, all in one frame at one scale. Either way, hold everything except
the disputed treatment constant, and include the current or no-treatment case as a
neutral control. Put longer rationale or provenance in a disclosure after the
Ask. The `lf-ask`, `lf-options`, and `lf-option` entries say how to word the
question and shape each option.

A page whose approval unblocks work declares:

```html
<meta name="lf-review" content="sign-off">
```

An informational page omits it. The banner offers approval only on a stamped
version that declares it, and enables it once every Ask on the page and in its
threads is answered.
