# One Question, answered in its section and shown on a board

The Questions model settles answer ownership. Shared editing from a board remains
an open view-to-owner contract. The earlier picker/board/section/record comparison
and discarded prototype informed this question; they do not describe the current
API.

## The need

A review page presents several proposals with their evidence. The user chooses
Next, Later or Drop beside each proposal, then reviews and rearranges those answers
on a board. Both surfaces must read and write the same canonical value.

## The settled owner

A Question contains its prompt, typed answer, lifecycle and source. A widget owns
its canonical answer state; `lf-ask` is an optional context adapter, alongside other
Question consumers. It owns neither another answer nor the Question's identity.

`readQuestions()` exposes `question.answer.value` directly. A board can already
read that collection, group answers by value, and open their sources through
`questionActions.open(question.id)`. It does not parse display labels or keep
another answer collection. Multiple selection and partial values need an explicit
board projection policy.

The source's registry declaration chooses the answer verb with `x-awaits.value`;
`x-awaits.answered` separately defines completion. Questions, Tasks and card order
remain different facts. The current contract lives in
`skills/leaf/references/module-authoring.md`, "Reading Questions and obligation
queues", and `skills/leaf/references/packages.md`. `questions.py` owns the server
inventory.

## What a board write still needs

Widget actions use `[owner widget, fold unit, verb]`. A source choice and an
independent board move occupy different coordinates, so admitting both stores two
facts for one intended answer. Reading a Question solves the projection; it does
not authorize a second view to send that source's command.

A declared view relation must identify the canonical owners a view shows and the
owner command each gesture invokes. The proposed name is `x-shows`; `x-views`
already names holders such as `lf-tabs` that show one member at a time. Implement
this only after trying composition through the existing public widget API and
identifying the admission guarantee it lacks.

The write contract must settle:

- How an authored relation identifies the source, including frozen-thread scope.
- How a card's column maps to the source's typed value without coupling core to
  `lf-options`, a particular verb, or labels.
- How admission proves the view may invoke that owner's declared command and
  records the actual source coordinate, optionally retaining the view as `via`.
- How markup validation refuses an independent board placement that contradicts
  the source value.
- Where card order belongs. It stays a board fact unless the source explicitly
  owns it; an answer projection alone does not imply order ownership.
- What write-in, partial, multiple-selection and withdrawn answers mean on the
  board, and how undo, refusal and revisions preserve the same value in both views.

The existing publisher supplies the source's state, and the existing append door
serializes admitted commands. The board consumes that publication and paints in
its own render region; it does not publish another semantic root or subscribe to
one widget in place of its own current state.

## Next

Build a focused section-and-board interaction once the view's command mapping and
admission guarantee are concrete. Keep the source widget's answer canonical,
exercise a drop and a section pick through the same coordinate, then prove undo,
refusal and revision behavior in both views. A new Answer primitive or a field on
`lf-ask` would undo the ownership decision already made.
