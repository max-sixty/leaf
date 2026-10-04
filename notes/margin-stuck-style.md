# A margin Undo that stays hidden under load

On a loaded machine, rejecting the feature gallery's suggested insertion (`bg-insert`)
can leave its Undo unreachable: the margin row that carries it stays hidden beside a
passage that is on screen. The suggestion's Accept and Reject can also disappear
after an Undo. The gallery actions journey has failed on main, including at 1200px
on `999e0231a`. The runtime, gallery source, and test used for the latest diagnosis
match main `015b1b9c26c240aeaef186e5f4981fcd85a881e1`.

Under `/fix-ci`'s fallback for a stuck failure verified on main,
`test_render_margin.py::test_the_feature_gallery_keeps_its_real_actions_reachable`
is a running `xfail(strict=False)` at all four widths. It still exercises the real
journey and can XPASS when the intermittent defect does not occur. The marker accepts
`AssertionError` and Playwright's `TimeoutError`; fixture `SystemExit` and other
exception types still fail. This quarantines the CI failure; it does not fix the
zero-size rendering defect. The navigation journey
`test_render_navigation.py::test_the_feature_gallery_keeps_a_choice_when_its_proposal_is_undone`
was implicated in the earlier investigation, but has no fresh main failure here and
remains unmarked.

The insertion-retirement assertion added in #1687 also fails with the runtime from
main `5984ca1c9`: an 18-copy pin round trip passed eight and failed ten. After
rejection, `#bg-insert lf-new` retains visible native style with `data-lf-retired`,
the hiding rule present, completed rendering, and no live animation. A raw Chromium
capture preserves its painted words; a normal screenshot's caret preparation can
unstick them. The test records this known retirement failure, completes every original
pin restoration and geometry assertion, and only then conditionally xfails. Those
other failures remain failures. Native minimal controls did not reproduce the defect,
so the triggering interaction is still unconfirmed.

After integrating main `085938106`, fifteen of eighteen pin journeys still reach
that retirement failure while all their original restoration and geometry checks
pass. `--runxfail` re-raises the saved original visibility assertion instead of
silently passing it. An explicit native 60px pin displacement still fails its
geometry assertion even when the retirement failure was already recorded.

The narrow journey command is:

```sh
uv run pytest 'tests/test_render_margin.py::test_the_feature_gallery_keeps_its_real_actions_reachable[1200]' -q -n0
```

The initiating failure is intermittent; this command can pass.

## What fails

The diagnosis on main exposed both a stale style/geometry reading and a separate
permanent parking defect:

- After the reject, the Undo moves to a row anchored to the passage around the emptied
  suggestion, `span#bg-insert-line`. The layout writes `anchor-name: --lf-a15` on the
  span and points the row at it. Computed style still reports `none`, so the row stands
  at its off-screen fallback. The diagnosed main layout cached that failed reading and
  kept the row parked (`data-lf-parked`, withheld) while it anchored to the same span.
- After an Undo, the authored suggestion state is restored and computed `display`
  returns `inline`, but the suggestion can still have a 0x0 bounding rectangle. Its
  Accept/Reject row stays withheld without being parked.

A small fixture independently verified the parking defect: temporarily override a
suggestion's `anchor-name` with `none`, run `layoutMarginRows()`, remove the override,
and run layout again. The same element's anchor name returned but its row stayed parked
and withheld; the cache cleared only when the anchor element changed. The repair
removes that cache and reads anchor availability on each layout pass. The scope
regression now verifies that removing an author's `anchor-scope` restores the existing
row and clears its stranded-margin finding. This repair cannot restore the zero-size
suggestion after Undo; that initiating failure remains quarantined.

The latest live reproduction used Chromium headless shell 153.0.8010.12 at 1200px,
normal motion and 20x CPU throttling, without the suite's write or typed-word watchers.
The second of two fresh pages lost Undo after accepting/undoing `bg-replace` and
rejecting `bg-insert`. Invoking the existing hidden Undo button from script restored
state but left the suggestion and its action row at 0x0. One fresh full Chrome
154.0.8037.97 run with the same motion, width, throttling and absent watchers passed.
That single cross-target pass does not establish a version remedy. Replacing native
`checkVisibility` in a separate diagnostic also left the live failure reproducible.

Earlier stuck-state probes on `span#bg-insert-line` (and `lf-suggestion#bg-insert`
inside it) recorded:

- `getComputedStyle` keeps answering `anchor-name: none` with the inline style present;
- an inline `color` or custom property written on the span, or on its `strong` child,
  never shows in `getComputedStyle`;
- removing and re-adding the whole `style` attribute does not help;
- in earlier runs, a style change on the parent paragraph (`p#bg-change-forms`), such
  as setting a custom property there, made the span recompute. In the latest failed
  journey, a parent write still left the revived suggestion and controls at 0x0.

`bg-replace-line`, the sibling span, was unaffected in these runs. On a page at rest
the same probe reads every write back.

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

The harness is a non-nightly test, kept here rather than in the suite because each run
takes minutes. Save it as `tests/test_scratch_stuck.py` (and delete it after): each of
48 copies opens the gallery at 20x CPU throttling, rejects `bg-insert` from script, waits,
and writes the probe for three elements to `.tmp/stuck/<copy>.json`.

```python
import json
import pathlib

import pytest
from render_harness import FEATURE_GALLERY, open_page, resized, round_trip

OUT = pathlib.Path(__file__).parents[1] / ".tmp" / "stuck"
STUCK = """(ids) => window.lfUnwatched(() => Object.fromEntries(ids.map(id => {
  const t = document.getElementById(id);
  t.style.setProperty('--lf-stuck-probe', 'q1');
  const ok = getComputedStyle(t).getPropertyValue('--lf-stuck-probe').trim() === 'q1';
  t.style.removeProperty('--lf-stuck-probe');
  return [id, !ok];
})))"""
REJECT = (
    '[data-lf-margin-entry-owner="suggestion:bg-insert"]'
    '[data-lf-margin-entry-key="reject"]'
)


@pytest.mark.parametrize("copy", range(48))
def test_scratch_stuck(browser, serve, copy):
    page = open_page(browser, serve(FEATURE_GALLERY))
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 20})
    resized(page, 1440, 900)
    page.locator(REJECT).evaluate("button => button.click()")
    round_trip(page)
    page.wait_for_timeout(1000)
    OUT.mkdir(exist_ok=True)
    stuck = page.evaluate(STUCK, ["bg-insert-line", "bg-insert", "bg-replace-line"])
    (OUT / f"{copy}.json").write_text(json.dumps(stuck))
```

```sh
rm -rf .tmp/stuck
uv run pytest tests/test_scratch_stuck.py -m 'not nightly' -n 8 -p no:randomly
grep -l '"bg-insert-line": true' .tmp/stuck/*.json | wc -l
```

The probe writes inside `lfUnwatched` (`tests/write_watch.js`), so the browser
fixture does not count its own writes; every copy passes, and the count is the
measurement. A run on 2026-10-01 counted 9 of 48.

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
There is no engine-only minimal reproduction yet. The initiating cause remains
unconfirmed.

## Next step

Record, in the live page, every runtime call that reads or writes `bg-insert`, its
ancestors, or their style, between the click and the first stuck probe (DOM writes,
`getComputedStyle`, `checkVisibility`, geometry reads, observer callbacks, in order),
and replay that sequence in the static snapshot. Cut it down until a page without
Leaf sticks. Then either file it with Chromium, attaching that page, or fix the call in
Leaf that triggers it.
