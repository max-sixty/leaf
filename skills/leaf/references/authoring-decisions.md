# Decisions

Put every decision waiting on the user on their list, On me. A widget records a
structured answer; a thread message with `--obligation` requests an answer in words. Recommending an answer doesn't make the decision. `conversation-loop.md`,
"The On lists", covers everything the user is asked for, including questions in the
conversation and actions outside the page.

For decisions on the document, make each understandable and answerable where On me takes the user, without
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
an edit, and a thread message with `--obligation` for a conversational answer. An
`lf-ask` holding no widget can also put an open question directly on the page.
Each widget puts one obligation on On me and records its answer. A choice can hold a
partial answer before the user presses Done, and an empty selection can be a complete
answer.

On me lists only what still needs the user. Retire a document decision or question
once it stops mattering, by removing its widget in a new version or marking it
`restated` (`authoring-revisions.md`). For a conversational obligation, use
`leaf task end` as "The On lists" describes. A request the user made stays open until you
answer it or they withdraw it; deciding something else, however related, doesn't
answer it. To retire one yourself, say what changed to make it unnecessary. A to-do you
put on the user is work for them to do, such as trying a build, not a question.

Each option is a result the user can pick, so its title says what choosing it does to
the subject, keeping today's behavior included: “Generate shared types” and “Keep
handwritten types”, rather than “Accept” and “Not now”. A compact title can be the
whole option. The user should be able to compare the options down the group without
reading their prose, as through `small.tag` labels for the facts they weigh, such as
effort or risk. Add words only for a consequence that no title or label shows.
Order the options by the subject, such as from today's behavior to the largest
change, and keep that one order wherever the decision lists them, including a
comparison table and lettered names, so the user matches each option to its row by
position. The recommended option stays where that order puts it; its `recommended`
label marks your advice. Prose that recommends or discusses an option names it by
its title, as in “I'd keep handwritten types”, never by its position or by a letter
from an earlier list, since the options' order can change after you write it.

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

## Permission

When the user must permit an action, ask for it as a decision whose options keep
things as they are and take the action, so declining is an answer too. Put the exact
action and the evidence the user needs in the `lf-ask` heading and prose:

```html
<lf-ask id="publish-report-decision">
  <h2>Publish this report to the team workspace?</h2>
  <p>The report shown above, including the revised cost estimate.</p>
  <lf-options id="publish-report" choose>
    <lf-option id="publish-report-keep"><strong>Keep it private</strong></lf-option>
    <lf-option id="publish-report-publish"
      ><strong>Publish it to the team workspace</strong></lf-option
    >
  </lf-options>
</lf-ask>
```

Other unanswered questions do not block it. When permission depends on an earlier
choice, resolve that choice first, then ask for the resulting action.

The pick belongs to the group with that id. Unrelated edits and page stamps keep it.
If the action or evidence changes enough to invalidate the permission, explain the
change and mark the group `restated` before asking again (`authoring-revisions.md`,
"Honor user state"). Distinguish approved wording from later edits to a draft. A new
stamp neither requests nor renews permission, and recording it does not end the page
or report that the permitted work has been done.
