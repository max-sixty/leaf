# Asks and sign-off

Pose an ask for every decision waiting on the user. Recommending an answer doesn't
make the decision. `conversation-loop.md`, "The On lists", covers everything the user
is asked for, including questions in the conversation and actions outside the page.

The user answers an ask from what is on screen when they reach it, often by pressing
`m`. Keep the question, a short premise and the evidence next to the answering control.
When that material sits outside the answering widget, frame it with an `lf-ask`: a
question heading, its context and evidence, and one answering widget. Backing detail
goes after the ask.

On a quick-answer page, open with the ask and put its backing in a disclosure after it;
the first screen shows the goal, the current state and what the user can do next. On a
record or system page, put each ask in the part of the page it decides: an ask about
one item goes with that item, and an ask that turns on a claim contains the claim and
its evidence. Only an ask about the whole record comes last.

An `lf-ask` keeps the prose's width. When it frames a figure above its options, the
options sit side by side under the figure, so question, figure and options share the
window. Give a table, chart, playground or other wide surface inside an `lf-ask` its
own `data-width`, such as `data-width="available"` for a playground that uses every
column it gets (`page-layout.md`, "Bounds and widths").

Write asks the user can answer independently in page order. If a later ask depends on
an earlier answer, pose it in the next turn rather than writing every branch.

The answering widget holds the ask's answer and status. A choice can record a partial
answer before the user presses Done, and an empty selection can be a complete answer.
A decision widget on its own also poses an ask; an `lf-ask` around it adds context, not
a second ask.

If an ask stops mattering before the user answers, remove it in a new version or mark
it `restated` (`authoring-revisions.md`). A to-do you put on the user is work for them
to do, such as trying a build, not a question.

When the user chooses which of several items to act on, and no item's answer depends on
the others, give each item its own ask with explicit accept and reject choices, placed
with that item's case, so the user can answer each as they review it. Either choice
answers the ask. When many items are clear-cut, one ask can accept them together if it
says for each why it is clear-cut; contested items keep their own asks. Use one
`lf-options` with `multiple` only when the answers depend on each other, such as a limit
on how many.

Each option shows, inside the ask, what choosing it would give the user, drawn the way
`page-authoring.md`, "Show the subject", shows that kind of thing. This holds on plans
and work-item lists too:

- For an interface or behavior choice, make the interaction work inside each option so
  the user can try every alternative.
- For arrangements or mechanisms nothing can run yet, draw each option, all in one
  frame at one scale.
- For a proposal to accept or reject, show today beside the change, in one frame or in
  the accepting option. A visible fault is a capture marked where it goes wrong, beside
  a drawing or demonstration of the fix.
- For a code or data change, show the text before and after when the text is what the
  user judges; otherwise show the change's effect before and after, with the code
  beside it.
- For a choice of wording, show each wording as it would appear.

Vary only the treatment in question, and show today's version, or no change, beside
them as a neutral baseline. Put longer rationale in a disclosure after the ask. The `lf-ask`,
`lf-options` and `lf-option` entries say how to word the question and options.

When the page exists for the user to choose among approaches, organize it around that
choice. The title and headings name the question and what the alternatives differ on,
without answering it. Mark your recommendation on its option as your advice. Give each
alternative the same depth on the same example. An alternative's costs and open
questions belong in its case. How to build an alternative, and questions that arise
only once it is chosen, wait for the user's pick, the one you recommend included.

## Sign-off

A page whose approval unblocks work declares:

```html
<meta name="lf-review" content="sign-off">
```

Leaf offers approval only on a stamped version that declares it, so stamp a draft
before asking for sign-off. Each such version gets an approval ask, which approving the
version answers and Undo reopens. Approval needs every widget ask on the page and in its
unresolved threads answered or withdrawn; asks in resolved threads and asks written only
in prose don't block it.
