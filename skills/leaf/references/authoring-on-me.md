# On Me

On Me is the user's list of everything waiting on them. This file covers the questions
and choices you put there for the user to answer. A widget records a structured answer;
a thread message with `--obligation` asks for an answer in words. Recommending an answer
doesn't make the decision; the user does. `conversation-loop.md`, "The On lists", covers
the rest of the list, such as actions you ask the user to take, and the agent's own list.

## What a question holds

Make each question self-contained, so the user can decide from it alone, without
recalling the conversation or reading your notes. Say why the choice arises, what each
option leads to in a case the user can picture, and what each costs, including the one
you recommend, so they could reach your recommendation or turn it down for reasons the
question gives. Where you can't yet say what an option does, find out before you ask.
Beside each pull request, issue or commit the question mentions, say what that work is
or does, in words the user already uses: title its thread “Merging #431, the retry for
dropped uploads”, not “Merging #431”.

Each option is a result the user can pick, so its title says what choosing it does to
the subject, keeping today's behavior included: “Generate shared types” and “Keep
handwritten types”, rather than “Accept” and “Not now”. Write the titles in your own
voice, so “I” means you and “you” the user: “Keep your wording”, not “Keep my
wording”. Words an option quotes, such as a README sentence, stay as written.
Where the options differ only
in a value, such as how long captures are kept, say once above them what that value
costs, and each title can be the whole option. A card carries its name in `label`,
which On Me and threads show, and shows its title in its own HTML, a leading
`<strong>`, usually in the same words. The user should be able to compare the options
down the list without reading their prose, as through `small.lf-tag` chips for the facts
they weigh, such as effort or risk. Keep each chip to a word or two, such as “2 days”
rather than “about two days of work”, so a card's chips fit on one line beside its pick
mark. Where cards stand side by side (`across`), chips that wrap push that card's title
below its neighbours'. Add words only for a consequence that no title or chip shows.
Order the options by the subject, such as from today's behavior to the largest
change, and keep that one order wherever the question lists them, including a
comparison table and lettered names, so the user matches each option to its row by
position. The recommended option stays where that order puts it; `recommended` on it
marks your advice, which draws a green chip in the card's corner. Prose that recommends or
discusses an option names it by its title, as in
“I'd keep handwritten types”, never by its position or by a letter from an earlier
list, since the options' order can change after you write it.

Let the user judge each option by its result rather than a description of it, on plans
and work-item lists too: an interaction they can try, a drawing of an arrangement or
mechanism in the same frame as the other options', a capture of today's interface
beside the change, with a fault marked where it goes wrong, a wording as it would
appear, or a code change's text or effect before and after. A change they would
neither see nor picture, such as a refactor, needs only words. Each option holds its
own pictures, so nothing pairs them with another option's; a picture of both answers
at once, such as a before-and-after pair, stands in the question's group outside the
options. Where the result spans several captures, such as several surfaces or states,
line each capture up with its counterparts in the other options and name each surface
or state once, so the reader compares one at a time down the options. The default is
a table of captures in every option with the same columns in the same order
(`authoring-evidence.md`, "Source files and media"), which the theme draws with no
page CSS. Vary only what the choice changes, and show today in the option that keeps
it, or above the options where none does.

When the page exists to choose among approaches, its title and headings ask the
question without answering it. Give each alternative the same depth on the same
example, with its own open questions, and mark your recommendation as advice.
How to build an alternative waits for the user's pick.

## Asking and retiring

Let the user answer in the form the answer takes: a widget wherever it is a choice or
an edit, and a thread message with `--obligation` for a conversational answer. Any
widget whose registry entry declares `awaits` asks, a package's as well as the
bundled `lf-options`, which asks with no attribute until you mark it `settled`; a
question about content that asks nothing, such as a chart or a passage, goes in a
thread on it. Put the widget where the question arises: a question a thread raises, such as which way to do
what the user asked there, goes in your reply (`threads.md`, "Ask for a
pick"), and a decision the page records goes on the page.
Each widget that asks puts one question on On Me and records its answer. A choice can hold a
partial answer before the user presses Done, and an empty selection can be a complete
answer.

Ask each question when it costs the user least. One they can answer at a glance beside
the one it depends on, as in “Merge the retry fix? If so, delete its branch?”, usually
goes with it; one whose options would differ with an open answer usually waits for it.

When the user decides several proposals independently, give each its own options to
accept or reject it, beside that proposal's case. One choice can accept a batch
of clear-cut proposals if it says why each is clear-cut. Use `multiple` only when the
picks depend on each other, such as a limit on how many.

On Me lists only what still needs the user. Retire a question on the document
once it stops mattering, by removing its widget in a new version or setting the
attribute its `awaits.retired` names, such as `lf-options`' `settled`. Marking it
`restated` asks it again (`authoring-revisions.md`). For a question asked in a thread message,
resolve its thread as `conversation-loop.md`, "The On lists", describes. A request the user made stays open until you
answer it or they withdraw it; deciding something else, however related, doesn't
answer it. To retire one yourself, say what changed to make it unnecessary.

## On the page

Make each question answerable where On Me takes the user: pressing `m` selects the
whole question and brings its start to the top of the window, leaving earlier content
out of view. Write each question as a named group (an entry declaring `reading-role:
group`, such as `lf-group`) holding the question and its case, with an id and a
`label` that asks the question on its own, without leaning on the
prose around it. The group draws none of its label, so give it the heading the page
needs, as for any part of the page. The label's words are the question's words on On Me and in the
answer you receive; Leaf reads the region and its name from that markup, so
`page check` refuses a widget that asks where no label names its question, and names
one whose own label alone names it: `m` selects that widget alone, so a premise that
stands outside it is left out.

The group is the region `m` selects, so it holds everything the user judges: why the
question arises, the current state and its evidence, such as a capture of today or a
measured table. Shared evidence and its limits come before the answering control;
optional detail follows it. Where the page shows a finding and then asks about it,
the group holds the finding too and its label asks; a smaller group round only the heading
and options, after the evidence, leaves the evidence outside what `m` selects. Each
widget in the group that asks is its own question with its own answer.

```html
<lf-group id="material-q" label="Which material for the housing?">
  <h2>Which material for the housing?</h2>
  <p>Aluminium costs three times as much and halves the weight.</p>
  <table id="material-weights">
    …
  </table>
  <lf-options id="material">…</lf-options>
</lf-group>
```

On a quick-answer page, open with the question and put optional detail in a disclosure after
it; the first screen shows the goal, the current state and what the user can do next. On
a record or system page, put each question in the part of the page it decides: a
question about one entry goes with that entry, and one that turns on a claim contains
the claim and its evidence. Only a question about the whole record comes last.

Where evidence, option pictures or option cards set across need more than the prose's
width, set `data-width` on the block that holds them, such as the `lf-options`, figure
or playground, so the block takes the room while the question's words keep the
column's edge (`page-layout.md`, "Bounds and widths"). Size an option's picture
by the difference the user weighs between the options rather than by the capture: crop
it to the region that differs, and scale it down as far as that difference still reads,
so all the options fit the window together. A difference of size or extent, such as how
much of a thread a panel shows, reads at a scale where the words inside it don't, and a
picture that links its original keeps the detail a click away.

The instructions of the widget that asks for the pick give its markup and
presentation, including when to set its options side by side.

## One answer in its question and on a board

When the user needs answers beside their cases and together on a board, keep one
answer in both views. The instructions of the widget that draws the board say how to
compose those views.

## Permission

When the user must permit an action, ask for it as a question whose options keep
things as they are and take the action, so declining is an answer too. Put the exact
action and the evidence the user needs in the question's heading and prose:

```html
<lf-group
  id="publish-report-question"
  label="Publish this report to the team workspace?"
>
  <h2>Publish this report to the team workspace?</h2>
  <p>The report shown above, including the revised cost estimate.</p>
  <lf-options id="publish-report">
    <lf-option id="publish-report-keep" label="Keep it private"
      ><strong>Keep it private</strong></lf-option
    >
    <lf-option id="publish-report-publish" label="Publish it to the team workspace"
      ><strong>Publish it to the team workspace</strong></lf-option
    >
  </lf-options>
</lf-group>
```

Approval of an editable proposal applies to the submitted values, while later edits
remain a working copy. A playground records its complete values together on
submission; a draft edit and an options pick are independent answers. Choose a
composition that keeps the approved wording or settings distinct from subsequent edits.

The pick belongs to the `lf-options` and its id, `publish-report`, not to the `lf-group`
round it. Unrelated edits and page stamps keep it. If the action or evidence changes
enough to invalidate the permission, explain the change and mark the option the user
picked `restated`, which takes the pick back, before asking again
(`authoring-revisions.md`, "Honor user state"). A new
stamp neither requests nor renews permission, and recording it does not end the page
or report that the permitted work has been done.
