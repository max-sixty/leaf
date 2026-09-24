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
// resident asks for them; `--lf-bottom-chrome-clear`
// carries the bottom chrome's band to whatever has to end above it; `--lf-claim-right` is the
// project-layer extension claim.

// Application composition supplies feature-local geometry. This owner cannot open
// auxiliary surfaces, send commands, or reconcile conversation DOM.
import { drawnEdge } from "./drawn-edge.js";
import { overlaps } from "./geometry.js";
import { standsBeside } from "./auxiliary-surfaces.js";
import { setRuntimeRootStyle } from "./root-state.js";

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
  reserveListClearance,
  restateTrayEdge,
  syncAuxiliarySurfaces,
  syncReactLayout,
  refreshFab,
  dockSeats,
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
    // Where the panel stands, not where its slide has carried it this frame: offsetLeft
    // ignores the slide's transform.
    const panelLeft = panelLive ? panel.offsetLeft : Infinity;
    const railCovered = [
      ...document.querySelectorAll(".lf-margin-projection .lf-margin-cluster"),
    ].some(
      (row) =>
        !row.classList.contains("lf-docked") &&
        row.getBoundingClientRect().right > panelLeft,
    );
    panel.closest(".lf-chrome")?.toggleAttribute("data-lf-rail-covered", railCovered);
    // The line keeps its viewport foot. A covering auxiliary surface makes it inert
    // background, so content growing in that foreground surface is not a collision and
    // cannot move the line.
    shortcutBarEl.style.bottom = "calc(14px + var(--lf-safe-bottom))";
    const line = shortcutBarEl.getBoundingClientRect();
    // The status shares the line's baseline when each occupies its own corner. If either
    // grows until their horizontal spans meet, stack the status above the line instead.
    bottomStatusEl.style.bottom = "calc(14px + var(--lf-safe-bottom))";
    const status = bottomStatusEl.getBoundingClientRect();
    if (
      !shortcutBarEl.inert &&
      line.height &&
      status.height &&
      overlapsAcross(status, line)
    ) {
      bottomStatusEl.style.bottom = `${innerHeight - line.top + 7}px`;
    } else if (panelCovers() && status.height && overlaps(status, foot)) {
      // Unlike the inert shortcut guide, notices are live feedback from the foreground
      // action and remain visible above the covering panel's foot.
      bottomStatusEl.style.bottom = `calc(${panelFoot.offsetHeight + 14}px + var(--lf-safe-bottom))`;
    }
    // What a scroll region gives up is the part of the line that stands over it: the band
    // from the line's top down to that region's own foot, plus the air above the line.
    // Read off the rendered line rather than stated as a number, which is what keeps it
    // true when the line's face or its padding moves — and off each region's own foot,
    // because the regions do not necessarily end in the same place. The document ends at
    // the foot of the window.
    //
    // The band and not the height. The height alone leaves out every inset holding the
    // line off the foot — the 14px above and the device's safe area — which spent 14 of
    // the 20px of air on the inset and left the document's last line 5px clear rather
    // than 20. One box read rather than two numbers added up, so a third inset cannot be
    // introduced without this following it.
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
    setRuntimeRootStyle(document.documentElement, "--lf-bottom-chrome-clear", clear);
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

  // The thread panel's edge, on the right, and the tray panel's, on the left. Each keeps
  // the user's choice in their own store rather than the tab's, because where a user
  // keeps their conversations, and how much of the page they will give a tray, is the
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
