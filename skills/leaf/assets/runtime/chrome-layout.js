// `syncLayout` derives only floating chrome placement and reservations from current
// chrome boxes. CSS owns the document shell: `body` is the named `lf-shell` inline-size
// container, `main` composes its left and right claims, and queries grant or withdraw
// margin postures. JavaScript may hear the shell's content-box size without deriving a
// posture or mirroring cramped state. `layoutSizes` schedules `syncLayout` and page
// repaint after a width change. No auxiliary surface changes the shell: each stands over
// the page. A height-only change sends `pageShifted` directly so a content reflow
// re-places document-attached paint without re-running chrome reservation.
//
// `syncLayout` measures only chrome whose placement or reservation depends on rendered
// chrome, and writes only chrome boxes. `layoutSizes` watches `document.body`'s
// content-box size without deriving a posture from it. A width change schedules
// `syncLayout` and page repaint in the following frame; a height-only content reflow calls `pageShifted` during observer delivery so
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
// one stands at a time, over the page and taking no width from it. Leaves always covers
// the page. Threads and the Asks tray cover it only where they would leave less than a
// usable page beside them, one rule for both (`standsBeside`, auxiliary-surfaces.js;
// `--lf-auxiliary-beside`, theme.css); elsewhere the page beside them stays live.
// Auxiliary modality is a shared inert boundary outside this geometry owner; the
// reference and Page Map keep native `showModal()`. `--strip-l`, `--strip-r`,
// `--lf-room`, `--lf-sidebar-posture`, and `--lf-rail-posture` are CSS-owned readings
// resolved on `main`, which is the named `lf-content-frame` style container a margin
// resident asks for them. The bottom
// band is a stated height (`--lf-band-h`, theme.css) rather than a reading, so whatever
// has to end above it reads that token; `--lf-claim-right` is the project-layer
// extension claim.

// Application composition supplies feature-local geometry. This owner cannot open
// auxiliary surfaces, send commands, or reconcile thread DOM.
import { sizeObserver } from "./rendering.js";
import { drawnEdge } from "./drawn-edge.js";
import { overlaps, overlapsAcross } from "./rect.js";
import { standsBeside } from "./auxiliary-surfaces.js";

// The width the panel stands at for a user who has not moved its edge. 420 since
// threads carry questions — option rows are the one thread content that can't scroll or
// scale its width away, and 360 crowded them. A default rather than the width, because
// what a thread needs is a fact about the thread: a thread quoting a table
// wants room the same thread quoting a sentence does not, and only the user looking at
// it knows which this is. So the edge is a thing they take hold of (`drawnEdge`), and
// this is where it stands until they do. theme.css spells the same default for the
// first paint of a reloaded page, before this module has written a width.
//
// Opening or closing an auxiliary surface calls its state setter and schedules the shared layout
// and key paint. User gestures remember their intent; an ephemeral developer replay
// uses the same transition without replacing it.
const THREAD_PANEL_W = 420;
// How narrow they may draw it in. 320 is the narrowest window the panel is held to
// standing up in (test_a_thread_keeps_submit_in_its_field_and_resolve_beside_its_quote),
// so it is the narrowest width anything has laid a thread's reply box and its two
// actions out at; below it nothing says they still fit. Wanting the panel gone is what
// closing it is for, and narrowing it to nothing is not the same wish.
const THREAD_PANEL_MIN = 320;
// Where the standing width is written, and where the cascade reads it.
const THREAD_PANEL_PROP = "--lf-thread-panel-width";

export function createChromeLayout({
  panelIsOpen,
  elements: { panel, closeBtn, panelFoot, threadsBox, shortcutBarEl, bottomStatusEl },
  scheduleThreadPreviewPosition,
  bottomChromeBoxes,
  restateTrayEdge,
  syncAuxiliarySurfaces,
  syncReactLayout,
  refreshFab,
  pageShifted,
  repaint,
  repaintPage,
}) {
  // The panel stands over the page and takes no room from it. It covers the page — the
  // modal boundary that makes the page inert — only where what it leaves beside it is
  // less than a usable page, the rule every surface that may stand beside the page shares
  // (`standsBeside`).
  const panelCovers = () => panelIsOpen() && !standsBeside();
  // Every writer here is a writer of the chrome, so nothing this function does resizes the
  // box it reads.
  function syncLayout() {
    scheduleThreadPreviewPosition();
    const panelLive = panelIsOpen() && !panelCovers();
    const foot = panelFoot.getBoundingClientRect();
    // Over a live page, the thread panel owns the right of the window all the way to its
    // foot. Cap the line's room at its edge rather than letting a long hint cross into it.
    const panelRoom = (panelLive ? commentsEdge.width() : 0) + "px";
    shortcutBarEl.style.setProperty("--lf-shortcut-bar-right", panelRoom);
    bottomStatusEl.style.setProperty("--lf-shortcut-bar-right", panelRoom);
    // Over a live page the panel stands over the page's right margin at any window short
    // of about 1700px, and over the pins at the column's edge at the same widths. The
    // markers are still drawn, under the panel; what says the user lost them is a margin
    // row the panel's edge reaches. Where one does, the banner offers the Page Map in
    // their place, as it does on a compact page (chrome.css).
    // Where the panel stands, not where its slide has carried it this frame: offsetLeft
    // ignores the slide's transform.
    const panelLeft = panelLive ? panel.offsetLeft : Infinity;
    const railCovered = [
      ...document.querySelectorAll(".lf-margin-projection .lf-margin-cluster"),
    ].some(
      (row) =>
        !row.classList.contains("lf-withheld") &&
        row.getBoundingClientRect().right > panelLeft,
    );
    panel.closest(".lf-chrome")?.toggleAttribute("data-lf-rail-covered", railCovered);
    // The status stands in the bottom band (chrome.css) and moves only to stay live above
    // a covering panel's foot: unlike the inert shortcut guide, notices are live feedback
    // from the foreground action. Everything the page ends above is the band's stated
    // height, so nothing here writes a reservation for the document or the trays.
    bottomStatusEl.style.bottom = "";
    bottomStatusEl.style.translate = "";
    const status = bottomStatusEl.getBoundingClientRect();
    if (panelCovers() && status.height && overlaps(status, foot)) {
      bottomStatusEl.style.bottom = `calc(${panelFoot.offsetHeight + 14}px + var(--lf-safe-bottom))`;
      bottomStatusEl.style.translate = "none";
    }
    // A region gives up the part of a bottom surface that stands over it: the band from
    // that surface's top down to the region's own foot, plus air above it. Read off the
    // rendered box, since what crosses the panel's list is a status whose place follows
    // the panel's foot rather than a stated band.
    const roomBelow = (region) => {
      const clearances = bottomChromeBoxes()
        .filter((box) => overlapsAcross(box, region) && region.bottom > box.top)
        .map((box) => Math.ceil(region.bottom - box.top) + 20);
      return clearances.length ? Math.max(...clearances) + "px" : null;
    };
    // The panel list is its own scroll region. The inert guide no longer reaches it, but
    // a live walk status remains above the covering panel and can stand over its list.
    // Reserve only the rendered bottom surface that crosses the list, for both wheel and
    // scroll-into-view landings, and restore the stylesheet's inset when none does.
    const listClear = panelIsOpen()
      ? (roomBelow(threadsBox.getBoundingClientRect()) ?? "")
      : "";
    threadsBox.style.paddingBottom = listClear;
    threadsBox.style.scrollPaddingBottom = listClear;
    syncFloats();
  }
  // The response bar lives in the viewport plane, and syncLayout is where its usable
  // reading boundary changes shape — a resize moves every rect. Re-place it against the
  // durable anchor so it cannot overhang the shell.
  function syncFloats() {
    if (syncReactLayout()) return;
    refreshFab();
  }
  // Field sizing and every other chrome-size change feed the one layout pass.
  // The document shell's size also feeds the page repaint door: content landing can move
  // a target without emitting a pointer or scroll event.
  const scheduleLayout = (shellChanged = false, chromeChanged = false) => {
    if (shellChanged) repaintPage();
    else if (chromeChanged) repaint();
  };
  // Body's own box is the first of them: width observation hears a window resize, which has
  // no gesture to repaint from.
  //
  // A height-only body resize is repaint-only. An image or font can move a later target
  // without resizing that target or mutating the DOM, and that ordinary page growth
  // changes nothing syncLayout writes.
  // A width change schedules syncLayout and its page repaint in the following animation
  // frame, outside ResizeObserver delivery, so a reservation changing another watched
  // chrome box cannot create an undelivered-notification loop. A height-only change calls
  // pageShifted during delivery; its direct geometry write belongs to the unobserved aim
  // box, while hover, legend, and action placement defer their work to frames.
  let bodyContentWidth = 0;
  let bodyContentHeight = 0;
  const layoutSizes = sizeObserver((entries) => {
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

  // The thread panel's edge, on the right, and the tray panel's, on the left. Each keeps
  // the user's choice in their own store rather than the tab's, because where a user
  // keeps their threads, and how much of the page they will give a tray, is the
  // chrome they arrange and expect to find arranged wherever they are reading (see
  // `userStore`). Live activation keeps the edges themselves; document travel and reload
  // restore the same choices, so no revision or visit asks the user to draw them again.
  // An edge's new width moves only its region: the page beneath it keeps its geometry.
  // What the width changes is whether the region still leaves a usable page beside it.
  function landEdge(state) {
    state();
    syncAuxiliarySurfaces();
    syncLayout();
  }
  const commentsEdge = drawnEdge({
    side: "right",
    noun: "thread panel",
    wide: THREAD_PANEL_W,
    min: THREAD_PANEL_MIN,
    prop: THREAD_PANEL_PROP,
    key: "lf-thread-panel-width",
    land: landEdge,
  });

  return {
    syncLayout,
    mountLayoutObservers,
    landEdge,
    commentsEdge,
  };
}
