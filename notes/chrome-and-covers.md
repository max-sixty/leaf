# Workspace scrolling and chrome

The sticky-header foundation landed in [PR #1472](https://github.com/max-sixty/leaf/pull/1472).
The banner has a stated height, sticky headers stack through `--lf-top`, and the
workspace row rule applies to pane grids without squeezing a widget's own rows.
These contracts live in [layouts.css](../skills/leaf/assets/layouts.css),
[theme.css](../skills/leaf/assets/theme.css), and the
[package header contract](../skills/leaf/references/packages.md).

The remaining decision is whether a workspace's main region scrolls with the root
or whether its panes keep their own scrollers. Bottom-bar removal and the phone
banner are separate choices. No further layout choice has been made.

## Options weighed

**A, implemented:** the document scrolls at the root; covers have stated heights
stacked through `--lf-top`. This preserves native page scrolling and restoration.
Moving the whole page into an inner scrolling box would need separate keyboard,
restoration, print and export behavior without settling header stacking.

**E, proposed:** keep A and make a workspace's main region flow with the document.
Side regions stick below the headers and scroll internally only when taller than
the available window. This changes the workspace's full-height contract and the
widgets and pages that consume it; it is not just a different grid rule.

**Keep pane scrollers:** retain the full-height workspace. Decide whether
`lf-tabs list="side"` needs independent list and item scrolling, with the item
registered as a reading region, or whether both may scroll away together.

Compare E and the pane-scroller form over the same `alert-review` task in a
playground before choosing. A root-scrolling grid could also work inside a block,
but a nested workspace still needs a concrete page that requires it.

## Evidence

The original review ran on 29 September 2026 at `5ed41df4b`, with alternatives
reviewed at `ef3cea8b3`. On a plain Chrome page it found:

| Gesture | Root scroller | Inner page box |
|---|---|---|
| PageDown or Space before a click | Scrolled | Stayed still |
| PageDown after clicking body text | Scrolled | Scrolled |
| PageDown after clicking the header | Scrolled | Stayed still |
| Back after `pushState` | Restored position | Kept the later position |
| Back from another document, or reload | Restored position | Returned to top |

On `alert-review` at 1440×900, PageDown twice on load moved nothing; after a click
in the detail pane it scrolled that pane. These are dated observations, not new
measurements of the current candidate. Repeat them for both playground arms:

```bash
uv run leaf-dev probe alert-review --viewport 1440x900 --do press:PageDown
```

Read root and pane `scrollTop`, then test reload and browser Back. A screenshot
alone cannot establish scroll ownership or restoration.

## Costs of option E

- **Full-height widgets:** `lf-playground`, `lf-visual-review` and `lf-ask` would
  need forms that work in sticky regions. Check `notification-playground` and
  `visual-review-gallery` as well as the workspace examples.
- **Footers:** queue counts and policy Asks currently remain at the window's foot.
  In document flow they move to the end unless another sticky cover holds them.
- **Margin lanes:** a stuck region's clipped lane must follow root scrolling while
  its rows remain attached to their targets.
- **Landings:** scrolling to an item inside a stuck side region must leave the
  root's reading position intact. A plain-page probe moved the root by 552px.
- **Per-item position:** changing a side-list item must preserve the places that
  root tab sets already retain through `reading-place.js`.
- **Phones:** stacked regions must stop sticking and drop their maximum height,
  rather than become window-tall inner scrollers.

## Remaining plan

Build both scrolling forms over `alert-review`, including a long queue and detail,
a footer Ask, a margin thread and an unfinished comment. Test PageDown from load,
reload, Back, side-region landing and per-item return at wide and narrow widths.
Include `rust-sort`, `wt-merge`, the review-queue and comparison fixtures, and the
full-height widget examples as distinguishing neighbors.

If E wins, cut over the Layout, widgets, examples and author guidance together.
Retire `--lf-full-height`, `syncLayoutRegion` and the render check's `heldPanes`
only when their duties are covered by the new contract. If pane scrollers win,
settle the side-list reading region without duplicating scroller measurements.

Independently compare keeping and removing the bottom shortcut bar. Removing it
moves key discovery behind `?` and its notices and navigation state into the
banner. Design the phone row for those contents before changing either surface.
Use `leaf-dev stills` against the merge base for changed first viewports and banner
states, alongside gesture evidence for scrolling and restoration.
