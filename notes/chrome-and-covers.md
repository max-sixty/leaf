# Chrome, covers and widget shapes

Research on main at `5ed41df4b`, 29 September 2026, from a user review of a 21-item
triage queue page. The plan keeps the document scrolling on the root, gives the banner
one fixed height, gives every box that sticks over content a stated height stacked
through `--lf-top`, and stops the workspace Layout from writing inside the widget it
arranges. The bottom bar stays for now and goes in a second step.

## What went wrong on the queue page

`page-authoring.md` prescribes a queue as `<main class="layout-workspace">` with one
`lf-tabs list="side"` as its body. That page failed `page check --render` with 76
overlaps, so its author fell back to `layout-wide`, and every other layout problem on
the page followed from the fallback. Two causes, each sufficient on its own (probed on
the user's page at 1728×1000):

- The workspace writes `grid-auto-rows: minmax(0, 1fr)` on its body
  (`skills/leaf/assets/layouts.css`, the full-height block). The rule is meant for a
  page's grid of panes, but it also lands on `lf-tabs`' own grid, which held the list's
  row to the body's 841px. Resetting it alone let the list run its full 1586px.
- `.lf-tab-btn` states its hit floor as `min-height: var(--aim-floor)`, which replaces
  flexbox's `min-height: auto`, the minimum that keeps an item as tall as its content.
  In the 841px column each 72px row shrank to 38px and drew over the next. Setting
  `min-height: auto` alone restored them. The page-flow strip was patched for the same
  thing earlier with `flex: none` (`packages/default/theme.css`, the page-flow strip).

The unmerged commit `771b3d72c` (branch `tend-dashboard-review`) fixed the queue with a
second `flex: none`, a sticky list whose top and height `lf-tabs.js` measures for each
kind of scroller (`#fitList`), and a landing rule. An independent review of its first
version found the measured list broken in a pane body, in a section-wrapped workspace
body and under a page tab strip, one case per kind of scroller.

The same missing contract shows outside `lf-tabs` on main today. An `lf-diff` inside a
page tab pins its file header at `--lf-top`, the banner's 42px, where the page tab strip
also sticks, so the diff's header is drawn over the tabs. To reproduce, write a column
page with a root `lf-tabs` whose first tab holds a 200-line `lf-diff`, then:

```bash
uv run leaf-dev probe page.html --viewport 1440x900 --js 'async () => {
  const d = document.querySelector("lf-diff");
  document.documentElement.scrollTop += d.getBoundingClientRect().top + 1500;
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const strip = document.querySelector("lf-tabs > .lf-tabstrip").getBoundingClientRect();
  const head = d.shadowRoot.querySelector(".lf-diff-file > details > summary").getBoundingClientRect();
  return { strip: [strip.top, strip.bottom], head: [head.top, head.bottom] };
}'
```

On `5ed41df4b` the strip spans 42–89px and the diff header 42–77px.

## Why the chrome handling is complicated

The banner and bottom bar are fixed over the page's scroller, and a sticky box inside
that scroller has to know how much of it they cover. worktrunk.dev (Astro Starlight)
covers its scroller the same way with about ten CSS rules and no script, because its
header has a stated height (`--sl-nav-height`, 3.5rem or 4rem), a second cover has a
stated height too (`--sl-mobile-toc-height`), and each consumer adds them in `calc`.

Leaf's cost comes from three things Starlight does not do:

- **Covers of measured height.** The banner is one row or two, chosen by an observer
  (`data-lf-banner-rows`, `banner.js`) with guesses in `theme.css` before it runs. The
  page tab strip and diff file headers are measured by `declareStickyHeaders`
  (`runtime/geometry.js`), which needs a size observer, a pass for headers not yet
  measured, and a special case in `insetBand` for covers that stick under the banner.
- **Covers that do not add up.** The page tab strip's height goes into
  `--lf-root-tab-clear`, which only `scroll-padding` reads. `--lf-top` never includes it,
  so anything sticking inside a page tab sticks under the strip.
- **Scrollers inside the page.** The workspace body and pane bodies inherit the page's
  `--lf-top` and each resets it (`layouts.css`), and CSS gives a box no reading of its
  scroller's height, so `#fitList` measures it in script.

## Options weighed

| Foundation | Keeps | Costs |
|---|---|---|
| **A.** Root scrolls; every cover has a stated height, stacked through `--lf-top` | Native keyboard scrolling, history and reload restoration, one layout on every surface | A one-row banner needs an overflow menu; covers cannot wrap |
| **B.** The page scrolls in a box between the bars | Nothing covers the page box | Leaf rebuilds keyboard scrolling and position restoration, moves `documentPoint`'s 8 callers, reworks ~405 test references; print, samples, export and the MCP frame need a second layout mode |
| **C.** Banner scrolls away; a corner pill stays | Root scrolling | Status and Approval out of view; the pill covers text |
| **D.** Banner becomes a strip at the left edge | Root scrolling, nothing covers vertically | Takes width from the column and margin; collides with the Asks drawer and contents map; fails on phones |

B does not fix the conflicts that prompted this: in a page box, the diff header and the
page tab strip would both stick at `top: 0` and collide the same way.

Tested in Chrome on a plain page, root scroller against a page box:

| Behaviour | Root scrolls | Page box |
|---|---|---|
| PageDown or Space on load, nothing clicked | scrolls | stays |
| PageDown after clicking text in the page | scrolls | scrolls |
| PageDown after clicking the header | scrolls | stays |
| Back after `pushState` | position restored | stays at the later position |
| Back from another document, or reload | position restored | top |

Chrome also honours `scroll-padding-top` for PageDown, so a stated-height banner keeps
paging correct. C and D were judged on design grounds, not tested.

## The foundation

- **The root scrolls on every surface:** live, print, export, sample and MCP frame. A
  live page adds a fixed banner and top padding of its height.
- **The banner is one row of one stated height,** one value per pointer type. Controls
  that do not fit go into its menu.
- **Covers stack through `--lf-top`.** On the root it is the banner's height; in any
  other scroller it is 0. A cover has a stated height, sticks at `var(--lf-top)`, and
  adds that height to `--lf-top` for what it covers. `scroll-padding` and the runtime's
  reading of what the user can see take the same value. Nothing is measured. A custom
  property cannot reference itself, so the cover's holder passes the incoming value on
  under a second name.
- **A Layout sets a box's outer size and whether it scrolls, never its inner tracks.**
  A widget fills the box it is given with `height: 100%` or `fr` tracks, which CSS
  resolves to content height where no height is given (probed), and keeps its
  content's minimum on both axes.
- **Scrollers inside the page exist only at bounded regions:** a pane, a panel, a block
  marked bounded.

## Plan

Step 1:

- Fix the banner at one row with an overflow menu, including on a phone. This is the
  largest piece and it is design work in `banner.js`.
- Give the page tab strip a stated height (it is already one row that scrolls
  sideways; hide the scrollbar so it cannot add height) and the diff file header one
  line, its path ellipsized with the whole path on hover or focus.
- Stack covers through `--lf-top` and delete `declareStickyHeaders`,
  `headersByScroller`, `measureUnseenHeaders`, `insetBand`'s sticky-inset case,
  `--lf-root-tab-clear` and the banner rows observer and guesses.
- Apply the workspace's row rule only to a body that holds panes
  (`:has(> [data-lf-reading-role="pane"])`); the five pane-grid examples keep it.
- Give `lf-tabs list="side"` a full-height form, answering `--lf-full-height` as
  `lf-ask`, `lf-playground` and `lf-visual-review` do: list and item scroll on their own
  inside the workspace body. On a flowing page the list sticks at `var(--lf-top)` with
  the view's height as its maximum.
- Move the tab row's `flex: none` to the base `.lf-tabstrip .lf-tab-btn` rule, replacing
  both copies.

`771b3d72c` then keeps its landing rule and `.tag { align-self: center }`, and drops
`#fitList`, `--lf-list-top` and `--lf-list-view`.

Step 2: drop the bottom bar. It already has a stated height, so step 1 does not touch
it and it does not get harder to remove. Removing it deletes `--lf-bottom-bar-h` and its
readers (`theme.css`, `chrome.css`, `shortcut-bar.js`, `lf-toc`), `declareBottomBar`, and
the bottom edge in `shownWindow`. Its key hints move to `?` and its status into the
banner.

Separately, `lf-options` cards run 1294px beside 720px paragraphs in a wide panel,
because text keeps the measure (`theme.css`, `:where(p, li, …) { max-inline-size:
var(--col) }`) and a widget without `x-space` takes the whole flow. Declaring the
existing column allocation on `lf-options` is not enough on its own: `schema.py` allows
`x-space` only `wide` and `available`, and `[data-lf-space="column"]` centres its box
(`margin-inline: auto`) while text in a wide flow starts at the left edge. The column
allocation and the text measure have to align the same way first; start-aligned in any
flow wider than the column is the reading that matches the prose.

## Open questions

- What the one-row banner holds on a phone, and what goes behind its menu.
- The visible height a sticky side list takes as its maximum inside a pane body. A
  pane body the workspace sizes can be a size container (`100cqb`); a generated pane
  sized by its content cannot, since size containment collapsed one in
  `notification-playground` from 158px to 28px.
