// `syncLayout` derives only floating chrome placement and reservations from current
// chrome boxes. CSS owns the document shell: `body` is the named `lf-shell` inline-size
// container, `main` composes its left and right claims, and queries grant or withdraw
// margin postures. JavaScript may hear the shell's content-box size without deriving a
// posture or mirroring cramped state. `layoutSizes` schedules `syncLayout` and page
// repaint after a width change. `moveContentFrame` lands the final responsive shell in one pass,
// then animates only the reading column's presentation offset and repaints page-attached
// chrome along that route. A height-only change sends `pageShifted` directly so a content
// reflow re-places document-attached paint without re-running chrome reservation.
//
// `syncLayout` measures only chrome whose placement or reservation depends on rendered
// chrome, and writes only chrome boxes. `layoutSizes` watches `document.body`'s
// content-box size without deriving a posture from it. A width change schedules
// `syncLayout` and page repaint in the following frame after an auxiliary surface lands its final
// shell; a height-only content reflow calls `pageShifted` during observer delivery so
// page paint follows targets that moved. That direct path may write only unobserved paint
// hosts and state or queue work for a frame. A `ResizeObserver` callback must not resize
// the box it observes, directly or through a class or attribute that changes that box.
//
// The browser's root is the document scrollport. `pageScroller` is the shared answer for
// reading position and paging; native fragments, history restoration, wheel/touch input,
// and browser UI all use that same root. Root scroll events are reported on `document`,
// while nested scrollports report on their elements. Use `scrollerFor(el)` where a widget
// may be one an agent sent, since a widget in a message is scrolled by the panel's own
// list and by nothing else. Threads and trays are alternate auxiliary surfaces, so only
// one stands at a time. The strip-taking auxiliary surfaces—Threads and Asks—take room when the
// viewport can hold them and cover the page under their respective media query otherwise;
// Leaves always covers because its rows leave this page. Auxiliary modality is a shared
// inert boundary outside this geometry owner; the reference and Page Map keep native
// `showModal()`. The shell's
// inline size already reflects the margins a beside panel or tray takes. `--strip-l`, `--strip-r`,
// `--lf-room`, and `--lf-sidebar-posture` are CSS-owned readings resolved on `main`, which is
// the named `lf-content-frame` style container a margin resident asks for them; `--lf-shell-inset-left`
// carries the left auxiliary-surface offset to viewport-fixed page furniture, and `--lf-bottom-chrome-clear`
// carries the bottom chrome's band to whatever has to end above it; `--lf-claim-right` is the
// project-layer extension claim. A script-free copy therefore answers the same layout
// from its own viewport without exporting session geometry.

// Application composition supplies feature-local geometry. This owner cannot open
// auxiliary surfaces, send commands, or reconcile conversation DOM.
import { drawnEdge } from "./drawn-edge.js";
import { motion } from "./motion.js";

// The width the panel stands at for a reader who has not moved its edge. 420 since
// threads carry questions — option rows are the one thread content that can't scroll or
// scale its width away, and 360 crowded them. A default rather than the width, because
// what a conversation needs is a fact about the conversation: a thread quoting a table
// wants room the same thread quoting a sentence does not, and only the reader looking at
// it knows which this is. So the edge is a thing they take hold of (`drawnEdge`), and
// this is where it stands until they do.
//
// Opening or closing an auxiliary surface calls its state setter and schedules the shared layout
// and key paint. Reader gestures remember their intent; an ephemeral developer replay
// uses the same transition without replacing it.
export const THREAD_PANEL_W = 420;
// How narrow they may draw it in. 320 is the narrowest window the panel is held to
// standing up in (test_a_thread_gives_its_reply_the_full_row_and_its_actions_the_next),
// so it is the narrowest width anything has laid a thread's reply box and its two
// actions out at; below it nothing says they still fit. Wanting the panel gone is what
// closing it is for, and narrowing it to nothing is not the same wish.
const THREAD_PANEL_MIN = 320;
// The window under which yielding the strip is worse than being covered by it, as a
// query rather than a number, because three things ask it: the rule that takes the strip,
// the rule that hands scrolling to the sheet instead, and the runtime, for what follows
// from which of those the page is under. Written as the covering half, since that is the
// half the runtime asks about; the strip is its complement, spelled `not` where it is
// taken.
//
// Asked of the default width and not of the reader's own, so widening the panel can never
// flip the posture out from under the hand doing it: a panel dragged past half its window
// would otherwise stop standing beside the page and cover it instead, which is the whole
// page rearranging itself in answer to one pixel of a drag. What the reader's width does
// answer to is the edge's own `cap`, which holds it to the same bargain this line
// strikes — the page keeps at least what the panel takes — without putting the posture
// itself in play.
export const COVERING = `(width <= ${THREAD_PANEL_W * 2}px)`;
// Where each standing width is written, and where the cascade reads it. chrome.css
// spells the same name and the same covering width, and the layer test holds the two
// spellings equal, since a stylesheet cannot read a constant.
export const THREAD_PANEL_PROP = "--lf-thread-panel-width";

export function createChromeLayout({
  panelIsOpen,
  elements: {
    panel,
    closeBtn,
    panelFoot,
    threadsBox,
    shortcutBarEl,
    bottomStatusEl,
    chromeRoot,
  },
  foldBannerRow,
  scheduleThreadPreviewPosition,
  bottomChromeBoxes,
  reserveListClearance,
  restateTrayEdge,
  syncAuxiliarySurfaces,
  syncReactLayout,
  refreshFab,
  dockSeats,
  pageShifted,
  layoutMarginRows,
  repaint,
  repaintPage,
}) {
  let shellMotion = null;
  const panelCovers = () => panelIsOpen() && commentsEdge.over.matches;
  // Every writer here is a writer of the chrome, so nothing this function does resizes the
  // box it reads: the strip the page yields to the panel is the stylesheet's, and the strip
  // it yields to a margin idiom is stated above.
  function syncLayout() {
    // How many of the banner's controls stand on its row is a reservation taken from the
    // row's current box, so it belongs here with the rest of them and it goes first: what
    // it decides is the banner's own contents, which nothing below reads. The banner is
    // fixed, so a fold cannot resize the boxes this function is watching.
    foldBannerRow();
    scheduleThreadPreviewPosition();
    const panelBeside = panelIsOpen() && !panelCovers();
    const overlapsAcross = (one, other) =>
      one.left < other.right && other.left < one.right;
    const overlaps = (one, other) =>
      overlapsAcross(one, other) && one.top < other.bottom && other.top < one.bottom;
    const foot = panelFoot.getBoundingClientRect();
    // Beside the page, the thread panel owns the right strip all the way to its foot. Cap
    // the line's room at that strip rather than letting a long hint cross into the panel.
    shortcutBarEl.style.setProperty(
      "--lf-shortcut-bar-right",
      (panelBeside ? commentsEdge.width() : 0) + "px",
    );
    bottomStatusEl.style.setProperty(
      "--lf-shortcut-bar-right",
      (panelBeside ? commentsEdge.width() : 0) + "px",
    );
    // Start at the line's ordinary foot. A covering sheet lifts it only where the sheet's
    // own foot actually occupies the same pixels. The old posture-level answer lifted the
    // line by every covering footer's height even when the footer stood wholly to its
    // right — a two-dimensional collision inferred from one viewport breakpoint.
    shortcutBarEl.style.bottom = "calc(14px + var(--lf-safe-bottom))";
    let line = shortcutBarEl.getBoundingClientRect();
    if (panelCovers() && line.height && overlaps(line, foot)) {
      // The foot is the complete fixed region: composer plus the page's reaction strip
      // when one is offered. offsetHeight retains the safe-area arithmetic owned by the
      // stylesheet and follows a draft as its textarea grows.
      shortcutBarEl.style.bottom = `calc(${panelFoot.offsetHeight + 14}px + var(--lf-safe-bottom))`;
      line = shortcutBarEl.getBoundingClientRect();
    }
    // The status shares the line's baseline when each occupies its own corner. If either
    // grows until their horizontal spans meet, stack the status above the line instead.
    bottomStatusEl.style.bottom = "calc(14px + var(--lf-safe-bottom))";
    let status = bottomStatusEl.getBoundingClientRect();
    if (
      !shortcutBarEl.inert &&
      line.height &&
      status.height &&
      overlapsAcross(status, line)
    ) {
      bottomStatusEl.style.bottom = `${innerHeight - line.top + 7}px`;
      status = bottomStatusEl.getBoundingClientRect();
    } else if (panelCovers() && status.height && overlaps(status, foot)) {
      bottomStatusEl.style.bottom = `calc(${panelFoot.offsetHeight + 14}px + var(--lf-safe-bottom))`;
      status = bottomStatusEl.getBoundingClientRect();
    }
    // What a scroll region gives up is the part of the line that stands over it: the band
    // from the line's top down to that region's own foot, plus the air above the line.
    // Read off the rendered line rather than stated as a number, which is what keeps it
    // true when the line's face or its padding moves — and off each region's own foot,
    // because the three do not end in the same place. The document ends at the foot of
    // the window; the panel's list ends at the top of the complete panel foot, whose
    // composer can grow to half the window with a draft.
    //
    // The band and not the height. The height alone leaves out every inset holding the
    // line off the foot — the 14px above, a covering sheet's lift, the device's safe area
    // — which spent 14 of the 20px of air on the inset and left the document's last line
    // 5px clear rather than 20, and over a covering sheet was short by the whole lift:
    // 148px of line standing on a reservation of 51. One box read rather than three
    // numbers added up, so a fourth inset cannot be introduced without this following it.
    //
    // A bottom surface that is not rendered is a band nothing stands in, so nothing
    // reserves it. A region gives up only the deepest surface crossing its own width.
    const roomBelow = (region) => {
      const clearances = bottomChromeBoxes()
        .filter((box) => overlapsAcross(box, region) && region.bottom > box.top)
        .map((box) => Math.ceil(region.bottom - box.top) + 20);
      return clearances.length ? Math.max(...clearances) + "px" : null;
    };
    const clear =
      roomBelow({
        left: 0,
        right: document.documentElement.clientWidth,
        bottom: document.documentElement.clientHeight,
      }) ?? "0px";
    // The document's, taken as the chrome container's own box rather than as padding on
    // body. The container is in the flow, holds nothing but out-of-flow chrome, and is
    // watched by nobody, so what it takes is room the document has and no measurement's
    // business.
    const boundedWorkspace = document.querySelector(
      "body > main > .lf-workspace-reading[data-lf-workspace-context='root'][data-lf-reading-posture='bounded']",
    );
    chromeRoot.style.paddingBottom = boundedWorkspace ? "0px" : clear;
    // Flow room lets the document reach past the line; scroll padding tells native focus
    // navigation where the visible edge actually is. Keep both on the same measured band
    // so a Tab stop already inside the viewport cannot be accepted underneath the line.
    //
    // The band is on the root rather than only spent here, so a region this function
    // cannot reach can end above the line without a fourth inline write. The contents
    // spine is such a region — fixed page furniture, so no flow room and no list padding
    // reaches it, and it runs under the line at every width. It does not take the band
    // today, deliberately: `lf-toc`'s own rule in the default theme carries the reasoning
    // and the TODO, which is that the line has to be a hover or a foot and not both.
    document.documentElement.style.setProperty("--lf-bottom-chrome-clear", clear);
    // A tray's list is the page's other scroll region, in the corner the line is
    // written into. Its foot is the window's, the tray being held to `bottom: 0`, so the
    // document's band is its band — and it states it twice, because it reaches
    // the bottom two ways that take their room from different places. A wheel to the end
    // reads the padding. A walk's own scroll reads none of it: scroll-padding is what a
    // scroll-into-view stops short of, and without it the last row's clearance is however
    // far Chrome happens to overshoot, which is a fact about row height and not about the
    // line standing there. Stepping the line clear instead was the other answer, and it
    // takes the tray's width off the line's: a busy scope already fills a laptop's, so
    // the room it gives up is chips clipped off the right-hand end.
    reserveListClearance(clear);
    // The panel's own list is the third scroll region the line can stand over. Its
    // reservation follows the same rendered overlap as the lift: a covering sheet with a
    // free lane beside it takes no room for a line that never reaches the list. Spent the
    // same two ways a tray's is — the wheel reads the padding, a walk's scroll-into-view
    // reads the scroll padding — and returned to the stylesheet's inset when there is no
    // shared lane.
    //
    // Measured to this list's own foot, which is the top of the complete fixed panel foot
    // rather than the window's. Giving it the document's band reserved the whole lift
    // twice: the line is standing on the foot, not on the list, so a grown draft put its
    // own height of blank paper under the last thread and parked a `t` walk that far short
    // of the list's end.
    const listClear = panelIsOpen()
      ? (roomBelow(threadsBox.getBoundingClientRect()) ?? "")
      : "";
    threadsBox.style.paddingBottom = listClear;
    threadsBox.style.scrollPaddingBottom = listClear;
    syncFloats();
    dockSeats();
  }
  // The response bar lives in the viewport plane, and syncLayout is where its usable
  // reading boundary changes shape — the panel takes or returns its strip and a resize
  // moves every rect. Re-place it against the durable anchor so it cannot overhang the
  // narrowed shell.
  function syncFloats() {
    if (syncReactLayout()) return;
    refreshFab();
  }
  // A auxiliary chrome state is a responsive-layout boundary, not a sequence of temporary
  // viewport sizes. Apply the state first, so every container query reads the final
  // shell in one pass, then carry the reading column from the box it occupied before
  // the change. Animating body's margin crosses sidebar and sidenote breakpoints during
  // motion and can reverse the column's direction. The offset moves only paint already
  // laid out against the final shell.
  function moveContentFrame(change) {
    const main = document.querySelector("body > main");
    const before = main?.getBoundingClientRect();
    // A second auxiliary surface can replace the first before its motion finishes. Preserve the
    // currently drawn position, then release the old effect before reading the next
    // layout; otherwise two animations would both own the same offset.
    if (shellMotion) {
      shellMotion.cancel();
      shellMotion = null;
    }
    change();
    if (!main || !before) {
      scheduleShellRepaint();
      return null;
    }
    const after = main.getBoundingClientRect();
    const distance = before.left - after.left;
    const moved = Math.abs(distance) >= 0.5;
    const played = moved
      ? motion(
          main,
          [
            { "--lf-shell-motion-x": `${distance}px` },
            { "--lf-shell-motion-x": "0px" },
          ],
          180,
        )
      : null;
    shellMotion = played;
    if (played) {
      const settled = () => {
        if (shellMotion === played) shellMotion = null;
        // The carry changes position without another resize; the repaint's frames lay
        // the margin's rows out along it and once more at rest (repaintMovingShell).
        scheduleShellRepaint();
      };
      played.finished.then(settled, settled);
    }
    scheduleShellRepaint();
    return played;
  }
  // Field sizing and every other chrome-size change feed the one layout pass.
  // The document shell's size also feeds the page repaint door: content landing can move
  // a target without emitting a pointer or scroll event.
  const scheduleLayout = (shellChanged = false, chromeChanged = false) => {
    if (shellChanged) repaintPage();
    else if (chromeChanged) repaint();
  };
  // Body's own box is the first of them, because an auxiliary surface lands its final shell width
  // before the column finishes moving there. Width observation handles taking or
  // returning room; moveContentFrame's frames keep page-attached paint with the carried column.
  //
  // A height-only body resize is repaint-only. An image or font can move a later target
  // without resizing that target or mutating the DOM, while sending that ordinary page
  // growth through syncLayout would feed it into the writer that reserves flow content.
  // A width change schedules syncLayout and its page repaint in the following animation
  // frame, outside ResizeObserver delivery, so a reservation changing another watched
  // chrome box cannot create an undelivered-notification loop. A height-only change calls
  // pageShifted during delivery; its direct geometry write belongs to the unobserved aim
  // box, while hover, legend, and action placement defer their work to frames.
  let bodyContentWidth = 0;
  let bodyContentHeight = 0;
  const layoutSizes = new ResizeObserver((entries) => {
    let layoutChanged = false;
    let shellMoved = false;
    let chromeMoved = false;
    for (const { contentRect, target } of entries) {
      if (target !== document.body) {
        layoutChanged = true;
        chromeMoved = true;
        continue;
      }
      const widthChanged = contentRect.width !== bodyContentWidth;
      const heightChanged = contentRect.height !== bodyContentHeight;
      if (widthChanged) {
        layoutChanged = true;
      }
      if (widthChanged || heightChanged) shellMoved = true;
      bodyContentWidth = contentRect.width;
      bodyContentHeight = contentRect.height;
    }
    if (layoutChanged) scheduleLayout(shellMoved, chromeMoved);
    else if (shellMoved) pageShifted();
  });
  // Mount only after chrome is attached. Constructors perform no observation or
  // listener installation, so importing the public widget API cannot start layout.
  function mountLayoutObservers() {
    commentsEdge.handle(panel, () => closeBtn);
    addEventListener("resize", () => {
      commentsEdge.state();
      restateTrayEdge();
      syncAuxiliarySurfaces();
      pageShifted();
      syncLayout();
    });
    layoutSizes.observe(document.body);
    layoutSizes.observe(panelFoot);
    layoutSizes.observe(shortcutBarEl);
    layoutSizes.observe(bottomStatusEl);
  }
  let shellFrame = 0;
  function repaintMovingShell() {
    shellFrame = 0;
    pageShifted();
    // The margin's rows are placed off the column's box, and the column's box is in
    // flight: the body's width change laid them out on the carry's first frame, against
    // a column a few pixels into its move, and nothing asked again once it had arrived —
    // a resize observer hears a box change size, not place. So the rows stood where the
    // column had been until the next poll or pointer move, over the prose the column had
    // moved under them. Laid out on each carried frame, they ride with the column, and
    // the last call here is the one taken at rest.
    layoutMarginRows();
    if (shellMotion?.playState === "running")
      shellFrame = requestAnimationFrame(repaintMovingShell);
  }
  function scheduleShellRepaint() {
    if (!shellFrame) shellFrame = requestAnimationFrame(repaintMovingShell);
  }

  // The thread panel's edge, on the right, and the tray panel's, on the left. Each keeps
  // the reader's choice in their own store rather than the tab's, because where a reader
  // keeps their conversations, and how much of the page they will give a tray, is the
  // chrome they arrange and expect to find arranged wherever they are reading (see
  // `readerStore`). Live activation keeps the edges themselves; document travel and reload
  // restore the same choices, so no revision or visit asks the reader to draw them again.
  // How the shell takes an edge's new width. A drag follows the hand exactly. An arrow is
  // a discrete change whose page move the reader can follow through the same final-layout
  // motion as opening a region.
  function landEdge(state) {
    const apply = () => {
      state();
      syncLayout();
    };
    if (document.body.hasAttribute("data-lf-sizing")) apply();
    else moveContentFrame(apply);
  }
  const commentsEdge = drawnEdge({
    side: "right",
    noun: "thread panel",
    wide: THREAD_PANEL_W,
    min: THREAD_PANEL_MIN,
    prop: THREAD_PANEL_PROP,
    key: "lf-thread-panel-width",
    covering: COVERING,
    land: landEdge,
  });

  return {
    syncLayout,
    mountLayoutObservers,
    moveContentFrame,
    landEdge,
    commentsEdge,
    panelCovers,
  };
}
