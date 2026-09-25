# Margin markers in a rail or as pins

Plan written 24 September 2026 against main `3be3a1cd1`. It assumes two pushed branches
land first:
- `fixed-rail` makes the rail's width a theme constant, `--rail` ≈ 95px. A page takes the
  rail once the shell is 863px wide, or 887px with a coarse pointer.
- `asks-tray-overlay` makes the Asks tray and Threads stand over the page instead of
  narrowing it.

It implements the section "The margin as a rail or pins" of `notes/layout-approach.md`
on the branch `how-it-works-one-layout` (called "the proposal" below). It holds Leaf to
that note's rule: nothing Leaf draws at run time moves the page's content.

**Status:** Max approved the plan on 24 September, with the decisions recorded under
"Decisions" below. `fixed-rail` has landed (#1140). Phase 1 starts once
`asks-tray-overlay` (#1148) lands.

Browser claims marked *probed* were run in Chrome 153 (the suite's headless shell) and
are summarized in the appendix.

## Terms

- The **shell** is `body`'s content box, the width Leaf's responsive rules ask about.
- A **marker** is the visible face of a margin cluster: one per annotated target,
  gathering its threads, Asks, changes, receipts, claims and contributed controls. A
  **contributed control** is one a package puts there, such as a suggestion's
  Accept/Reject or a draft's Save/Cancel.
- A **band** is the vertical span a marker occupies on the page.
- The page's right **gutter** is the strip between the shell's right edge and the
  furthest any content may reach: `--lf-gutter-r` wide, at least 24px, and wider where a
  strip is reserved. `main`'s right padding lies inside the room content may use, not in
  the gutter.
- A **reading region** is a box Leaf tracks the reader's place in, such as a pane's body.
  It is **bounded** when it scrolls on its own. A **lane** is the layer holding the
  markers of one bounded region.
- A **withheld** row is hidden because its target isn't shown (a closed `details`, an
  inactive tab, scrolled out of its pane).
- The **`Map` door** is the banner button that opens the Page Map dialog, the searchable
  list of every marker. The banner shows it where markers are hidden today.
- A **shadow stage** is a shadow root Leaf renders content into (a widget's own DOM); it
  adopts `marks.css` separately from the document.
- The **look pass** (phase 1) renders the open visual candidates for Max to choose from
  before the main change lands.
- A **grown block** is a wide figure: a box wider than the column, grown into the free
  room beside it with negative margins.
- A **frame** is a box declaring `--lf-block-frame: 1`: `main`, pane bodies, cards, grid
  cells, callouts, `details`. A wide block inside one fills it instead of growing out.
- **Anchor positioning** is the CSS feature that places one element relative to another
  (`anchor-name` on the target, `position-anchor` and `anchor()` on the placed element).
  The placed element's **containing block** is the box its `top`/`left` are measured
  from, and it must not sit between the target and the root in a way the spec forbids:
  in practice, a placed element inside a *positioned* wrapper can only anchor to things
  inside that wrapper. Anchor names don't cross shadow-root boundaries.

## The plan in brief

- A margin row has two postures, **rail** and **pin**, and never docks into the text.
  - The rail is a strip the page reserves beside its column.
  - A pin is a marker drawn over the page at the right edge of its target's block. Pins
    are used where there is no rail: the page declared none, the window is too narrow, or
    the target sits in a pane that scrolls on its own.
- Every row lives in the chrome and is tied to its target by anchor positioning.
  - A pane's scrolling moves its pins with no script.
  - Leaf inserts nothing into the page's content.
- A rail marker stands 22px past the column. A marker whose own block has grown past the
  rail's inner edge stands as a pin on that block. No block is resized for a marker, so
  `data-lf-yield` goes.
- Column pages have a rail; every other page (sheets, and so workspaces) has pins.
  `data-rail="right" | "none"` on `main` overrides either default.
- `o` shows or hides the annotation layer: everything Leaf draws over the page's content
  (pins, controls included, the durable marks on anchored passages, an open card). The
  rail covers nothing, so what stands in it stays. The layer is tab view state, and
  hiding it changes no geometry, because nothing in it takes up room.

## What the user sees

| Case | Today | Planned |
|---|---|---|
| Column page, shell ≥ 863px | Markers stand 22px past the column. A wide block level with a marker grows left only | Markers stand 22px past the column. A comment on a figure that grew past the rail is a pin on the figure's right edge. Figures keep their shape |
| Column page, shell < 863px | Reporting markers are hidden and the banner shows a `Map` door. Clusters with contributed controls (a suggestion's ✓/✗, lf-draft, lf-shot) dock into the text as a line of their own | Pins beside their blocks, reaching into the page's right gutter. Between 768 and 862px a pin covers nothing. Below 768px the gutter is 24px, so a 32px pin covers 8px of text, or 20px under touch. The `Map` door stays |
| Sheet or workspace | A rail at the sheet's far edge, possibly hundreds of pixels from the card a marker is about. Markers in panes dock into the pane | No rail by default, so a sheet gains up to 95px where the rail limited it. Pins stand on their blocks, and a pane's pins scroll with the pane and are clipped to it |
| A cluster unfolds (`…`, reaction choices) | Borrows room to the right, else docks | In the rail it unfolds rightward, as today. As a pin it unfolds leftward over its block until closed |
| `o` pressed | — | Reporting markers and durable marks disappear. Contributed controls and all geometry stay |

## Decisions

Each section gives the options considered, the recommendation, and why.

### A. How a page declares the rail

The user asked whether the rail could be "a widget". A rail holds no content: it is the
projection of what is anchored elsewhere, and its markers must stand level with their
targets. A grid track the agent lays out could promise that only by spanning exactly the
content beside it. So the rail is declared, not placed.

| Option | For | Against |
|---|---|---|
| `data-rail` attribute on `main` | Matches `data-width`, the page-level attribute agents already write. It is in the first paint, the theme reads it in the rail's selector, and `version check` can read it statically | — |
| `<lf-rail>` element as a column of the agent's layout | Reads as "a region of the page"; could serve a pane | Every custom layout must lay out a Leaf element correctly, and a rule must map targets to rails |
| CSS property (`--lf-rail: none`) | Lives in the agent's CSS | The claim is computed on `main` itself, and a container query cannot style its own host, so it needs numeric switch arithmetic. Invisible to the Python side |
| Inferred from the page's form, with no override | Nothing to learn | A column page cannot give its right margin to its own notes; a sheet with a prose body cannot keep the rail |

**Decided** (24 September): default by the page's form, overridable by one attribute.
Max: "the agent decides … we should do the simplest thing and then we can adjust
later".

- **Column page** (`main` without `data-width="wide|available"`): rail.
  - A document read top to bottom is where a marker beside each passage reads best, and
    its centred column leaves room.
- **Sheet**, and so a workspace, which is a sheet's only block
  (`packages/default/theme.css:204-216`): pins.
  - On a sheet the rail can stand hundreds of pixels from the card a marker is about.
  - A workspace's panes scroll on their own, so their markers are pins anyway.
- **No further inference.** A column page with right-hand `aside.sidenote`s keeps the
  default rail. The notes and the rail claim the same strip (`--strip-r` takes the wider
  of the two, `theme.css:694`), and markers stand over notes (`theme.css` ~1313), so an
  agent that hangs notes on the right writes `data-rail="none"`. `page-authoring.md`
  says so beside the numbers below.
- **Overrides:** `data-rail="right"` and `data-rail="none"`. A left rail would be a new
  feature, not another value.
- **Panes:** never a rail of their own. The mechanism is keyed on a region, so a pane
  could later declare one as another value on the same axis.
- **Telling the agent:** `page-authoring.md` states the numbers once:
  - the rail's width is `--rail`, and it appears at 863px of shell;
  - markers stand 22px past the column;
  - nothing Leaf draws moves the page's content;
  - a pin stands beside a block if 32px of padding is free there, and otherwise covers
    what is missing, at the block's top-right.
- **Name collision:** `page-authoring.md:119-129` also calls a sheet's side track "a
  rail"; rename it "side track".

### B. How rail markers meet wide blocks

The reservation is taken at the page's far edge, and the column centres in what is left.
So the free room beside the column (`--lf-free-r`, 268px at a 1400px window) lies between
the column and the reserved strip. Markers stand 22px past the column, inside that room,
which is why a figure growing right is made to yield today.

| Option | Result |
|---|---|
| **B1.** Wide blocks stop short of the rail (the proposal's wording) | Every figure on every rail page grows left only, off the prose axis, whether or not a marker stands near it |
| **B2.** Markers stand in the reserved strip at the far edge | Nothing collides, but a marker stands 290px from its passage at 1400px and 450px at 1728px |
| **B3.** A marker whose own block reaches past the rail's inner edge becomes a pin on that block | Figures stay centred, and a comment on a figure lands on it. The rail column stays straight. The pin covers the figure's top-right corner |
| **B4.** A marker steps out to 22px past the widest grown box in its band | Figures stay centred, and a resting marker never covers content. Markers zigzag beside figures |

**Recommendation: B3.**
- It reads one rectangle, the row's own block, so it follows an agent's own CSS as well
  as Leaf's declared widths.
- B4 couples a marker's position to *other* blocks through the band scan that yield
  uses today, moving the marker instead of the figure. A paragraph's marker packed 36px
  down beside a figure steps 180px right at 1440 and reads as the figure's.
- B4's scan sees only declared widths (`[data-lf-space]`, `[data-width]`). A block an
  agent widened with its own CSS still collides.
- B4 ignores floats, so a `data-rail="right"` sidenote page still draws over the note.
- B4's "never covers" holds only while a cluster is folded.

**The rule, stated for the implementer:** a row is a pin when its block's right edge,
less half a marker, passes the rail's inner edge (`main`'s padding-box right + 22px).
- A sheet's blocks end at `main`'s edge, so on a `data-rail="right"` sheet the rail always
  wins.
- A figure grown past the column loses it.
- A marker packed down into a *following* figure's band keeps its own posture and may
  stand over that figure's corner. The user can hide it with `o`.

If the stills favour B4 instead, it is feasible. Under `fixed-rail` a grown block ends at
or left of the gutter, the gutter is at least `--rail` wide, and a resting cluster needs
22 + 68 + 5 = 95px (the 22px hang, two 32px entries and their 4px gap, and the focus
ring's room). So it fits at every shell from 863px up, with nothing to spare at 863. Under
touch the entries are 44px and the rail widens with them to 119px, so the same holds. This
was worked from the theme's formulas at 900, 1200, 1440 and 1920 for columns and sheets,
and the formulas matched measurements on main.

### C. Where a pin stands and how it looks

**Anchor box.**
- A pin anchors to its target. For a passage, the target is already the block holding
  the passage's first segment (`anchor-resolution.js:497`), so the pin stands level with
  the block's top, as the rail marker does today.
- CSS cannot anchor to a range of text. Standing at the passage's own line would need a
  layout-time offset, and two passages in one block share one cluster anyway. Not
  planned.

**Horizontal** (recommended: the room rule).
- The pin stands `min(32px, room)` past its block's right edge, and covers whatever the
  room lacks.
- For a block directly in `main`, room runs from the block's right edge to the shell's
  right edge. Content never enters the gutter at the end of it, at any width, in columns
  or sheets (*probed*). `main` differs from other frames here because a sheet has no
  inline padding, and on a column page grown blocks use `main`'s padding between 769 and
  862px of shell.
- For a block inside any other frame (a card, a cell, a pane body), room is that nearest
  frame's inline-end padding. Only the nearest frame counts: climbing past a grid cell
  with no padding to the pane beyond would put a left cell's pin on the right cell's
  content.
- Results: a prose pin covers nothing between 768 and 862px, and 8px below 768px (20px
  under touch). A card's pin covers what the card's padding lacks. A grid cell's pin
  straddles the cell's edge.
- The look pass compares two alternatives. **Straddle** centres every pin on its block's
  right edge (16px over the content), with no room reading. **Inside the corner** puts a
  24px pin wholly inside the block's top-right.

**Size and face.**
- With a mouse the pin is the rail's 32px marker face.
- Under a coarse pointer `--margin-entry` is 44px (`theme.css:404`), wider than the 24px
  gutter. Either the pin covers 20px of text on a phone, or it shows a smaller face with
  a 44px hit area that reaches over the text. The look pass decides.
- The count badge moves inside the pin's box on its left. At the window's edge,
  `overflow-x: hidden` clips a badge placed at `right: -7px`.

**Clusters.**
- The resting budget (two entries, the second of which may be `…`,
  `margin-model.js:7`) applies in both postures.
- A pin cluster is right-aligned to its spot and unfolds leftward over its block.
  Unfolding rightward would run it into a pane's clip and off a sheet's edge.
- An `lf-suggestion` shows ✓ and ✗ as its two resting entries, as in the rail. Inside a
  pane they cover the last words of the suggestion's first line.

**Collisions.**
- Rows are packed as today, by priority and then top, but by rectangle overlap rather
  than by band, because a pin and a rail marker at the same height do not collide.
- Different targets are not merged into one count marker. Merging would break
  one-marker-per-target and the `t` walk.

**Author controls.** A pin over a card's corner button takes the press until `o` hides
the layer, unless the pin holds a contributed control (E).

### D. Mechanism

| Option | For | Against |
|---|---|---|
| **Anchor positioning** | Scroll tracking runs on the compositor, in panes and the document alike (*probed*). Leaf already uses it (`chrome.css:591-625`; `lf-gloss.js:64-66` writes `style.anchorName` on authored content) | Unique anchor names at the Chrome 125 floor, which has no `anchor-scope`. Invalid anchors need an explicit fallback. Contributed controls leave the content's tab order |
| **JS-measured overlay** (today's `place`, plus scroll listeners for panes) | Works in any engine | Scroll events arrive after the compositor has moved the content, so pins lag and snap. It needs a scroll owner per region |
| **Absolute children inside content** (today's external hosts, without docking) | Native scroll and clipping; tab order stays local | A runtime node inside authored content, with `inBlockFlow`'s grid, flex and `:only-child` problems. `contain` and `overflow: hidden` clip the pin |

**Recommendation: anchor positioning.**

**DOM.**
- `nav.lf-margin-projection` stays the one owner, appended to `.lf-chrome`. It becomes a
  static, zero-height block, and its `.lf-margin-toolbar` is unpositioned too. A
  positioned wrapper would make every anchor outside it invalid (*probed*).
- The nav holds the root lane (`.lf-margin-toolbar`, for rows whose targets scroll with
  the document) and one `.lf-margin-lane` per bounded reading region.
- A lane clips its pins to its region's shown bounds, widened by the focus ring's room,
  with `clip-path`. That clips painting and hit testing without making the lane a
  containing block (*probed*).
- The clip is in the lane's coordinates, so it goes stale whenever the region moves or
  resizes. It is recomputed on every layout pass and by a `ResizeObserver` on each
  region's host.
- Every row, whether it holds contributed controls or not, lives in a lane.
  `data-lf-external`, `externalPerch`, `inBlockFlow`, `moveExternalHost` and
  `externalDocks` go.
- `.lf-margin-inline` hosts for targets inside chrome (`syncInlineOffers`) are not rows
  and stay.

**Anchors.**
- The layout pass gives each row's anchor element a name `--lf-a<n>`, merged with any
  `anchor-name` the author set (*probed*: the author's name survives).
- The pass writes the row's `style.positionAnchor` inline, as the probes did.
- The anchor element is the target, or its shadow host when the target is inside a
  declared shadow tree, since names don't cross shadow roots (*probed*). For a
  `display: contents` target it is the first shown part.

```css
.lf-margin-cluster {
  position: absolute;
  /* Level with the anchor, pushed down by packing. */
  top: calc(anchor(top, -9999px) + var(--lf-push, 0px));
  /* Hidden once the anchor's scroller fully clips it. */
  position-visibility: anchors-visible;
}
.lf-margin-cluster[data-lf-place="rail"] {
  /* 22px past the column; unfolds rightward. */
  left: calc(anchor(--lf-page right, -9999px) + var(--rail-hang));
}
.lf-margin-cluster[data-lf-place="pin"] {
  /* Right edge --lf-dx past the block's right edge; unfolds leftward. */
  right: calc(anchor(right, 9999px) - var(--lf-dx));
}
```

`main` carries `anchor-name: --lf-page`. Every position function has an off-screen
fallback for an invalid anchor (*probed*, including the pin's `right`).

**Invalid anchors.**
- `position-visibility: anchors-visible` does not hide a pin whose anchor is invalid:
  missing, `display: contents`, or inside `content-visibility: hidden` (*probed*: the pin
  was drawn where it would sit with no positioning, and took presses).
- This happens routinely. `lf-tabs` hides inactive tabs with `content-visibility:
  hidden`, and closed `<details>` do the same.
- So each position function carries a fallback that parks the pin off screen
  (`anchor(top, -9999px)`, *probed*).
- The layout pass also marks a row withheld when its target has no shown part, which
  takes it out of the tab order. `checkVisibility()` does not report
  `position-visibility`, so withheld is Leaf's own reading.
- A scroll inside a bounded region re-takes that reading for that region's rows only
  (rAF-coalesced), so a long page does not pay a forced layout per scroll frame.

**The layout pass** (`layoutMarginRows`, rewritten) reads everything first and then
writes, as today. It runs on body resize, on each margin render, and on a scroll inside a
bounded region. For each row:
1. **Lane.** The innermost bounded reading region containing the target, or else the
   root.
2. **Withheld.** The target has no shown part inside its region.
3. **Posture.** Rail when `railStands()`, the row is in the root lane, and its block
   doesn't pass the rail's inner edge (B). Otherwise pin.
4. **Offset.** A pin's `--lf-dx` comes from its nearest frame's room (C).
5. **Packing.** After one layout, read the row rectangles, pack overlaps by priority and
   then top, and write `--lf-push`.
6. **Clips.** Recompute each lane's clip.

Posture, offset and packing move into a pure module that Node tests (`tests/runtime/`).

**Unsupported browsers.** Under `@supports not (anchor-name: --x)` the layer is hidden
and the `Map` door shows. Leaf's floor is Chrome 125, but leaf.page serves the examples to
any browser. By the support tables (not probed), Firefox 147 and Safari 26.2 support
everything used here.

**Tab order.**
- Rows in the chrome come after the content in tab order, as reporting markers already
  do.
- A suggestion's ✓/✗ therefore leaves the content's sequence near its target. The routes
  that remain are the roving margin toolbar, standing on the target, `t`, and the Page
  Map.
- This is the cost of inserting nothing into the content (decision #4).

### E. The `o` toggle

**What the annotation layer is** (decided 24 September, Max's rule): everything Leaf
draws over the page's content. The rail covers nothing, so it and everything standing in
it stay. The rule keys on a row's posture, so no cluster's entries need sorting into
reports and controls.

**Hides**
- Every row in the pin posture, whatever it holds. A contributed control standing as a
  pin hides with it: an lf-draft's Save and Cancel (`lf-draft.js:388-400`), or an
  lf-suggestion's Accept/Reject, which is an Ask (`lf-suggestion.js:305-316`). The
  decision stays reachable through the requests below.
- The durable passage marks `lf-mark` and `lf-react`, and element contours in the
  comment and reaction states.
- An open card, and an unfolded cluster standing over the column.

**Keeps**
- The rail and every row standing in it.
- Standing and gesture paint: `lf-mark-here` (the thread the user opened), `lf-pending`
  (the user's own draft), and the aim and trace boxes.
- Version comparison paint, which has its own toggle.
- A suggestion's insertions and deletions, which are the widget's content.
- The card, Threads, the Asks tray and the Page Map.
- The accessible comment notes, since hiding is visual.

**Mechanism**
- `html[data-lf-annotations="hidden"]`, with one writer: `margin-projection.js`, which
  owns the layer.
- The durable highlight colours become tokens (`--lf-mark-*`) that the attribute sets to
  transparent. A custom property set under the root attribute reaches `::highlight()`
  inside the shadow stages that adopt `marks.css`, while a `:root[…]` selector in those
  stages cannot (*probed*). Highlight registration is untouched.
- `markAt` (`anchor-paint.js:158`) returns nothing while hidden. Its two callers are
  hover paint (`:186`) and the press that opens a thread (`composing/surface.js:1453`), so
  an unseen passage shows no hand cursor and opens nothing when pressed.
- On hiding, focus held by a pinned row moves to its target (`focusDestination`),
  because hiding a focused element sends focus to `body` (*probed*). An open card closes
  through its ordinary close path.

**While hidden**
- Explicit requests still work and show what was asked for, without revealing the layer.
  The `t` walk, a Threads row and a Page Map pick all go through `openPageThread`
  (`margin-projection.js:2594`), which opens the card at the target and paints
  `lf-mark-here` on the passage. An `a` arrival at an Ask whose control is a hidden pin
  shows that one row. `c` composes as usual.
- The banner's unread count and the bottom-line notices of new replies don't read the
  layer, so they keep announcing arrivals. A message not shown is not marked read.

**Persistence.** A `tabStore` key beside the design-mode key, listed in
`USER_VIEW_RESTORE_CASES` and restored by `restoreUserView`. It is not `userStore`: a
standing "never show markers" would hide arrivals on every page. That belongs to the
user-preferences mechanism if it is ever wanted.

**Command.**
- `annotations.toggle` on `o`, placed in `PAGE_COMMANDS` after `design.mode.enter`.
- `o` is unbound in every scope. It is only a generated hint letter while `g` or `s` owns
  the keyboard, and those sequences take every key.
- Its shortcut line reads "hide annotations", or "show annotations" while they are
  hidden. It announces through `notice`.
- Figma, FigJam and Miro use Shift+C. Leaf's page keys are single letters, and `c` is
  taken.

**Glossary**
- Add **annotation layer**, **pin** and **contributed control**.
- Margin row placement becomes `rail`, `pin` or `withheld`; *docked* goes.
- Rename **pinned cover** (glossary :84, a sticky box declared through
  `declareCoverRoom`) to **sticky cover**, so *pin* means one thing.
- `o` is a toggle, not a mode: the glossary reserves *mode*.

### F. The thread card and the Page Map

- **The card.** Its geometry (`thread-card-geometry.js`) is unchanged. Beside a pin there
  is rarely the card's 320px minimum, so the card stands under or over the pin, with its
  right edge on the visible edge, inside the region when in a pane. That is today's
  behaviour for a docked or withheld row. During a pane scroll the card, still placed by
  script, trails its pin by a frame.
- **Threads over the rail.** Unchanged. Today `chrome-layout.js:111-124` notices when
  the panel covers rail markers (below about 1700px) and shows the `Map` door
  (`data-lf-rail-covered`). Flipping those markers to pins would not help, because a pin
  stands at the column's edge, which the panel covers at the same widths. Threads itself
  lists every thread while it is open.
- **The Page Map.** The compact-width `Map` door stays. On a phone, pins are small
  targets over content, and the searchable map is the better route. `g M` opens it at any
  width.

## Implementation

### What goes

All of this goes in phase 2.

- `margin-layout.js`:
  - docking: `dockedAgainst`, the `staysDocked` pre-read, and the `dock`, `float`,
    `hangs` and `fallback` options;
  - `reserveRail` and `data-lf-rail`;
  - the re-place after docking;
  - the yield sweep.
- `margin-projection.js`:
  - `measureMargin`;
  - `changePosture`'s hand-off of focus to the map, since markers no longer vanish when
    the rail falls;
  - `markerOptions`' `hangs`, `float`, `dock`, `fallback` and `place`;
  - `externalPerch`, `inBlockFlow` and `moveExternalHost`;
  - the split in `renderNow` between reporting clusters and clusters with contributed
    controls;
  - `reserveRail()` in `mount`.
- `theme.css`:
  - `.lf-margin-cluster.lf-docked` and its options rule (1633-1648);
  - the compact `display: none` of the projection;
  - the `:root[data-lf-rail]` selector half;
  - the coarse `margin-left`;
  - the yield block (1906-1924).

### Contracts and documents that change

- `skills/leaf/assets/AGENTS.md`: the "Margin placement" owner row, and "Keep annotation
  access and visible residents clear of expanding content", which is the yield rule in
  prose.
- `references/packages.md` (`registerMarginContribution`): a contribution stands in its
  target's cluster in either posture, and as a pin its cluster unfolds leftward.
  Under `o` a contribution hides when it stands as a pin and stays in the rail.
- `references/page-authoring.md`:
  - a short section on the rail and the annotation layer (see A);
  - the side-track rename;
  - the "occupied margins" wording at :158-161.
- `registry.json` `x-space`: the rail is no longer a "margin resident".
- The glossary (E); the How it works page, if it names docking.
- `examples/developer/feature-gallery.html`:
  - a pin specimen (a commented block in a bounded pane);
  - an `o` specimen beside `#bg-margin-controls`.
  - Regenerate the corpus.

### The render gate

- `coveredWords` skips everything under `.lf-chrome` (`words.js:201`), so it cannot see
  pins.
- Moving contributed controls out of `main` also removes them from `marginReading`'s
  residents (`layout.js:58`), so the gate would stop seeing marker/exhibit collisions.
- Add one reading that intersects the marker layer's rectangles with word runs and with
  exhibits, and reports what they cover as a count. Covering is expected (a pin, or a
  packed marker over a following figure), so it is a reading for the agent to look at,
  not a fault.
- Check that no row stands at its off-screen fallback while its target is shown.

### Tests

About 69 references to docking, yield, withheld rows or the `Map` door, in 10 files:
- `test_render_margin.py`
- `test_render_navigation.py`
- `test_render_widgets.py`
- `test_render_pages.py`
- `test_render_gate.py`
- `test_render_controls.py`
- `test_render_reactions.py`
- `test_render_conversations.py`
- `test_site.py`
- `render_cases_widgets.py`

Also changing:
- `tests/runtime/margin-model.test.mjs:257`;
- the two pane tests (`test_render_navigation.py:382`, `test_render_widgets.py:919`),
  which become pin assertions.

New:
- Node folds for posture, offset and packing.
- A pin tracks its pane's scroll with no layout pass, is clipped at the pane's edge, and
  is withheld once its target leaves.
- A pin inside an inactive `lf-tab` is parked and unfocusable.
- A commented wide block keeps symmetric growth, and its marker is a pin on it.
- `o` leaves every authored box's rectangle unchanged, keeps the rail's rows, hides every pin, and
  a press on a hidden passage opens nothing.

## Phases

Phases 2 to 4 each land on their own and leave the app coherent.

0. `fixed-rail` and `asks-tray-overlay` land.
1. **Look pass.**
   - In the phase-2 branch, put the open visual candidates behind one temporary switch:
     - pin room rule vs plain straddling vs inside the corner;
     - the touch face;
     - B3 vs B4.
   - Render `review-a-plan` (a column with wide blocks, with a comment on one),
     `triage-board` (a sheet) and `alert-review` (a workspace with panes) at 1440, 1000
     and 800px, and at 390px with a coarse pointer.
   - Hand the stills to Max on a Leaf page. The switch is deleted before landing.
2. **Pins replace docking.**
   - Covers the static layer, lanes, anchors, withheld, B3's posture rule, packing, the
     `@supports` fallback, the deletions (docking and yield), the gate reading and the
     tests.
   - The largest phase, roughly −600/+400 lines (*estimate*).
3. **The rail is declared (A).**
   - `data-rail`, and the sheet default.
   - `page-authoring.md` and the glossary.
4. **`o` (E).**

Phases 3 and 4 are independent of each other.

## Risks and probes still open

- **Cost.** The margin re-renders every two seconds while a page is live. Measure a
  200-marker page before and after, on that render and on a pane-scroll trace, following
  the phase-profile guidance in `AGENTS.md`.
- **Revisions.** Check whether the in-place revision patch (`version.js`) clears a
  runtime `style.anchorName` on an authored element, and whether the next layout pass
  restores it before paint.
- **Nested panes.** A pane inside a bounded pane needs the inner lane's clip to be the
  intersection of both regions' shown bounds.
- **Sticky targets.** A target in a sticky box (`aside.sidebar` at ≥ 1188px) makes pack
  offsets stale as it sticks. Probably leave such targets unpacked.

## Decisions

- **#1 — Wide blocks:** decided, B3 (the marker on a figure grown past the rail is a pin
  on the figure). B4 stays the look pass's alternate.
- **#2 — Defaults:** decided: column pages have a rail, every other page pins, and the
  agent overrides with `data-rail`; no sidenote inference.
- **#3 — Pin look and touch size:** decided on the look pass's stills.
- **#4 — Tab order:** decided: contributed controls (a suggestion's ✓/✗) move after the
  content in tab order, the price of inserting nothing into the page.
- **#5 — `o`:** decided: it hides everything drawn over the page, pinned controls
  included, and keeps the rail. It is tab state. Explicit requests (`t`, `a`, Threads,
  the Page Map) show what was asked for without revealing the layer.
- **#6 — Declared, not placed:** decided, an attribute on `main`.

## Appendix: probes

All runs in Chrome 153 headless:

- **Tracking.** A pin with `position-anchor` to a paragraph inside an `overflow: auto`
  pane, placed in a non-positioned layer so it resolved against the initial containing
  block or `main`:
  - It followed a 60px and a 400px pane scroll, and a 200px document scroll, with no
    script.
  - With the layer itself positioned, the anchor was invalid and the pin sat at the
    layer's origin.
- **Clipping.** With the target scrolled out of the pane, `position-visibility:
  anchors-visible` removed the pin from hit testing, while `checkVisibility()` still
  returned true. With the target partly clipped, the pin hung over the pane's header.
  Moving the pin into a zero-height, non-positioned layer with `clip-path: inset(…)`:
  - clipped its paint and hit testing at the pane's edge;
  - left `main` as its containing block.
- **Invalid anchors.** An anchor inside a shadow root, a `display: contents` anchor, and
  an anchor inside `content-visibility: hidden` content were all invalid. The pin drew
  where it would sit with no positioning, and took presses. `anchor(top, -9999px)`
  parked it off screen. `anchors-valid` is unsupported.
- **The pin's edge.** `right: calc(anchor(right, 9999px) - 20px)` put a pin's right edge
  20px past a block's right edge (600 → 620), with `20px` or a custom property. With a
  missing anchor it parked the pin off screen.
- **Name merging.** A runtime-written `anchor-name` merged with an author's
  (`--by-author, --bt`), and both resolved.
- **Highlights in shadow stages.** Inside a shadow stage, `:root[data-off]
  ::highlight(x)` did not match. A custom property set under `:root[data-off]` and used
  by the stage's `::highlight(x)` rule did change the highlight.
- **Content in the gutter.** On ship-review with injected wide blocks, tables, a long
  `pre`, an image and a long URL, measured at 390, 700, 800, 840 and 1440px:
  - Grown blocks entered `main`'s right padding at 800 and 840px (by 16 and 36px).
  - At 840px they ended at the gutter's edge (the shell's right edge less
    `--lf-gutter-r`), which is where the theme's formulas hold every grown block at
    every width.
  - A sheet has no right padding at any width.
