# Chrome, covers and widget shapes

Research on main at `5ed41df4b`, 29 September 2026, from a user review of a 21-item
triage queue page, then reviewed against alternatives at `ef3cea8b3`. The plan keeps
the document scrolling on the root, gives the banner a stated height, gives every box
that sticks over content a stated height stacked through `--lf-top`, and stops the
workspace Layout from writing inside the widget it arranges. One decision follows the
first step: whether a workspace keeps panes that scroll on their own, or its regions
stick to the root scroller instead (option E below).

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

Neither the mechanical parts of step 1 below nor the two causes of the queue failure
depend on E. So decide E after step 1, from `alert-review` built both ways in a
playground.

## The foundation

- **The root scrolls on the live page, print, export and the MCP page frame.** A live
  page adds a fixed banner and top padding of its height. A block sample is an iframe
  whose root does not scroll, so nothing sticks in it. The MCP inline snapshot renders
  the page in a shadow host inside the app's scroller, under the app's sticky 48px bar,
  and sets no `--lf-top` today; the host sets it to the bar's height.
- **The banner has a stated height:** a value CSS computes from the pointer type, the
  window's width and the page's declared sign-off (`data-lf-review`, which arrives with
  the document). What the row holds may still be measured to decide which controls go
  into its menu, since that changes the row's content and not its height; the rows
  observer and the guesses go. The banner is one row down to about 600px with Approve
  on it (`ship-review`) and about 440px without (`rust-sort`), read from
  `data-lf-banner-rows` in `leaf-dev probe`; below those it takes a stated second row.
  One row there is a separate design (step 3).
- **Covers stack through `--lf-top`.** On the root it is the banner's height; in a
  bounded region it is 0. A cover has a stated height, sticks at `var(--lf-top)`, and
  adds that height to `--lf-top` for what it covers. A custom property cannot reference
  itself, so the cover's holder passes the incoming value on under a second name, and
  only a cover's holder and a bounded region write it:

  ```css
  lf-tabs[data-lf-tabs-flow="page"] { --lf-top-outer: var(--lf-top); }
  lf-tabs[data-lf-tabs-flow="page"] > .lf-tabstrip {
    position: sticky; top: var(--lf-top); block-size: var(--lf-tabstrip-h); }
  lf-tabs[data-lf-tabs-flow="page"] > lf-tab {
    --lf-top: calc(var(--lf-top-outer) + var(--lf-tabstrip-h)); }
  ```

- **Landings keep today's two mechanisms with stated heights.** A cover over a whole
  scroller, the banner and the page tab strip on the root, goes into that scroller's
  `scroll-padding-top`, which native landings and the runtime's `landingBand` both read.
  A cover over part of the content, the diff file header, goes into `scroll-margin-top`
  on what it covers, as `lf-diff` already writes it from `--lf-head-room`, combined with
  the focus ring's room in one value. Landing already clears both on main (a diff row in
  a page tab lands at 136px, below the strip and the header); what changes is that both
  values are stated instead of measured. Moving the tab strip into `scroll-margin` fails:
  `scrollIntoView` applies the target's margin at every ancestor scroller, so a line in
  a bounded block inside a page tab landed under the strip, and every runtime landing
  reading `landingBand` would too.
- **Readings of what the user sees read the same stack.** The clip walk behind
  `shownRect`, `seenRect` and the read and arrival checks takes, at each scroller, the
  `--lf-top` computed at the box just inside it (the element itself at its own scroller,
  the inner scroller's box at each outer one) off that scroller's top. Under a stuck
  diff header an element inside that diff inherits the header's height, and an element
  above the diff is not under it. That replaces `headersByScroller`. The one scroller-wide reading,
  `visibleBand(scroller)` for the reading place (`user-place.js`), subtracts only the
  scroller's `scroll-padding`, so a place taken while a diff header is stuck counts the
  lines under the header as shown.
- **Bounded regions own the reset.** Covers stick in the root or a bounded region (a
  pane body where panes scroll, a panel, a block marked bounded), and each of those
  starts `--lf-top` from 0. A box the theme makes scroll only sideways (`table`, `pre`,
  `lf-board`, `lf-diagram`) is still the scroller for anything sticky inside it, so
  `lf-diff` pins its header only where its scroller is the root or a bounded region.
- **A Layout sets a box's outer size and whether it scrolls, never its inner tracks.**
  A widget fills the box it is given with `height: 100%` or `fr` tracks, which CSS
  resolves to content height where no height is given (probed), and keeps its
  content's minimum on both axes. A widget written that way needs no
  `--lf-full-height` query to tell it which case it is in.
- **A hit floor never removes a content minimum on the block axis.** A control a flex
  or grid container can squeeze states its block floor as padding,
  `padding-block: max(<its padding>, (<its minimum> - 1lh) / 2)`, where its minimum is
  `var(--aim-floor)` or the rule's own `max(Npx, var(--aim-floor))`, rather than as
  `min-height`. In a 60px flex column a three-line button
  with that padding stayed 88px tall where `min-height` crushed it to 44px (probed). A
  multi-line control on a coarse pointer grows by the whole padding, 12px a side at a
  20px line. Inline floors (`min-width: var(--aim-floor)` on an item in a row) stay
  squeezable; the page tab strip's `flex: none` is what holds its buttons.

## Plan

Step 1, which does not depend on E:

- Compute the banner's row count in CSS from the pointer type, the width and the
  declared sign-off, and delete the rows observer and the guesses.
- Give the page tab strip a stated height, one row that scrolls sideways with its
  scrollbar hidden. A hidden scrollbar leaves a mouse with a vertical wheel no way to
  reach a tab past the edge, so the strip needs a pointer route: edge buttons, or the
  tabs it cannot show in an overflow menu. Give the diff file header one line, its path
  ellipsized at the start so the file name stays, with the whole path on hover or focus.
- Stack covers through `--lf-top`, put the tab strip's stated height in the root's
  `scroll-padding-top` and the diff header's in its rows' `scroll-margin-top`, and
  delete `declareStickyHeaders` (with `lf-diff`'s `declareHeadRoom`),
  `headersByScroller`, `measureUnseenHeaders`, `insetBand`'s sticky-inset case and
  `--lf-root-tab-clear`.
- Make `lf-diff` hold its file header as a cover: each file's body sets `--lf-top` to
  the incoming value plus the header's stated height, and its rows' `scroll-margin-top`
  derives from the header's height with the focus ring's room.
- Set `--lf-top` on the MCP inline snapshot's host to the app bar's height.
- Move the `--lf-top` reset from the two workspace rules to the bounded-region
  primitive, so a `data-bound` block gets it too, and pin a diff header only where its
  scroller is one of those or the root.
- State the hit floor as padding in each rule, of the twenty (twelve that read
  `var(--aim-floor)` alone, eight that read `max(Npx, var(--aim-floor))` in
  `chrome.css`, `theme.css`, the visual-review, playground and swipe themes and
  `diff/shadow.css`), whose control a flex or grid container can squeeze. The page-flow strip's `flex: none` stays, since it keeps a tab
  from shrinking along the row and cutting its name; the side list needs no second copy.
- Apply the workspace's row rule only to a body that holds panes
  (`:has(> [data-lf-reading-role="pane"])`), and give `lf-tabs list="side"` one form
  that fills a definite height and takes its content's otherwise. On a flowing page its
  list sticks at `var(--lf-top)` with the root's view as its maximum; inside a pane body
  it stays in flow until the open question on its height there is settled. E replaces
  this form in step 2 if chosen.

`771b3d72c` then keeps its landing rule and `.tag { align-self: center }`, and drops
`#fitList`, `--lf-list-top` and `--lf-list-view`.

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

Step 3: drop the bottom bar, and give the phone banner one row. Removing the bar deletes
`--lf-bottom-bar-h` and its readers (`theme.css`, `chrome.css`, `shortcut-bar.js`,
`lf-toc`), `declareBottomBar`, and the bottom edge in `shownWindow`. Its key hints move
to `?`, and its status (notices, the Go-to sequence, the walk position) to the banner,
so the phone row is designed for its final contents. The shortcut bar is how a desktop
user learns the keys without asking; moving the hints behind `?` trades that for 44px,
which is a product choice to make on its own.

## Checks

- The queue page from the user's review, written as `page-authoring.md` prescribes,
  passes `page check --render`.
- The diff-in-tab probe above reads the diff header starting at the strip's foot.
- A fragment, a Go-to travel and a thread landing into a diff line inside a page tab,
  and into a line of a bounded block inside a page tab, each land below every cover.
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
- Without E, the visible height a sticky side list takes as its maximum inside a pane
  body. A pane body the workspace sizes can be a size container (`100cqb`); a generated
  pane sized by its content cannot, since size containment collapsed one in
  `notification-playground` from 158px to 28px.
