# One decision, answered in its section and shown on a board

Open design question, 30 September 2026. Nothing here is built; a prototype of
approach A was made and discarded.

## The need

A review page argues several proposals, one section each, and asks the user to
sort them into Next, Later and Drop. Asking at the end, on one `lf-board` that
repeats every proposal as a card, puts the decision far from its evidence;
asking only in each section loses the view of every answer together. The user
wants both: answer in the section, see and rearrange all answers on a board,
with both surfaces reading and writing the same fact.

## Why Leaf can't today

Every widget action is keyed by `[owner widget, fold unit, verb]`.
A section's choice is `(rail-choice, rail-choice, choose)` and a board move
`(plan-board, card-rail, move)`, so a picker and a card for one proposal hold
two facts. Run on a scratch page, the append door admitted a `choose` of Next
and a `move` of the card to Drop, `leaf page state` reported both with no
precedence, and `version check` accepted markup that wrote both.

## Four approaches

They differ in what owns the answer; every other surface is a view of it.

| | A · picker owns | B · board owns | C · section owns | D · records own |
| --- | --- | --- | --- | --- |
| Answer beside its evidence | yes | no, in the board | yes | no, in the record |
| Next / Later / Drop written | once per section | once | once, as a scale | once, as a scale |
| Order within a column | needs a second owner | yes | yes, as a field | yes, as a field |
| Section's Ask works as today | yes | needs cross-owner Asks | yes | needs cross-owner Asks |
| Tasks the user adds | no | yes, as cards | later, as records | yes |
| New in Leaf | views | views, cross-owner Asks | views, scale, a field on `lf-ask` | views, records, cross-owner Asks |

- **A.** `lf-options` keeps the answer; the board maps each option's value to
  a column. Smallest step. The values repeat in every section, cards take no
  order, and a write-in answer has no column.
- **B.** The board keeps column and order; each section shows a control drawn
  from its card. Asks answered by another widget's action are a kernel change
  (`asks.py` reads the widget's own coordinate).
- **C.** The section's `lf-ask` carries `value` (and later `rank`); a picker
  and the board are views; `lf-scale` declares the values once. One element
  holds the question's words, evidence and answer, so comments, the Asks tray,
  `restated` and write-back land together.
- **D.** A data-only record set holds every answer; sections and board are
  views. Suits tasks the user adds; splits each answer from its words.

Recommendation: C. A is right if order and a shared value set can wait; D if
user-added tasks become the main use, and C can add records later
(the editable rows `datastore-review.md` proposes) without undoing anything. Two
independent reviews split between A (keep `lf-options` as owner, add views)
and C.

## What every approach needs

Each approach needs a declared view relation in the registry. The proposed name is
`x-shows`; `x-views` already names holders like `lf-tabs` that show one member at a
time. A view names the owners it shows, using the nearest ancestor, an attribute
naming an owner, or an attribute match. It also declares the verb it may send for
those owners.

The kernel would supply the owners' state through the publisher and record a view's
gesture against the owner, with the view as `via`. It would refuse a gesture from a
view that does not show that owner, check that authored placement agrees with the
owner, and report placement as derived in `leaf page state`. A widget with no views
would be unchanged. At the time of the experiment, 8 of the 13 declared verbs already
owned their widget's own field. Writes would remain serialized by the append door,
so several views or tabs would need no merging.

## C, sketched

```html
<lf-scale id="disposition">
  <lf-value id="next">Next</lf-value>
  <lf-value id="later">Later</lf-value>
  <lf-value id="drop">Drop</lf-value>
</lf-scale>

<lf-board id="plan" scale="disposition"></lf-board>

<lf-ask id="rail-ask" scale="disposition">   <!-- answered: value="later" -->
  <h3>When should the rail stay beside the text?</h3>
  <lf-pick></lf-pick>
</lf-ask>
```

`lf-ask` declares a `set` verb with a `value` record, as command-hub's
`lf-task` declares `status`. A board drop logs
`{"widget": "rail-ask", "action": "set", "detail": {"value": "next"}, "via": "plan"}`.

Open within C: where rank is written back when a revision reorders subjects
(the `among` problem board moves already have); whether a comment on a card
shows in its subject's thread seat; what `restated` on an `lf-value` retracts;
`lf-ask` as the subject versus a new generic element.

## The discarded prototype

A card with `for` naming an `lf-options` group was placed by that group's pick,
in the column its chosen option's `for` named, and a drop sent the group's own
`choose`. It worked both ways with no change to the log, admission or Asks.
Reviews found it tag-coupled (the board named `lf-options` and `choose`),
overloaded option `for`, let a group without `choose` be written through the
board, left write-ins with no column, still let the door admit a board `move`
on a gathered card, and repainted from another widget's subscription outside
the board's own render region.

## Next

Choose an approach. The design page with the comparison, each approach's markup
and a live sample is at
`~/.local/state/leaf/pages/shared-state-design/` (v4).
