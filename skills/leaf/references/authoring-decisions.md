# Decisions and sign-off

Put every decision waiting on the user on their list, On me, as a widget that records
the answer. Recommending an answer doesn't make the decision. `conversation-loop.md`,
"The On lists", covers everything the user is asked for, including questions in the
conversation and actions outside the page.

Make each decision understandable and answerable where On me takes the user, without
reading earlier content. Pressing `m` brings that decision to the top of the window,
leaving preceding prose out of view. Put the question, the current
state, the evidence that bears on the answer and the answering control inside the
answering widget or an enclosing `lf-ask`. Compose the explanation there first;
backing detail goes after it.

On a quick-answer page, open with the decision and put its backing in a disclosure after
it; the first screen shows the goal, the current state and what the user can do next. On
a record or system page, put each decision in the part of the page it decides: a
decision about one entry goes with that entry, and one that turns on a claim contains
the claim and its evidence. Only a decision about the whole record comes last.

An `lf-ask` keeps the prose's width. When it frames a figure above its options, the
options sit side by side under the figure, so question, figure and options share the
window. Give a table, chart, playground or other wide surface inside an `lf-ask` its
own `data-width`, such as `data-width="available"` for a playground that uses every
column it gets (`page-layout.md`, "Bounds and widths"). A page whose subject is that
surface is a workspace instead (`page-authoring.md`, "Composing a page").

Write decisions the user can answer independently in page order. If a later one depends
on an earlier answer, pose it in the next turn rather than writing every branch.

The answering widget holds the item's answer and status. A choice can record a partial
answer before the user presses Done, and an empty selection can be a complete answer. A
decision widget on its own puts an item on On me; an `lf-ask` around it adds context,
not a second item. An `lf-ask` holding no widget is a question the user answers in
words: on the page, by commenting on it; in a thread message, by their next message
there. Use it for an open question no widget can record, and a widget wherever the
answer is a choice or an edit.

Retire decisions and questions you introduced when they stop mattering. Keep unanswered
user requests distinct from settled decisions. A request remains open until answered or
withdrawn, or until you explicitly retire it and explain why changed circumstances make
it unnecessary. Applying an independent decision does not itself answer or retire the
request. Retire one by removing its widget in a new version or marking it `restated`
(`authoring-revisions.md`). A to-do you put on the user is work for them to do, such as
trying a build, not a question.

When the user chooses which of several proposals to act on, and no proposal's answer
depends on the others, give each proposal its own decision with explicit accept and
reject choices, placed with that proposal's case, so the user can answer each as they
review it. Either choice answers it. When many proposals are clear-cut, one decision can
accept them together if it says for each why it is clear-cut; contested proposals keep
their own decisions. Use one `lf-options` with `multiple` only when the answers depend
on each other, such as a limit on how many.

State what choosing each option does to the subject in its label or title, including
the choice to keep today's behavior: “Generate shared types” or “Keep handwritten
types”. Accepting or rejecting your advice is the gesture; name the result it records.
A compact label can be the whole option. Add words for a
consequence or tradeoff the decision has not yet shown. Show the result inside the
decision, following `page-authoring.md`, "Show the subject". This holds on plans and
work-item lists too:

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
- For a change the user would neither see nor need to picture, such as a refactor
  judged by its reasons and cost, give what it gives them in words.

Vary only the treatment in question, and show today's version, or no change, beside them
as a neutral baseline. Put longer rationale in a disclosure after the decision. The
`lf-ask`, `lf-options` and `lf-option` entries give their markup and presentation.

When the page exists for the user to choose among approaches, organize it around that
choice. The title and headings name the question and what the alternatives differ on,
without answering it. Mark your recommendation on its option as your advice. Give each
alternative the same depth on the same example. An alternative's costs and open
questions belong in its case. How to build an alternative, and questions that arise
only once it is chosen, wait for the user's pick, the one you recommend included.

## Sign-off

A page whose approval unblocks work declares:

```html
<meta name="lf-review" content="sign-off" />
```

Leaf offers approval only on a stamped version that declares it, so stamp a draft before
asking for sign-off. Each such version puts an approval item on On me, which approving
the version answers and Undo reopens. Later widget edits do not withdraw that approval
or approve the new wording. For editable content, distinguish the approved wording from
the current draft. Approval needs every widget's item on the page and in its unresolved
threads answered or withdrawn, a question in an `lf-ask` included; items in resolved
threads don't block it.
