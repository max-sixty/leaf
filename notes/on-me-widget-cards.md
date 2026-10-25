# Widgets drawing their own On me cards

Parked on 24 October 2026. On me's card for a widget obligation (`onItemCard` in
`browser/runtime/floating-panel.js`) is the panel's: it copies each of the widget's
`decision: true` command controls onto a plain button, and a press clicks the real
control (`choicesOf`, `browser/runtime/obligations/view.js`). So a widget decides
only which controls are copied, and a widget whose DOM isn't drawn, such as one in
an unopened thread message, gets only Discuss and Show. Max asked for a widget to
decide how its obligation shows there, and chose to prototype design C below.

## Designs compared

- **A. Keep deriving.** The panel draws a message-borne widget by drawing its whole
  message, as it already does for a question asked in words.
- **B. A card function on the widget class**, beside `answerWords`, returning the
  card body's template from the obligation and state, with its own dispatch.
- **C. The widget draws itself in the card:** a second live element with the
  source's id, bound to the same state, in a compact form the widget's render and
  theme choose.

## What the prototype of C found

Branch `on-me-card-prototype` (commit `12f469d45`) implements C for `lf-options`
and `lf-approval`; `lf-ask` has no module, so its card holds a reply box. A widget
opts in with `static seats = ["card"]` and styles `[data-lf-seat="card"]`.

- **Gestures work.** A press in the card admits the same action as on the page;
  Undo and `z` work from either place; a widget in an unopened thread message
  becomes answerable.
- **Shared id broke two shared mechanisms.** Presentation regions are keyed by
  widget id, so the copy took over the page widget's region and deleted it when
  the card closed; the prototype keys a copy's regions `widget:<id>:<kind>@<seat>`.
  Copying from the live element drew a user-added option twice; the copy now
  comes from authored markup.
- **Lookups by id change meaning.** For a page widget the page's element wins.
  For a widget in an unopened thread message the copy is the only element with
  that id, so the 36 `elementById` call sites resolve into the card while it is
  open. axe reports `duplicate-id`.
- **Local state diverges.** Digit keys number a user-added option differently in
  the card; `lf-draft`'s editor and `lf-playground`'s unsent values would diverge
  the same way. Per-record obligations (`lf-visual-review`) can't be seated.
- **Size.** 210 runtime lines added; converting every widget would let 53 lines
  of the copied-button path go. Taller cards show about 3½ per phone screen
  instead of 4.

## Why it is parked

The gap C closes is rare. On the 263 pages on the maintainer's machine in
October 2026, all 631 `lf-ask` held a decision widget, and 2 of 1,110 agent
replies carried a widget in a thread message.

## If it is picked up

Keep the card's copy out of id space: mount it where no lookup reaches, and move
a thread widget's single instance into the card rather than copying it. B suits
per-record obligations and touches no ids, at the cost of a second render path
per widget. The prototype's tests are in its
`tests/browser/widgets/test_on_panel.py`.
