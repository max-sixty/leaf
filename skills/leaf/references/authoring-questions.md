# Asks and sign-off

Pose an ask for every decision waiting on the user. A recommendation leaves
that decision open until the user decides. `conversation-loop.md`, "Questions and
Tasks", owns the complete queue contract, including conversational questions and
requests for actions outside the page.

The user answers an ask from what is on screen when they reach it, often by pressing
`q` (`conversation-loop.md`, "Questions and Tasks"). Keep its question,
short shared premise, and evidence together with the answering control. Use `lf-ask`
to frame that material when it lives outside the answering widget: a question heading,
then context and evidence, then one answering widget. Backing detail and reproductions
of the current behavior follow the ask.

On a quick-answer page, open with the ask and put its backing in a disclosure
after it. The first viewport should show the objective, current state, and
what the user can do next together.

On a record or system page, put each ask in the part of the page it decides,
and let the page continue after it. An ask about one item of a list sits with
that item, and an ask that turns on a claim holds the claim and its evidence
rather than following them. Only an ask that turns on the whole record comes
last.

An `lf-ask` keeps the prose's width on every page, so its question, options and the
marker beside it stand with the paragraphs around it. An `lf-ask` that frames a
figure, such as a chart, image or table, around one option list sets the list beside
its premise and evidence wherever the context has room, so the question, the figure and
every option share the window. The reading column is too narrow for that, so give the
`lf-ask` the wide measure with `data-width="wide"`. A playground or another surface in
an `lf-ask` that uses every column it gets takes `data-width="available"` itself, so the
question and its premise keep the prose's width (`page-authoring.md`, "Bounds and
widths").

Write related, independently answerable asks in page order. A widget can carry its
own question and context, or an `lf-ask` can frame them around it. They remain visible
as one complete page. If a later ask depends on an earlier answer, publish it in the
next turn instead of authoring every possible branch.

Each ask contains its prompt, current typed answer and status. Widget state
owns the answer: a choice can supply a partial value before its Done completes
the ask, and an empty selection can be a completed answer. `lf-ask` adds
context around the answering widget; it does not create another ask or
replace the widget's identity. Standalone decision widgets also pose asks.

If a widget ask stops mattering before the user answers, retire its source in a
version or mark that source `restated` as `authoring-revisions.md` says. A to-do you
put on the user is work you ask them to do, such as trying a build, rather than a
question they answer (`conversation-loop.md`, "Questions and Tasks").

The user can finish each independently answerable proposal as they review it,
without leaving the material it rests on. Choosing which of several items to act
on poses one proposal per item whenever each item's answer would stand whatever
the others get. Give each its own answering widget with explicit accept and reject
choices, placed with that item's case. Use `lf-ask` when its heading and evidence
live outside that widget. Either choice completes the proposal's ask; leaving
it unanswered keeps it open. Where many proposals are clear-cut, one ask may
accept them together if it states, for each, what makes it clear-cut; the contested
ones keep their own asks. A selected set, answered in one `lf-options` with
`multiple`, is for items whose answers depend on each other, such as a limit on how
many or a combination that has to work together.

For an interface or behavior choice, make the relevant interaction work inside
each option so the user can try every alternative before choosing. For a choice
between arrangements, structures, or mechanisms that nothing can run yet, draw each
option inside it, all in one frame at one scale. Either way, hold everything except
the disputed treatment constant, and include the current or no-treatment case as a
neutral control. Put longer rationale or provenance in a disclosure after the
ask. The `lf-ask`, `lf-options`, and `lf-option` entries say how to word the
question and shape each option.

When the page exists for the user to choose among approaches, it is organized
around that choice. Its title and headings name the question and state what the
alternatives differ on without answering it, and your recommendation is advice,
stated as yours and marked on its option. Each alternative gets the same depth on
the same example, and a revision that adds detail adds it to each. An
alternative's costs and open questions belong in its case; how to build it, and
asks that arise only once it is chosen, wait for the user's pick, the one you
recommend included.

## Sign-off

A page whose approval unblocks work declares:

```html
<meta name="lf-review" content="sign-off">
```

An informational page omits it. The banner offers approval only on a stamped
version that declares it, so stamp a draft before requesting its sign-off. Each such
version gets an approval ask; that version's approval answers it, and Undo reopens
it. Approval requires every widget ask on the page and in its unresolved threads to
be answered or withdrawn. Widget asks in resolved threads and prose asks do not
block approval. Discussion alone leaves a widget's answer incomplete.
