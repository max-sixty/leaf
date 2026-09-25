// `syncLayout` derives only floating chrome placement and reservations from current
// chrome boxes. CSS owns the document shell: `body` is the named `lf-shell` inline-size
// container, `main` composes its left and right claims, and queries grant or withdraw
// margin postures. JavaScript may hear the shell's content-box size without deriving a
// posture or mirroring cramped state. `layoutSizes` schedules `syncLayout` and page
// repaint after a width change. `moveContentFrame` lands the final responsive shell in one
// pass and repaints page-attached chrome in the same gesture. Nothing here holds the
// user's place across the reflow that lands with the new shell: the browser does, because
// the strip the shell yields is a transparent border rather than a margin, and `border-width`
// is not a scroll-anchoring suppression trigger (theme.css, at the body strip, carries the
// measurement and the reasoning). A height-only change sends `pageShifted` directly so a content
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
// one stands at a time. Leaves always covers the page. Threads and the Asks tray cover it
// only where they would leave less than a usable page beside them, one rule for both
// (`standsBeside`, auxiliary-surfaces.js; `--lf-auxiliary-beside`, theme.css at the body
// strip). Elsewhere the Asks tray takes a strip on the left, and Threads stands over a
// column page and takes no width from it, and beside a sheet, which yields it a strip on
// the right. Auxiliary modality
// is a shared inert boundary outside this geometry owner; the reference and Page Map
// keep native `showModal()`. The shell's inline size already reflects the strip a beside
// surface takes. `--strip-l`, `--strip-r`,
// `--lf-room`, `--lf-sidebar-posture`, and `--lf-rail-posture` are CSS-owned readings
// resolved on `main`, which is the named `lf-content-frame` style container a margin
// resident asks for them; `--lf-shell-inset-left`
// carries the left auxiliary-surface offset to viewport-fixed page furniture. The bottom
// band is a stated height (`--lf-band-h`, theme.css) rather than a reading, so whatever
// has to end above it reads that token; `--lf-claim-right` is the project-layer
// extension claim.

// Application composition supplies feature-local geometry. This owner cannot open
// auxiliary surfaces, send commands, or reconcile conversation DOM.
import { sizeObserver } from "./rendering.js";
import { drawnEdge } from "./drawn-edge.js";
import { overlaps } from "./geometry.js";
import { standsBeside } from "./auxiliary-surfaces.js";

// The width the panel stands at for a user who has not moved its edge. 420 since
// threads carry questions — option rows are the one thread content that can't scroll or
// scale its width away, and 360 crowded them. A default rather than the width, because
// what a conversation needs is a fact about the conversation: a thread quoting a table
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
  dockSeats,
  pageShifted,
  layoutMarginRows,
  repaint,
  repaintPage,
}) {
  // The panel stands over a column page and takes no room from it: the centred column
  // mostly clears it. A sheet has no column to clear it with — its rail is under the
  // panel — so it yields the panel a strip and reflows its tracks beside it. Either way
  // the panel covers the page — the modal boundary that makes the page inert — only where
  // what it leaves beside it is less than a usable page, the rule every surface that may
  // stand beside the page shares (`standsBeside`).
  const panelCovers = () => panelIsOpen() && !standsBeside();
  // Every writer here is a writer of the chrome, so nothing this function does resizes the
  // box it reads: the strip the page yields to a tray is the stylesheet's, and the strip
  // it yields to a margin idiom is stated above.
  function syncLayout() {
    scheduleThreadPreviewPosition();
    const panelLive = panelIsOpen() && !panelCovers();
    const overlapsAcross = (one, other) =>
      one.left < other.right && other.left < one.right;
    const foot = panelFoot.getBoundingClientRect();
    // Over a live page, the thread panel owns the right of the window all the way to its
    // foot. Cap the line's room at its edge rather than letting a long hint cross into it.
    const panelRoom = (panelLive ? commentsEdge.width() : 0) + "px";
    shortcutBarEl.style.setProperty("--lf-shortcut-bar-right", panelRoom);
    bottomStatusEl.style.setProperty("--lf-shortcut-bar-right", panelRoom);
    // The rail stands in the page's right margin, and over a live page the panel stands
    // over that margin at any window short of about 1700px. The markers are still drawn,
    // under the panel, so the rail's own posture says nothing; what says the user lost
    // them is a rail row the panel's edge reaches. Where one does, the banner offers the
    // Page Map in their place, as it does where the rail is not drawn at all (chrome.css).
    const panelLeft = panelLive ? panel.getBoundingClientRect().left : Infinity;
    const railCovered = [
      ...document.querySelectorAll(".lf-margin-projection .lf-margin-cluster"),
    ].some(
      (row) =>
        !row.classList.contains("lf-docked") &&
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
    dockSeats();
  }
  // The response bar lives in the viewport plane, and syncLayout is where its usable
  // reading boundary changes shape — a tray takes or returns its strip and a resize
  // moves every rect. Re-place it against the durable anchor so it cannot overhang the
  // narrowed shell.
  function syncFloats() {
    if (syncReactLayout()) return;
    refreshFab();
  }
  // An auxiliary chrome state is a responsive-layout boundary, not a sequence of temporary
  // viewport sizes. Apply the state and every container query reads the final shell in one
  // pass; the reading column arrives at its new horizontal position in that same pass.
  //
  // It used to glide there over 180ms. That glide animated `main`'s `left`, which is a
  // scroll-anchoring suppression trigger on every frame it ran, so the page bought a
  // moving column at the price of dropping the user each time a strip was returned. The
  // browser carries them now (theme.css, at the body strip), and the column jumps — which
  // is what every editor with a side panel does, and cheaper than it looks against words
  // that stay put.
  //
  // So the paint that follows the column follows it here, in the gesture, not a frame
  // later. The repaint was deferred only because the column used to be in flight; with
  // it already at rest there is nothing to wait for, and waiting left a frame in which
  // the margin's rows and the marks on the page stood where the column had been. They are
  // placed off the column's box, which a resize observer cannot report — it hears a box
  // change size, not place. The observers still run on the frame after, and re-placing
  // what is already placed is a no-op.
  //
  // `change` carries the shell write, and chrome reconciliation rides with it: `landEdge`
  // passes `syncLayout` through this call and the user stays on the same words across
  // the reflow. What may not go inside is a surface's own rendering. The hold the browser
  // carries rests on an ordering (theme.css, at the body strip): nothing may move the
  // reading column except the container-query recalc that runs inside layout, and showing
  // a surface in the same batch as the shell write switches that hold off — measured at
  // 900px, the user landed three paragraphs back. So the frame is private,
  // and what leaves this module is `takeShell`, which carries a surface's key rather than
  // a callback: a surface owner has no way to render inside it, and renders either side.
  function moveContentFrame(change) {
    change();
    pageShifted();
    layoutMarginRows();
  }
  function takeShell(surface) {
    moveContentFrame(() => {
      if (surface) document.body.dataset.lfAuxiliarySurface = surface;
      else delete document.body.dataset.lfAuxiliarySurface;
    });
  }
  // Field sizing and every other chrome-size change feed the one layout pass.
  // The document shell's size also feeds the page repaint door: content landing can move
  // a target without emitting a pointer or scroll event.
  const scheduleLayout = (shellChanged = false, chromeChanged = false) => {
    if (shellChanged) repaintPage();
    else if (chromeChanged) repaint();
  };
  // Body's own box is the first of them: taking or returning room changes body's content box,
  // since the strip is a border inside it, so width observation hears every auxiliary
  // surface arrive and leave. `moveContentFrame` has already placed page-attached paint by
  // then; this pass is the one that also covers a window resize, which has no gesture to
  // repaint from.
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
  // keeps their conversations, and how much of the page they will give a tray, is the
  // chrome they arrange and expect to find arranged wherever they are reading (see
  // `userStore`). Live activation keeps the edges themselves; document travel and reload
  // restore the same choices, so no revision or visit asks the user to draw them again.
  // How the shell takes an edge's new width. A drag follows the hand exactly. An arrow is
  // a discrete change whose page move the user can follow through the same final-layout
  // motion as opening a region.
  function landEdge(state) {
    const apply = () => {
      state();
      syncAuxiliarySurfaces();
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
    land: landEdge,
  });

  return {
    syncLayout,
    mountLayoutObservers,
    takeShell,
    landEdge,
    commentsEdge,
  };
}
