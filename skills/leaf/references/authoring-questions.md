# Questions and sign-off

Pose a Question for every decision waiting on the user. A recommendation leaves
that decision open until the user decides.

The user answers a Question from what is on screen when they reach it. The `q`
key takes them to its answering widget and context. Keep its question,
short shared premise, and evidence together with the answering control. Use `lf-ask`
to frame that material when it lives outside the answering widget: a question heading,
then context and evidence, then one answering widget. Backing detail and reproductions
of the current behavior follow the Question.

On a quick-answer page, open with the Question and put its backing in a disclosure
after it. The first viewport should show the objective, current state, and
available move together.

On a record or system page, put each Question in the part of the page it decides,
and let the page continue after it. A Question about one item of a list sits with
that item, and a Question that turns on a claim holds the claim and its evidence
rather than following them. Only a Question that turns on the whole record comes
last.

An `lf-ask` keeps the prose's width on every page, a wide one included, so its
question, options and the marker beside it stand with the paragraphs around it. An
`lf-ask` that frames a figure, such as a chart, image or table, around one option
list sets the list beside its premise and evidence wherever the context has room, so
the question, the figure and every option share the window. The reading column is too
narrow for that, so give the `lf-ask` the wide measure with `data-width="wide"`, on a
column page and a wide one alike. An `lf-ask` holding a playground or another surface that
uses every column it gets takes `data-width="available"` (`page-authoring.md`,
"Bounds and widths").

Write related, independently answerable Questions in page order. A widget can carry its
own question and context, or an `lf-ask` can frame them around it. They remain visible
as one complete page. The user can press `q` to reach the next thing waiting on them
(an open Question, a thread whose question is theirs, a task you put on them, or a move
whose reply failed and needs sending again) and use a Question's displayed `1`–`9`
actions. If a later Question depends on an earlier answer, publish it in the next turn
instead of authoring every possible branch.

Each Question contains its prompt, current typed answer and status. Widget state
owns the answer: a choice can supply a partial value before its Done completes
the Question, and an empty selection can be a completed answer. `lf-ask` adds
context around the answering widget; it does not create another Question or
replace the widget's identity. Standalone decision widgets also pose Questions.

`leaf page state` lists Questions separately from explicit `tasks`. A widget's
Question is identified by `widget:<widget-id>`; a prose question in a thread by
`reply:<message-id>`. If a widget Question stops mattering before the user answers,
retire its source in a version or mark that source `restated` as
`authoring-revisions.md` says. A task is work you ask the user to do, such as trying
a build, rather than a question they answer (`conversation-loop.md`, "Tasks on
the user").

The user can finish each independently answerable proposal as they review it.
Give each its own answering widget with explicit accept and reject choices.
Use `lf-ask` when its heading and evidence live outside that widget. Either choice
completes the proposal's Question; leaving it unanswered keeps it open. The
`lf-options` entry owns questions whose answer is a selected set.

For an interface or behavior choice, make the relevant interaction work inside
each option so the user can try every alternative before choosing. For a choice
between arrangements, structures, or mechanisms that nothing can run yet, draw each
option inside it, all in one frame at one scale. Either way, hold everything except
the disputed treatment constant, and include the current or no-treatment case as a
neutral control. Put longer rationale or provenance in a disclosure after the
Question. The `lf-ask`, `lf-options`, and `lf-option` entries say how to word the
question and shape each option.

When the page exists for the user to choose among approaches, it is organized
around that choice. Its title and headings name the question and state what the
alternatives differ on without answering it, and your recommendation is advice,
stated as yours and marked on its option. Each alternative gets the same depth on
the same example, and a revision that adds detail adds it to each. An
alternative's costs and open questions belong in its case; how to build it, and
Questions that arise only once it is chosen, wait for the user's pick, the one you
recommend included.

A page whose approval unblocks work declares:

```html
<meta name="lf-review" content="sign-off">
```

An informational page omits it. The banner offers approval only on a stamped
version that declares it. Approval requires every widget Question on the page
and in its unresolved threads to be answered or withdrawn. Widget Questions in
resolved threads and prose Questions do not block approval. Discussion alone
leaves a widget's answer incomplete.
