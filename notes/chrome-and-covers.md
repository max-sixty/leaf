# Chrome, covers and widget shapes

Research on main at `5ed41df4b`, 29 September 2026, from a user review of a 21-item
triage queue page, then reviewed against alternatives at `ef3cea8b3`. The plan keeps
the document scrolling on the root, gives the banner a stated height, gives every box
that sticks over content a stated height stacked through `--lf-top`, and stops the
workspace Layout from writing inside the widget it arranges. That first step has landed
("Step 1, landed"); the sections before it describe main as it stood. What remains is
one decision, whether a workspace keeps panes that scroll on their own or its regions
stick to the root scroller instead (option E), and then the bottom bar and the phone
banner.

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
  Twelve rules state the floor this way (`rg 'min-(height|block-size):\s*var\(--aim-floor'
  skills/leaf`) and eight more as `max(Npx, var(--aim-floor))`, and each is crushable in
  a bounded flex container.

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
  scroller's height, so `#fitList` measures it in script. Nothing else resets it: a
  bounded block (`data-bound`) and every box that scrolls sideways (`table`, `pre`,
  `lf-board`, `lf-diagram`, where `overflow-x: auto` makes the other axis `auto` too) is
  a scroller in which `--lf-top` still reads the banner's height, so an `lf-diff` in a
  bounded block pins its header 42px below the block's top.

Only two things stick vertically inside the page on main: the page tab strip and the
`lf-diff` file header, with its review press. The first `aside.sidebar` in the margin and
a Layout track's block (`page-authoring.md`) stick at `var(--lf-top)` with content
height and cover nothing below them.

## Options weighed

| Foundation | Keeps | Costs |
|---|---|---|
| **A.** Root scrolls; every cover has a stated height, stacked through `--lf-top` | Native keyboard scrolling, history and reload restoration, one layout on every surface | The banner's height must be computable in CSS; covers cannot wrap |
| **B.** The page scrolls in a box between the bars | Nothing covers the page box | Leaf rebuilds keyboard scrolling and position restoration, moves `documentPoint`'s 6 callers (9 with raw `scrollX/Y` conversions), reworks ~405 test references; print, samples, export and the MCP frame need a second layout mode |
| **C.** Banner scrolls away; a corner pill stays | Root scrolling | Status and Approval out of view; the pill covers text |
| **D.** Banner becomes a strip at the left edge | Root scrolling, nothing covers vertically | Takes width from the column and margin; collides with the Asks drawer and contents map; fails on phones |
| **E.** A with no pane scrollers: a workspace's main region scrolls with the root, and the regions that stay in view stick to it | Everything A keeps, on workspace pages too; the only scroller whose height a sticky box needs is the root's, which is stated | Reworks the workspace Layout, the widgets that fill a full-height body, their guidance and the pages on them; moves the nested scrollers into the side regions rather than removing them; costs listed below |
| **H.** One bar at the window's foot instead of the banner | Root covers start at 0, so nothing adds the banner's height | Primary actions at the foot on a desktop; iOS Safari's bottom toolbar and the home indicator share that edge; the drawers and thread panel hang from the top |

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
paging correct. C, D and H were judged on design grounds, not tested.

A full-height workspace is B inside `main`: the root does not scroll, and each pane body
is a page box. On `alert-review` at 1440×900, PageDown twice on load scrolled nothing;
after a click in the detail pane it scrolled that pane (`leaf-dev probe alert-review
--do press:PageDown …`, reading every element's `scrollTop`). So the costs that ruled B
out for the page apply to every workspace page, and every failure of the side list
above (`#fitList`'s three broken scrollers, the `--lf-top` resets, the negative
`--lf-pane-top` offset, the open question about a pane body's visible height) comes
from a pane scroller.

E keeps the arrangement a workspace offers without the pane scrollers. The main region
flows with the page; the others stick at `var(--lf-top)` with
`max-block-size: calc(var(--lf-view-height) - …)` and scroll on their own once taller
than that, as the margin sidebar already does (`theme.css`,
`main.layout-column[data-lf-margin~="sidebar"]`) and as `page-authoring.md` already
prescribes for a Layout track shorter than the window. The five pane-grid pages each
have one main region: in `alert-review` the queue sticks and the detail flows, in
`rust-sort` the stage sticks and the source flows, in `wt-merge` the film sticks and
the steps flow, and likewise in the fixture `review-queue`. The fixture
`current-proposed-comparison` has two equal columns, which would flow side by side and
scroll together as one page. E also retires `syncLayoutRegion` and the render check's
`heldPanes` reading, since no region's height depends on the window's any more, and
settles the TODO item on letting a block be a workspace, since a sticky region works at
any depth in the root's flow that has no scrolling ancestor.

E costs more than the Layout:

- **Widget full-height forms.** `lf-playground` (controls scroll while the instruction
  stays whole), `lf-visual-review` and the full-height `lf-ask` answer
  `--lf-full-height`, as `packages.md` documents; `notification-playground` and
  `visual-review-gallery` are built on them. Each needs a sticky-region form instead.
- **Footers in view.** `alert-review`'s "Nine decisions open", `review-queue`'s footer
  and `current-proposed-comparison`'s footer, which holds the policy Ask, stand at the
  window's foot today. Under E they sit at the document's end unless they stick at the
  bottom, a second cover stack at the other edge.
- **Margin lanes.** A region's lane is clipped to the region by a `clip-path` the layout
  pass recomputes, and `hearScrolls` skips the root's scroll, so a stuck region's clip
  goes stale as the root scrolls. The rows themselves follow their targets (anchor
  positioning against a sticky anchor, probed). The lane needs a pass on root scroll,
  or a fixed lane.
- **Landings into a side region.** `scrollIntoView({block: "start"})` on an item near
  the end of a stuck side region scrolled the root by 552px on a plain page, which
  loses the reader's place in the main region. Travel into a stuck region has to scroll
  only the region.
- **Per-item places.** A side list's items share one root offset, so switching items
  needs the per-view place memory root tab sets already keep (`reading-place.js`).
- **Phones.** Where the regions stack, they stop sticking and drop their maximum height,
  or a stacked queue becomes a window-tall inner scroller.

Neither the mechanical step (step 1, below) nor the two causes of the queue failure
depended on E, so they came first; decide E from `alert-review` built both ways in a
playground.

## Step 1, landed

Step 1 settled the foundation A describes, and each contract now lives beside its code
(the glossary's name for a cover is a sticky header):

- The banner's height is stated: `theme.css` computes its rows from the pointer, the
  window's width and the declared sign-off (`data-lf-review`), and the rows observer
  and the pre-runtime guesses are gone.
- Sticky headers stack through `--lf-top`, a registered length (`theme.css`, at its
  `@property`; `packages.md` for a package's header). The page tab strip is one row of
  a stated height with presses at its edges in place of a scrollbar (lf-tabs.js), and
  a diff's file header is one line of a stated height whose path gives way from its
  folders (diff `shadow.css`). A header over a whole scroller joins its
  `scroll-padding`; one over part of it gives its rows `scroll-margin-top`.
- The runtime reads what the headers stand over from `--lf-top` (geometry.js,
  `headerInset`), which replaced `declareStickyHeaders` and the measured rooms.
- Every box the theme makes scroll that can hold a header starts `--lf-top` from 0: a
  bounded block, a table, a board, and the workspace's scrollers.
- The workspace's row rule applies only to a body holding panes (layouts.css), and the
  hit floor is padding where a flex or grid container could squeeze a control.

## Remaining plan

Step 2, E if chosen: rewrite the workspace Layout as a grid whose side regions stick at
`var(--lf-top)` and scroll within `--lf-view-height`, with `lf-tabs list="side"` as one
such case (its list sticks, its item flows); give `lf-playground`, `lf-visual-review`
and `lf-ask` sticky-region forms; make the footers stick at the bottom; solve the margin
lane, side-region landing and per-item place costs above; move the pages
(`alert-review`, `rust-sort`, `wt-merge`, the two fixtures and their `versions/*.v1.html`,
`notification-playground`, `visual-review-gallery`, `feature-gallery`,
`docs/how-it-works.html`) and the guidance (`page-authoring.md`'s workspace section,
`packages.md`'s full-height contract); delete the full-height block, the
`--lf-full-height` queries, `syncLayoutRegion` and `heldPanes`. This is the largest
step in the plan.

Without E, `lf-tabs list="side"` needs a full-height form of its own: its list and item
each scroll inside a full-height workspace body, and the item's scroller is registered
as a reading region, as a generated pane is. Today, after step 1, the whole body
scrolls with the list and the item together, which holds its rows at their height but
lets the list scroll away.

`771b3d72c` then keeps its landing rule and `.tag { align-self: center }`, and drops
`#fitList`, `--lf-list-top` and `--lf-list-view`.

Step 3: drop the bottom bar, and give the phone banner one row. Removing the bar deletes
`--lf-bottom-bar-h` and its readers (`theme.css`, `chrome.css`, `shortcut-bar.js`,
`lf-toc`), `declareBottomBar`, and the bottom edge in `shownWindow`. Its key hints move
to `?`, and its status (notices, the Go-to sequence, the walk position) to the banner,
so the phone row is designed for its final contents. The shortcut bar is how a desktop
user learns the keys without asking; moving the hints behind `?` trades that for 44px,
which is a product choice to make on its own.

## Checks

- With E: on `alert-review`, PageDown on load scrolls the page and reload restores its
  place; a margin row in a stuck region stays with its target after a root scroll; a
  landing into the queue leaves the root where it was; the playground and visual-review
  pages keep their forms.
- `uv run leaf-dev stills` against the merge base for every changed first viewport and
  banner state, on a phone too.

## Open questions

- E or pane scrollers (step 2).
- What the one-row banner holds on a phone, and what goes behind its menu. A candidate:
  the status mark alone, opening the status detail; the gesture step or Approve; Threads
  as an icon with its count; More.
- Without E, whether the side list's full-height form is worth registering its item as
  a reading region, or whether the list scrolling away with the body is acceptable.
