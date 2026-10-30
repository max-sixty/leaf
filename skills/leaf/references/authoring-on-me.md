# On me

On me is the user's list of everything waiting on them. This file covers the questions
and choices you put there for the user to answer. A widget records a structured answer;
a thread message with `--obligation` asks for an answer in words. Recommending an answer
doesn't make the decision; the user does. `conversation-loop.md`, "The On lists", covers
the rest of the list, such as to-dos you give the user, and the agent's own list.

## What a question holds

Make each question self-contained, so the user can decide from it alone, without
recalling the conversation or reading your notes. Say why the choice arises, what each
option leads to in a case the user can picture, and what each costs, including the one
you recommend, so they could reach your recommendation or turn it down for reasons the
question gives. Where you can't yet say what an option does, find out before you ask.

Each option is a result the user can pick, so its title says what choosing it does to
the subject, keeping today's behavior included: “Generate shared types” and “Keep
handwritten types”, rather than “Accept” and “Not now”. Where the options differ only
in a value, such as how long captures are kept, say once above them what that value
costs, and each title can be the whole option. The user should be able to compare the
options down the group without reading their prose, as through `small.tag` labels for
the facts they weigh, such as effort or risk. Keep each label to a word or two, such as
“2 days” rather than “about two days of work”, so a card's labels fit on one line
beside its pick mark. Where cards stand side by side, labels that wrap push that card's
title below its neighbours'. Add words only for a consequence that no title or label
shows.
Order the options by the subject, such as from today's behavior to the largest
change, and keep that one order wherever the question lists them, including a
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
own pictures, so nothing pairs them with another option's; a picture of both answers
at once, such as an `lf-shot` pair, belongs to the group. Where the result spans
several captures, such as several surfaces or states, line each capture up with its
counterparts in the other options and name each surface or state once, so the reader
compares one at a time down the options. The default is a table of captures in every
option with the same columns in the same order (`authoring-evidence.md`, "Source files
and media"), which the theme draws with no page CSS. Vary only what
the choice changes, and show today in the option that keeps it, or above the options
where none does.

When the page exists to choose among approaches, its title and headings ask the
question without answering it. Give each alternative the same depth on the same
example, with its own open questions, and mark your recommendation as advice.
How to build an alternative waits for the user's pick.

## Asking and retiring

Let the user answer in the form the answer takes: a widget wherever it is a choice or
an edit, and a thread message with `--obligation` for a conversational answer.
Each widget that asks puts one question on On me and records its answer. A choice can hold a
partial answer before the user presses Done, and an empty selection can be a complete
answer.

Write questions the user can answer independently in page order. If a later one depends
on an earlier answer, pose it in the next turn rather than writing every branch.

When the user decides several proposals independently, give each its own options to
accept or reject it, beside that proposal's case. One choice can accept a batch
of clear-cut proposals if it says why each is clear-cut. Use `multiple` only when the
picks depend on each other, such as a limit on how many.

On me lists only what still needs the user. Retire a question on the document
once it stops mattering, by removing its widget in a new version or marking it
`restated` (`authoring-revisions.md`). For a question asked in a thread message, use
`leaf task end` as "The On lists" describes. A request the user made stays open until you
answer it or they withdraw it; deciding something else, however related, doesn't
answer it. To retire one yourself, say what changed to make it unnecessary. A to-do you
put on the user is work for them to do, such as trying a build, not a question.

## On the page

Make each question answerable where On me takes the user: pressing `m` brings its
heading to the top of the window, leaving earlier content out of view. Inside the
answering widget or an enclosing `lf-ask`, build the question around the material the
user judges: a heading that asks it, why it arises, the current state and its evidence.
Shared evidence and its limits come before the answering control; optional detail
follows it.

On a quick-answer page, open with the question and put optional detail in a disclosure after
it; the first screen shows the goal, the current state and what the user can do next. On
a record or system page, put each question in the part of the page it decides: a
question about one entry goes with that entry, and one that turns on a claim contains
the claim and its evidence. Only a question about the whole record comes last.

Where a table, chart or playground inside the question, or the pictures in
its options, can't be read at the prose's width, give that block, or the `lf-options`,
its own `data-width` (`page-layout.md`, "Bounds and widths"). Size an option's picture
by the difference the user weighs between the options rather than by the capture: crop
it to the region that differs, and scale it down as far as that difference still reads,
so all the options fit the window together. A difference of size or extent, such as how
much of a thread a panel shows, reads at a scale where the words inside it don't, and a
picture that links its original keeps the detail a click away.

The `lf-ask`, `lf-options` and `lf-option` entries give their markup and presentation.

## One answer in its section and on a board

When the user answers proposals beside their cases and also needs every answer in one
view to compare or rearrange, keep each answer in its section's `lf-options` and add a
board whose cards show those answers, rather than asking twice. Give each option a
`value` naming the answer it gives, in words every section shares, and the board one
column per value with that `value`, plus one column without a value for proposals not
yet answered or answered in the user's own words. Each card's `shows` names its
section's group, and the card appears in the column matching that group's selected value:

```html
<lf-options id="rail-choice" choose>
  <lf-option id="rail-next" value="next">Next</lf-option>
  <lf-option id="rail-later" value="later">Later</lf-option>
</lf-options>
<!-- … the other proposals' sections … -->
<lf-board id="plan">
  <lf-column id="plan-open" label="Undecided">
    <lf-card id="plan-rail" shows="rail-choice"><strong>Keep the rail</strong></lf-card>
  </lf-column>
  <lf-column id="plan-next" label="Next" value="next"></lf-column>
  <lf-column id="plan-later" label="Later" value="later"></lf-column>
</lf-board>
```

A drop on the board answers through the group, so the page holds one answer, which
Undo and `restated` take back in both views. When a revision writes the user's pick
into the group, move the card to that pick's column too. A card that shows an answer
keeps the order you wrote it in; where the order within a column is itself the user's
call, ask for it as its own question.

## Permission

When the user must permit an action, ask for it as a question whose options keep
things as they are and take the action, so declining is an answer too. Put the exact
action and the evidence the user needs in the `lf-ask` heading and prose:

```html
<lf-ask id="publish-report-question">
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
