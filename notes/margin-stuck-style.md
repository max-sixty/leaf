# A margin Undo that stays hidden under load

On a loaded machine, rejecting the feature gallery's suggested insertion (`bg-insert`)
can leave its Undo unreachable: the margin row that carries it stays hidden beside a
passage that is on screen. The same defect hides the suggestion's Accept and Reject
after an Undo. Two nightly tests show it as flakes:

- `test_render_margin.py::test_the_feature_gallery_keeps_its_real_actions_reachable`
  (the Undo click times out, or Accept is not visible after the Undo);
- `test_render_navigation.py::test_the_feature_gallery_keeps_a_choice_when_its_proposal_is_undone`
  (rarely).

They are not marked flaky or listed as known: the control really disappears.

## What fails

The rows are hidden by the margin layout acting correctly on a wrong reading of the
page's style:

- After the reject, the Undo moves to a row anchored to the passage around the emptied
  suggestion, `span#bg-insert-line`. The layout writes `anchor-name: --lf-a15` on the
  span and points the row at it. The browser never applies the name, so the row stands
  at its off-screen fallback, and the layout parks it (`data-lf-parked`, withheld) for as
  long as it anchors to that span (`margin-layout.js`, `parked`).
- After an Undo, the suggestion's own row stays withheld while the suggestion is shown
  again, with the suggestion's style stuck the same way.

In both, the target element's style has stopped updating. On `span#bg-insert-line` (and
`lf-suggestion#bg-insert` inside it):

- `getComputedStyle` keeps answering `anchor-name: none` with the inline style present;
- an inline `color` or custom property written on the span, or on its `strong` child,
  never shows in `getComputedStyle`;
- removing and re-adding the whole `style` attribute does not help;
- a style change on the parent paragraph (`p#bg-change-forms`), such as setting a
  custom property there, makes the span recompute, after which every write applies.

`bg-replace-line`, the sibling span, is never affected. On a page at rest the same probe
reads every write back.

## How it was measured

A probe that does not unstick a stuck span: write a custom property on the element itself
and read it back. Probing the span this way at several points before and after the
reject seemed to prevent the stuck state (0 of 24 copies, twice), so the harness probes
once, at the end.

```js
(id) => {
  const t = document.getElementById(id);
  t.style.setProperty("--lf-stuck-probe", "q1");
  const ok = getComputedStyle(t).getPropertyValue("--lf-stuck-probe").trim() === "q1";
  t.style.removeProperty("--lf-stuck-probe");
  return !ok; // stuck
}
```

The harness was a throwaway, non-nightly test in `tests/` (not committed). Each of 48
parametrized copies opens `FEATURE_GALLERY` with `open_page`, sets CPU throttling
(`Emulation.setCPUThrottlingRate`, 20), resizes to 1440×900, clicks the
`[data-lf-margin-entry-owner="suggestion:bg-insert"][data-lf-margin-entry-key="reject"]`
entry from script, runs `round_trip`, waits 1s, and records the probe for
`bg-insert-line`, `bg-insert` and `bg-replace-line`:

```sh
uv run pytest tests/test_scratch_stuck.py -m 'not nightly' -n 8 -p no:randomly
```

About 2.5 minutes. On main (2026-10-01) the span stayed stuck in 6–15 of 48 copies
across runs; at 10x throttling, 2 of 24. The flake predates #1493: CI nightly at
`f2b153139`, run as 18 concurrent copies (`leaf-dev flake`), failed the margin test
3–6 of 18 at 1440px and 1–2 of 18 at 1200 and 700px, as main and every partial revert of
#1493 did.

## What was ruled out

Each switch was one run of 48 copies; "stuck" counts copies with `bg-insert-line`
stuck.

| Switched off or changed | Stuck |
|---|---|
| nothing (baseline, several runs) | 6–15 |
| no action at all | 0 |
| a different gesture: choosing `#bg-route-river` | 0 |
| the accept-and-undo of `bg-replace` before the reject (dropped from every row below) | 8 |
| the pointer: the entry clicked from script (every row below) | 8 |
| the margin target falling back to the parent (`target: () => this`) | 7 |
| the `:has()` rule hiding an emptied suggestion | 13 |
| the widget's emphasis and spoken labels | 15 |
| the widget's whole settle (`#settle` returns at once) | 10 |
| that, plus the layer's `paintSettlements`, `aria-busy`, and the selection clear | 8 |
| all of that, plus focus moving to the Undo | 2 |
| CSS highlights (`CSS.highlights.set` stubbed) | 8 |
| every `anchor-name` (`* { anchor-name: none !important }`) | 6 |
| `container-type` (`* { container-type: normal !important }`) | 8 |
| the margin layout pass (`layoutMarginRows` returns at once) | 11 |
| the suggestion's `says` reads for its label | 4 |
| `changed()` in the contribution's `update` | 7 |
| `paintKeys()` after the refresh | 10 |
| **the suggestion's whole `#refreshMargin` after the click** | **0** |

With the widget's settle and the layer's settlement paint off, the suggestion stays
shown, its row keeps targeting it, and nothing in the span's subtree mutates; the span
still sticks. So the trigger is not a mutation inside the subtree.

## The lead

Skipping the suggestion's whole `#refreshMargin` after the click was the only switch
that cleared it (`lf-suggestion.js`): `this.#margin.update(...)`, which publishes the
reading (calling `read()`), schedules the projection, and with `immediate` settles it and
runs `layoutMarginRows()` synchronously, then `paintKeys()`. Each part switched off
alone still stuck, so either the parts combine or a single 0/48 was luck at the low end
of the rate. Read it as a lead, not a cause.

## Not reproduced without Leaf

A static snapshot of the live page (its whole DOM, every stylesheet including the
adopted ones as text, scripts removed), replaying exactly the DOM mutations the reject
makes under `p#bg-change-forms` (recorded with a MutationObserver: `data-lf-state`,
`data-lf-retired`, the moved label, `anchor-name` on the span, `data-lf-user-override`),
stuck 0 of 48 at 20x throttling. The runtime does something more around the reject.

## Next step

Record, in the live page, every runtime call that reads or writes `bg-insert`, its
ancestors, or their style, between the click and the first stuck probe (DOM writes,
`getComputedStyle`, `checkVisibility`, geometry reads, observer callbacks, in order),
and replay that sequence in the static snapshot. Cut it down until a page without
Leaf sticks. Then either file it with Chromium, attaching that page, or fix the call in
Leaf that triggers it.
