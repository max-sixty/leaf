// The width the panel stands at for a reader who has not moved its edge. 420 since
// threads carry questions — option rows are the one thread content that can't scroll or
// scale its width away, and 360 crowded them. A default rather than the width, because
// what a conversation needs is a fact about the conversation: a thread quoting a table
// wants room the same thread quoting a sentence does not, and only the reader looking at
// it knows which this is. So the edge is a thing they take hold of (`drawnEdge`), and
// this is where it stands until they do.
export const PANEL_W = 420;
// How narrow they may draw it in. 320 is the narrowest window the panel is held to
// standing up in (test_a_thread_gives_its_reply_the_full_row_and_its_actions_the_next),
// so it is the narrowest width anything has laid a thread's reply box and its two
// actions out at; below it nothing says they still fit. Wanting the panel gone is what
// closing it is for, and narrowing it to nothing is not the same wish.
export const PANEL_MIN = 320;
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
export const COVERING = `(width <= ${PANEL_W * 2}px)`;
export const NON_COVERING = `(width > ${PANEL_W * 2}px)`;
// Where each standing width is written, and where the cascade reads it. Named rather than
// spelled, because the stylesheet and the runtime's writer are two ends of one fact
// and a property spelled twice is two facts the day one of them moves.
export const PANEL_PROP = "--lf-panel-w";

// Panel open/closed is remembered too: it survives live activation, document travel,
// and reload, so reopening the panel by hand after every revision gets old fast.
export const PANEL_KEY = "lf-panel-open";

export function createChromeLayout({
  chromeRoot,
  commentsEdge,
  closeReactions,
  containsAcross,
  currentTray,
  dockSeats,
  focused,
  foldShelf,
  keylineEl,
  motion,
  pageShifted,
  paintHere,
  panel,
  panelChanged,
  panelFoot,
  panelList,
  readerStore,
  refreshFab,
  refreshHover,
  renderPanel,
  reserveListClearance,
  showTray,
  syncReactLayout,
  syncGeneral,
  toggleBtn,
  traysEdge,
}) {
  // Until the first state answer, [] means "not read", not "no comments". Keep that
  // distinction for a Threads panel restored or opened during startup; its General
  // composer stays usable while the log-derived list says what it is waiting for.

  // The threads the panel last reconciled. A receipt repaints on the heartbeat's clock and
  // not only on the log's, because its age is half of what it says and a claim nobody
  // renews is exactly the one whose age has stopped moving. Keeping the last fold is what
  // makes that cheap: buildThreads walks the log and the page, and a second walk every two
  // seconds would answer nothing the last one didn't.
  let panelOpen = false;
  let shellMotion = null;
  const panelIsOpen = () => panelOpen;
  // Whether the panel stands over the page rather than beside it — the same fact as which
  // of the two rules that take the strip the page is under, and as which region the
  // reader's own scrolling moves. Asked of the edge's query rather than stored, so no reader
  // of it can hold an answer from a window that has gone.
  const panelCovers = () => panelOpen && commentsEdge.over.matches;
  // Whether the reader is standing in the panel rather than merely looking at it — focus,
  // not visibility, the same line PANEL draws for its own scope and the one every surface
  // here reads. A press that acts on where the reader is standing has to ask it of the
  // focus: beside the page the panel is a column of its own, and a reader working down the
  // list is in it whatever the window is wide enough to show behind them.
  const inPanel = () => panelOpen && containsAcross(panel, focused());
  // The panel is shown, never shown modally, at either posture. A modal dialog makes the
  // rest of the document inert, and the panel covering the page is the posture in which the
  // page most needs to stay live: the toggle that opened it is out in the banner and is how
  // it closes, the decisions toggle beside it is the other workspace this one replaces
  // (test_workspaces_replace_each_other_instead_of_stacking), and the strip of page still
  // showing beside a covering sheet is still page a reader can point a hint at
  // (test_selection_hints_do_not_name_page_content_behind_a_covering_panel, which is the
  // one that states what "covering" means here — the panel covers the page rather than
  // clipping it, and what it covers is out of reach only where it is actually painted over).
  // What modality was carrying instead is already owned elsewhere and stays: the covering
  // sheet's scroll lock is the stylesheet's (COVERING's `overflow-y: hidden`), and Escape is
  // the ladder's, which browserDismissesTopLayer hands to the platform only for the layers
  // the platform really owns.
  //
  // Opening a <dialog> runs the browser's dialog focusing steps whichever way it is opened,
  // so the invoker has to be given its focus back: raising the panel is not a request to
  // leave where the reader was standing, and the toggle that lost it would otherwise hold
  // aria-expanded with no ring on it and hand the reader's next Space to a button they
  // never chose. A reader who asked to go in says so with the press that takes them —
  // `g T` focuses the list and `c` focuses its requested box — and setPanel's own handoff
  // is the other thing that moves them.
  function showPanelLayer() {
    // Both a comment destination and Threads navigation may ask for a panel that is already
    // showing. Nothing to redo, and the focus below would otherwise fire against a reader
    // already standing inside.
    if (panel.open) return;
    const invoker = document.activeElement;
    panel.show();
    if (invoker?.isConnected && !panel.contains(invoker))
      invoker.focus({ preventScroll: true });
  }
  // A window that has changed is a cap that has changed, so each edge restates its
  // standing width. CSS container queries read the resulting body width directly.
  addEventListener("resize", () => {
    commentsEdge.state();
    traysEdge.state();
  });
  // Every writer here is a writer of the chrome, so nothing this function does resizes the
  // box it reads: the strip the page yields to the panel is the stylesheet's, and the strip
  // it yields to a margin idiom is stated above.
  function syncLayout() {
    // How many of the banner's addresses stand on its row is a reservation taken from the
    // row's current box, so it belongs here with the rest of them and it goes first: what
    // it decides is the banner's own contents, which nothing below reads. The banner is
    // fixed, so a fold cannot resize the boxes this function is watching.
    foldShelf();
    const panelBeside = panelOpen && !panelCovers();
    // Beside the page, the thread panel owns the right strip all the way to its foot. The
    // line starts at the window's left, so cap its room at that strip rather than letting a
    // long computed hint cross into the general comment box. A covering panel leaves the
    // line its natural width: unlike a standing strip, it may leave a complete lane beside
    // its foot, and whether it does is a fact of the two rendered boxes below.
    keylineEl.style.setProperty(
      "--lf-keyline-right",
      (panelBeside ? commentsEdge.width() : 0) + "px",
    );
    // Start at the line's ordinary foot. A covering sheet lifts it only where the sheet's
    // own foot actually occupies the same pixels. The old posture-level answer lifted the
    // line by every covering footer's height even when the footer stood wholly to its
    // right — a two-dimensional collision inferred from one viewport breakpoint.
    keylineEl.style.bottom = "calc(14px + var(--lf-safe-bottom))";
    const overlapsAcross = (one, other) =>
      one.left < other.right && other.left < one.right;
    const overlaps = (one, other) =>
      overlapsAcross(one, other) && one.top < other.bottom && other.top < one.bottom;
    const foot = panelFoot.getBoundingClientRect();
    let line = keylineEl.getBoundingClientRect();
    if (panelCovers() && line.height && overlaps(line, foot)) {
      // The foot is the complete fixed region: composer plus the page's reaction strip
      // when one is offered. offsetHeight retains the safe-area arithmetic owned by the
      // stylesheet and follows a draft as its textarea grows.
      keylineEl.style.bottom = `calc(${panelFoot.offsetHeight + 14}px + var(--lf-safe-bottom))`;
      line = keylineEl.getBoundingClientRect();
    }
    // What a scroll region gives up is the part of the line that stands over it: the band
    // from the line's top down to that region's own foot, plus the air above the line.
    // Read off the rendered line rather than stated as a number, which is what keeps it
    // true when the line's face or its padding moves — and off each region's own foot,
    // because the three do not end in the same place. The document ends at the foot of
    // the window; the panel's list ends above the sheet's own foot, which is the composer
    // and can be half the window once a draft has grown it.
    //
    // The band and not the height. The height alone leaves out every inset holding the
    // line off the foot — the 14px above, a covering sheet's lift, the device's safe area
    // — which spent 14 of the 20px of air on the inset and left the document's last line
    // 5px clear rather than 20, and over a covering sheet was short by the whole lift:
    // 148px of line standing on a reservation of 51. One box read rather than three
    // numbers added up, so a fourth inset cannot be introduced without this following it.
    //
    // A line that is not rendered — no room on a coarse pointer, nothing to say on any
    // pointer — is a band nothing stands in, so nothing reserves it. Nor does a region
    // whose own foot is above the line, which is what the panel's list is beside the page.
    const roomBelow = (region) =>
      line.height && overlapsAcross(line, region) && region.bottom > line.top
        ? Math.ceil(region.bottom - line.top) + 20 + "px"
        : null;
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
    chromeRoot.style.paddingBottom = clear;
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
    // Measured to this list's own foot, which is the sheet's composer rather than the
    // window's. Giving it the document's band reserved the whole lift twice: the line is
    // standing on the foot, not on the list, so a grown draft put its own height of blank
    // paper under the last thread and parked a `t` walk that far short of the list's end.
    const listClear = panelCovers()
      ? (roomBelow(panelList.getBoundingClientRect()) ?? "")
      : "";
    panelList.style.paddingBottom = listClear;
    panelList.style.scrollPaddingBottom = listClear;
    syncFloats();
    dockSeats();
  }
  // The response bar lives in the document, and syncLayout is where its containing box
  // changes shape — the panel takes or returns its strip and a resize moves every rect.
  // Re-place it against the durable anchor so it cannot overhang the narrowed shell and
  // create sideways-scrollable overflow.
  function syncFloats() {
    if (syncReactLayout()) return;
    refreshFab();
  }
  // A workspace state is a responsive-layout boundary, not a sequence of temporary
  // viewport sizes. Apply the state first, so every container query reads the final
  // shell in one pass, then carry the reading column from the box it occupied before
  // the change. Animating body's margin made the shell itself pass through every layout
  // breakpoint: on the gallery the 520px conversation claim disappeared mid-flight and
  // sent the column back the way it had come; one window down, the authored sidebar did
  // the same. The offset moves only paint already laid out against the final shell.
  function moveShell(change) {
    const main = document.querySelector("body > main");
    const before = main?.getBoundingClientRect();
    // A second workspace can replace the first before its motion finishes. Preserve the
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
        scheduleShellRepaint();
      };
      played.finished.then(settled, settled);
    }
    scheduleShellRepaint();
    return played;
  }
  function setPanel(open) {
    if (open && currentTray()) showTray(null);
    // Closing while focus is inside would drop it on body, the user's place
    // lost silently; it lands on the one control that reopens what just closed.
    if (!open && panel.contains(document.activeElement))
      toggleBtn.focus({ preventScroll: true });
    panelOpen = open;
    // Twice, the two readers being on opposite sides of the chrome's own scope: the class
    // shows the panel, from a rule inside it, and the attribute is what the page yields its
    // strip to, from a rule outside. A document-level rule naming .lf-panel would be a name
    // a page could coin and take the strip with, which is the leak
    // test_a_coined_class_cannot_reach_the_chromes_rules pins, so the posture is stated on
    // body, where page CSS can see it without naming private chrome.
    panel.classList.toggle("open", open);
    moveShell(() => document.body.toggleAttribute("data-lf-panel", open));
    toggleBtn.setAttribute("aria-expanded", String(open));
    if (open) {
      // The layer before what goes in it. The panel is a dialog, and a dialog nobody has
      // shown yet is display:none, so anything rendered into it measures zero — and
      // renderPanel is where the anchor pass runs for the threads it draws. A mark hangs
      // on the boxes its element shows through (shownParts), so a widget an agent sent in
      // a reply resolved to an element with no box, took no mark, and left the thread
      // still open in the panel pointing at nothing on either side.
      showPanelLayer();
      renderPanel();
      syncGeneral(); // a restored draft has to reach the Send button's disabled state
    } else if (panel.open) panel.close();
    syncLayout();
    panelChanged(open);
    readerStore.set(PANEL_KEY, open ? "1" : "0");
    paintHere();
    // The panel is one of the two surfaces the hover reads, so its arriving or going away
    // is the pointer moving even when the pointer has not: closing it with the keyboard,
    // from a hand resting on a card, took the card out from under the pointer and left the
    // page lit about a comment with no panel to explain it. The open half came free through
    // renderPanel; this is the half that has no render.
    refreshHover();
  }
  toggleBtn.onclick = () => setPanel(!panelOpen);
  addEventListener("resize", () => {
    closeReactions();
    pageShifted();
    syncLayout();
  });
  // Field sizing and every other chrome-size change feed the one chrome geometry writer.
  // The document shell's size also feeds the page repaint door: content landing can move
  // a target without emitting a pointer or scroll event.
  let layoutFrame = 0;
  let pageMoved = false;
  let chromeMoved = false;
  const scheduleLayout = (shellChanged = false, chromeChanged = false) => {
    pageMoved ||= shellChanged;
    chromeMoved ||= chromeChanged;
    if (layoutFrame) return;
    layoutFrame = requestAnimationFrame(() => {
      layoutFrame = 0;
      const repaintPage = pageMoved;
      const repaintChrome = chromeMoved;
      pageMoved = false;
      chromeMoved = false;
      syncLayout();
      if (repaintPage) pageShifted();
      // A settled key-line or panel-foot size can change both the line's final box and
      // the part of a target or search match it covers. Re-enter the shared paint after
      // the chrome writer has placed that box, so every consumer reads the same geometry.
      // `paintHere` is frame-coalesced, and a same-sized line emits no further resize.
      if (repaintChrome) paintHere();
    });
  };
  // Body's own box is the first of them, because a workspace lands its final shell width
  // before the column finishes moving there. Width observation handles taking or
  // returning room; moveShell's frames keep page-attached paint with the carried column.
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
  layoutSizes.observe(document.body);
  layoutSizes.observe(panelFoot);
  layoutSizes.observe(keylineEl);

  let shellFrame = 0;
  function repaintMovingShell() {
    shellFrame = 0;
    pageShifted();
    if (shellMotion?.playState === "running")
      shellFrame = requestAnimationFrame(repaintMovingShell);
  }
  function scheduleShellRepaint() {
    if (!shellFrame) shellFrame = requestAnimationFrame(repaintMovingShell);
  }
  return { inPanel, moveShell, panelCovers, panelIsOpen, setPanel, syncLayout };
}
