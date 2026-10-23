# Decisions and approval

Put every decision waiting on the user on their list, On me, as a widget that records
the answer. Recommending an answer doesn't make the decision. `conversation-loop.md`,
"The On lists", covers everything the user is asked for, including questions in the
conversation and actions outside the page.

Make each decision understandable and answerable where On me takes the user, without
reading earlier content. Pressing `m` brings that decision to the top of the window,
leaving preceding prose out of view. So the decision opens with a heading that asks
its question, and holds the current state, the evidence that bears on the answer and
the answering control, inside the answering widget or an enclosing `lf-ask`. Compose
the explanation there first; backing detail goes after it.

On a quick-answer page, open with the decision and put its backing in a disclosure after
it; the first screen shows the goal, the current state and what the user can do next. On
a record or system page, put each decision in the part of the page it decides: a
decision about one entry goes with that entry, and one that turns on a claim contains
the claim and its evidence. Only a decision about the whole record comes last.

Keep the question, its evidence and the options on screen together. Where a table,
chart or playground inside the decision, or the pictures in its options, can't be read
at the prose's width, give that block, or the `lf-options`, its own `data-width`
(`page-layout.md`, "Bounds and widths").

Write decisions the user can answer independently in page order. If a later one depends
on an earlier answer, pose it in the next turn rather than writing every branch.

Let the user answer in the form the answer takes: a widget wherever it is a choice or
an edit, and an `lf-ask` holding no widget for an open question they answer in words.
Each widget puts one obligation on On me and records its answer. A choice can hold a
partial answer before the user presses Done, and an empty selection can be a complete
answer.

On me lists only what still needs the user. Retire a decision or question you
introduced once it stops mattering, by removing its widget in a new version or marking
it `restated` (`authoring-revisions.md`). A request the user made stays open until you
answer it or they withdraw it; deciding something else, however related, doesn't
answer it. To retire one yourself, say what changed to make it unnecessary. A to-do you
put on the user is work for them to do, such as trying a build, not a question.

Each option is a result the user can pick, so its title says what choosing it does to
the subject, keeping today's behavior included: “Generate shared types” and “Keep
handwritten types”, rather than “Accept” and “Not now”. A compact title can be the
whole option. The user should be able to compare the options down the group without
reading their prose, as through `small.tag` labels for the facts they weigh, such as
effort or risk. Add words only for a consequence that no title or label shows.

Let the user judge each option by its result rather than a description of it, on plans
and work-item lists too: an interaction they can try, a drawing of an arrangement or
mechanism in the same frame as the other options', a capture of today's interface
beside the change, with a fault marked where it goes wrong, a wording as it would
appear, or a code change's text or effect before and after. A change they would
neither see nor picture, such as a refactor, needs only words. Each option holds its
own picture, so nothing pairs it with another option's; a picture of both answers at
once, such as an `lf-shot` pair, belongs to the group. Vary only what the decision
changes, and show today in the option that keeps it, or above the options where none
does.

When the user decides several proposals independently, give each its own decision with
accept and reject options, beside that proposal's case. One decision can accept a batch
of clear-cut proposals if it says why each is clear-cut. Use `multiple` only when the
picks depend on each other, such as a limit on how many.

When the page exists to choose among approaches, its title and headings ask the
question without answering it. Give each alternative the same depth on the same
example, with its own costs and open questions, and mark your recommendation as advice.
How to build an alternative waits for the user's pick.

The `lf-ask`, `lf-options` and `lf-option` entries give their markup and presentation.

## Approval

Use `lf-approval` when the user must explicitly permit a stated action. Put the exact
subject and the evidence they need in its heading and prose:

```html
<lf-approval id="publish-report">
  <h2>Publish this report to the team workspace?</h2>
  <p>Publish the report shown above, including the revised cost estimate.</p>
</lf-approval>
```

The widget registers an ordinary obligation on On me. Approve records permission;
Undo approval takes it back and reopens the request. Other unanswered questions do
not block it. When permission depends on an earlier choice, resolve that choice
first, then present the resulting action for approval. Use `lf-options` when the
user needs to choose between outcomes, including an explicit rejection.

Approval belongs to the request with that id. Unrelated edits and page stamps keep
it approved. If the action or evidence changes enough to invalidate the permission,
explain the change and mark the widget `restated` before asking again
(`authoring-revisions.md`, "Honor user state"). Distinguish approved wording from
later edits to a draft. A new stamp neither requests nor renews approval.

Process approval through the ordinary widget-action workflow (`event-batches.md`).
It does not end the page or report that the approved work has been done.
