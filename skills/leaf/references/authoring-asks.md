# Asks and sign-off

The user answers an Ask from what is on screen when they reach it, and `a`
brings its heading to the top with everything above it out of view. So the
`lf-ask` holds what answering takes: its question heading, then the short shared
premise and the evidence that tells the alternatives apart, then the control.
Backing detail and reproductions of the current behavior follow the Ask.

On a quick-answer page, open with the Ask and put its backing in a disclosure
after it. The first viewport should show the objective, current state, and
available move together.

On a record or system page, put each Ask in the part of the page it decides,
and let the page continue after it. An Ask about one item of a list sits with
that item, and an Ask that turns on a claim holds the claim and its evidence
rather than following them. Only an Ask that turns on the whole record comes
last.

An Ask that holds a figure, such as a chart, image or table, and answers through
one option list sets the list beside its premise and evidence wherever the Ask
has the room, so the question, the figure and every option share the window. A
reading column is too narrow for that, so in a column give such an Ask the wide
measure with `data-width="wide"` (`page-authoring.md`, "Bounds and widths").

Every Ask is an `lf-ask`: `page check` refuses a widget that takes an answer
anywhere else. Write related, independently answerable Asks as separate `lf-ask`
elements in page order. They remain visible as one complete page. The user can press
`a` to reach the next open Ask and use its displayed `1`–`9` actions. If a later
Ask depends on an earlier answer, publish it in the next turn instead of authoring
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
