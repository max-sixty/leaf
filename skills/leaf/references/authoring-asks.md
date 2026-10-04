# Asks and sign-off

The user answers an Ask from what is on screen when they reach it, and `a`
brings its start to the top with everything above it out of view. Keep its question,
short shared premise, and evidence together with the answering control. Use `lf-ask`
to frame that material when it lives outside the answering widget: a question heading,
then context and evidence, then one answering widget. Backing detail and reproductions
of the current behavior follow the Ask.

On a quick-answer page, open with the Ask and put its backing in a disclosure
after it. The first viewport should show the objective, current state, and
available move together.

On a record or system page, put each Ask in the part of the page it decides,
and let the page continue after it. An Ask about one item of a list sits with
that item, and an Ask that turns on a claim holds the claim and its evidence
rather than following them. Only an Ask that turns on the whole record comes
last.

Write related, independently answerable Asks in page order. A widget can carry its
own question and context, or an `lf-ask` can frame them around it. They remain visible
as one complete page. The user can press `a` to reach the next thing waiting on them
(an open Ask, a thread whose question is theirs, or a move whose reply failed and
needs sending again) and use an Ask's displayed `1`–`9` actions. If a later Ask depends on an earlier answer, publish it in
the next turn instead of authoring
every possible branch.

For independent proposals, make progress visible as each one is decided: give
each proposal its own `lf-ask` with explicit accept and reject choices. Either
choice completes that Ask; leaving it unanswered keeps it open. A shared
`multiple` group fits a question whose answer is a selected set.

For an interface or behavior choice, make the relevant interaction work inside
each option so the user can try every alternative before choosing. For a choice
between arrangements, structures, or mechanisms that nothing can run yet, draw each
option inside it, all in one frame at one scale. Either way, hold everything except
the disputed treatment constant, and include the current or no-treatment case as a
neutral control. Put longer rationale or provenance in a disclosure after the
Ask. The `lf-ask`, `lf-options`, and `lf-option` entries say how to word the
question and shape each option.

When the page exists for the user to choose among approaches, it is organized
around that choice. Its title and headings name the question and state what the
alternatives differ on without answering it, and your recommendation is advice,
stated as yours and marked on its option. Each alternative gets the same depth on
the same example, and a revision that adds detail adds it to each. An
alternative's costs and open questions belong in its case; how to build it, and
Asks that arise only once it is chosen, wait for the user's pick, the one you
recommend included.

A page whose approval unblocks work declares:

```html
<meta name="lf-review" content="sign-off">
```

An informational page omits it. The banner offers approval only on a stamped
version that declares it, and enables it once every Ask on the page and in its
threads is answered.
