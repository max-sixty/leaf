export function createSelectionSurface({
  anchoringIsReady,
  composer,
  composerInput,
  composerIsOpen,
  designIsOn,
  designTarget,
  fab,
  hideComposer,
  hideReference,
  inChrome,
  markAt,
  noteClass,
  openComposer,
  openOnDesign,
  pageRange,
  pageScroller,
  pageSelection,
  pageWords,
  paintHere,
  panel,
  panelCovers,
  pendingMarks,
  referenceIsOpen,
  selectionAnchor,
  showThread,
  showVersionMenu,
  snapSelection,
  tagsDeclaring,
  takesLetters,
  versionMenuIsOpen,
  visualPartAt,
}) {
  // ---------- selection → comment ----------
  // Floating UI stays inside the document's own box, which is body's client box: it
  // already ends at the open panel's edge (syncLayout's margin) and inside a classic
  // scrollbar's gutter, so a float clamped to it can't hand body a sideways scrollbar
  // by overhanging either. The covering sheet is the one strip that box no longer
  // states — body keeps its full width under it — so the sheet's own width comes off
  // here, and a float raised from the strip beside it can't stand over the thread list.
  const rightEdge = () =>
    (panelCovers() ? innerWidth - panel.offsetWidth : pageScroller.clientWidth) - 8;
  // The floats live in the document — they scroll with the passage they stand beside —
  // while every caller reasons in viewport terms: rects, the pointer, the banner's own
  // band. Named, because four sites had the number written out and it is neither of the
  // two it stands near — the banner is 42px and the scroller's scroll-padding-top 54px,
  // this being the slack over the first that says what the reader can actually see.
  const BANNER_CLEAR = 48;
  // So the one writer of their position is where the coordinates change space: clamp in
  // the viewport, store in the document.
  function place(node, left, top) {
    node.style.left =
      Math.max(8, Math.min(left, rightEdge() - node.offsetWidth)) + "px";
    node.style.top =
      Math.max(BANNER_CLEAR, Math.min(top, innerHeight - node.offsetHeight - 8)) +
      pageScroller.scrollTop +
      "px";
  }
  // The composer's first choice of a place is the column's margin, beside the passage, so
  // the mark and the box stand side by side — where the box opened instead at the gesture
  // (the fab, the ⌥-click's pointer), it stood on the page's own text next to the
  // passage, which is the one thing a 320px card over a 720px column can't avoid doing
  // there. placeClear steps it down past any control the page hangs out in that same
  // margin (a suggestion's Accept/Reject row).
  //
  // A sidenote is out there too and the box covers one whole while it stands, which is
  // where this stops short of stepping clear. What the walk steps past is controls,
  // because a control the box hides is a press the reader was reaching for; a note is
  // prose they are not mid-gesture on, and the box goes when they are done with it. The
  // walk could be taught the note as easily — the cost is where it would then put the box
  // on a page carrying a run of them, which is far enough down the margin to be about a
  // different paragraph.
  //
  // Where the margin is too narrow for the box — a laptop window, the panel open — it
  // has one thing left to stay clear of: its own mark. That mark is the only thing
  // naming the passage the box is about, so a box standing on all of it is a box about
  // nothing. Not "no overlap" — the box has always covered the tail of a long passage
  // and that reads fine — but every rect hidden is the case to move for, and it is a
  // case that happens: a restored draft reappears near the top of the viewport, and the
  // reading position puts the passage it was made on back in the same place.
  // Below the passage where the viewport has room, above it otherwise; place()'s own
  // clamp has the last word, so a passage too tall for either side simply keeps the
  // better spot.
  function placeComposer(left, top) {
    place(composer, left, top);
    const rects = pendingMarks().flatMap((where) =>
      where instanceof Range
        ? [...where.getClientRects()]
        : [where.getBoundingClientRect()],
    );
    const box = composer.getBoundingClientRect();
    const column = document.querySelector("main")?.getBoundingClientRect();
    if (rects.length && column && column.right + 8 + box.width <= rightEdge())
      return placeClear(
        composer,
        column.right + 8,
        Math.min(...rects.map((r) => r.top)),
      );
    // Vertically only: the document never scrolls sideways and body's margin keeps it clear
    // of the panel, so off-screen means scrolled past, and a mark scrolled past is not one
    // this box is standing on.
    const onScreen = (r) => r.bottom > BANNER_CLEAR && r.top < innerHeight;
    const behindBox = (r) =>
      r.left >= box.left &&
      r.right <= box.right &&
      r.top >= box.top &&
      r.bottom <= box.bottom;
    // A passage and a thing want different rules here, because
    // they are read differently. Covering the tail of a quote is fine — the user has read
    // it, and the mark still names where it starts. A card, a column, a metric is judged as
    // one object, so a box standing anywhere on it is a box between them and the thing they
    // are writing about. ⌥-click made that plain by opening the composer under the pointer,
    // which is by definition inside what was clicked.
    const whole = pendingMarks().some((where) => where instanceof Element);
    const touching = (r) =>
      r.left < box.right &&
      box.left < r.right &&
      r.top < box.bottom &&
      box.top < r.bottom;
    const clear = whole
      ? !rects.some((r) => onScreen(r) && touching(r))
      : rects.some((r) => onScreen(r) && !behindBox(r));
    if (!rects.length || clear) return;
    const below = Math.max(...rects.map((r) => r.bottom)) + 8;
    const above = Math.min(...rects.map((r) => r.top)) - box.height - 8;
    if (below + box.height <= innerHeight - 8) return place(composer, left, below);
    if (above >= BANNER_CLEAR) return place(composer, left, above);
    // Neither end has room, which a tall thing reaches easily: a board column is most of the
    // viewport before the box's own height is counted, and place()'s clamp would haul the box
    // back over it — the very thing this is here to stop. So go beside instead, even where
    // the margin is narrower than the box wants; the side is chosen rather than clamped,
    // because the clamp keeps a box on screen by sliding it left, back over the thing it
    // is avoiding.
    const rightOf = Math.max(...rects.map((r) => r.right)) + 8;
    const leftOf = Math.min(...rects.map((r) => r.left)) - box.width - 8;
    place(composer, rightOf + box.width <= rightEdge() ? rightOf : leftOf, top);
  }
  // Controls the page is standing on its own account, as against the ones in the runtime's
  // layer: a reply's widget is markup frozen in the log, and the layer's own buttons are
  // what floating chrome is allowed to sit beside. `data-lf-offer` is what makes a thing
  // pressable (`offer`), so this asks after any widget's controls without naming one.
  //
  // The line saying how many comments a block holds is the one control out here that is
  // still the layer's. It wears the marker because a screen reader reaches it by Tab, and
  // it is clipped to a pixel where it stands (it only takes a box on focus, fixed under
  // the banner) — so a float stepping down past it steps around nothing anyone can see,
  // which is exactly the movement this walk exists to prevent.
  const pageControls = () =>
    [...document.querySelectorAll(`[data-lf-offer]:not(.${noteClass()})`)].filter(
      (c) => !inChrome(c),
    );

  // The 💬 button carries the anchor it would open a composer on, so raising it and acting
  // on it can't come to different conclusions about what the reader picked. Visibility is
  // derived from that anchor and never read back off the stylesheet.
  const beside = (rect) => [rect.right + 6, rect.top - 6];
  // A float has one more thing to stay clear of, and it is the same kind of thing the
  // composer's mark is: a control standing on the page. The floats float and they don't.
  // A selection runs to the column's right edge on any line it fills, so `beside` puts
  // the button in the margin — which is where a suggestion hangs the row deciding the
  // change that selection just covered. The user's own gesture then hid the Accept
  // they were reaching for, and the press that would have dismissed the button was the
  // press it was covering. The composer's margin placement stands in the same column of
  // rows, so it takes the same walk.
  //
  // Down, and past each in turn, because the margin runs down the page: clearing one row
  // can land on the next, and walking a sorted list is the step the rows themselves take to
  // nudge apart. place()'s clamp still has the last word, so a float with nowhere left to
  // go keeps the best spot rather than leaving the screen.
  function placeClear(node, left, top) {
    place(node, left, top);
    const box = node.getBoundingClientRect();
    const sharing = pageControls()
      .map((c) => c.getBoundingClientRect())
      .filter((r) => r.width && r.left < box.right && box.left < r.right)
      .sort((a, b) => a.top - b.top);
    let y = box.top;
    for (const r of sharing)
      if (r.top < y + box.height && y < r.bottom) y = r.bottom + 6;
    if (y !== box.top) place(node, left, y);
  }
  let fabAnchor = null;
  function showFab(anchor, left, top) {
    fabAnchor = anchor;
    fab.style.display = anchor ? "block" : "none";
    if (anchor) placeClear(fab, left, top);
    paintHere(); // the c row names this anchor, so the line is one more rendering of it
  }
  // The one way an item under a gesture becomes the composer's anchor, so no two routes
  // can come to write different anchors for the same press.
  function openOnItem(item, from) {
    showFab(null);
    openComposer({ section: item.id }, "", from.left, from.top);
  }
  function openOnVisual({ element, part }, from) {
    showFab(null);
    openComposer({ section: element.id, visual: part.part }, "", from.left, from.top);
  }
  // The button follows the selection. What counts as one is measured on the quote it would
  // store, not on the selection's own toString(): those are different strings, and gating on
  // the one the reader sees while storing the one the document holds lets a two-character
  // quote through behind a rendered three-character selection — a quote short enough to match
  // almost anywhere.
  const MIN_QUOTE = 3;

  // What the button is on, decided here alone. The selection is read fresh; a visual find —
  // a clicked diagram or image, which has no text to select — comes in from the click that
  // found it, and a qualifying selection outranks it. The last branch is why order between
  // that click and the update queued behind its mouseup never matters: no selection speaks
  // for an element anchor, so the selection's absence takes down only a quote, and the
  // queued re-decide lands on the same outcome.
  function updateFab(found) {
    if (!anchoringIsReady()) {
      showFab(null);
      return;
    }
    const sel = pageSelection();
    const anchor = sel ? selectionAnchor(sel) : null;
    if (anchor?.quote.length >= MIN_QUOTE)
      showFab(anchor, ...beside(pageRange(sel).getBoundingClientRect()));
    else if (found) showFab(found.anchor, found.x + 6, found.y - 40);
    else if (fabAnchor?.quote) showFab(null);
  }
  // Where the pointer stopped is not the question; where the selection is, is. The guard
  // exists so a mouseup inside the runtime's layer — a click in the panel, the composer —
  // can't re-decide the button out from under an open draft. A drag that ends on a widget's
  // control is the opposite case: the user was selecting that control's label, and a
  // tab's name runs to within a few pixels of the strip button's padding, so the mouseup
  // lands on chrome while the selection is the page's. The snap runs in the same queued
  // step that raises the button, so the button lands beside the selection as snapped and
  // the capture reads the one the reader is looking at — and only for the primary
  // button, because a right button's release precedes its context menu, and growing the
  // selection there rewrites what Copy was aimed at.
  document.addEventListener("mouseup", (ev) => {
    if (!pageWords(ev.target) && !pageSelection()) return;
    setTimeout(() => {
      if (ev.button === 0) snapSelection();
      updateFab();
    });
  });
  // Selections made from the keyboard (shift-arrows, ⌘A) deserve the same button. Typing in
  // a box never does, whatever is selected elsewhere.
  document.addEventListener("keyup", (ev) => {
    if (takesLetters(ev.target)) return;
    if (!pageWords(ev.target) && !pageSelection()) return;
    setTimeout(updateFab);
  });
  // Floating chrome getting out of the way of a press somewhere else, which is a fact about
  // the press rather than about who receives it: the aim takes a press away from the page
  // (see claimPress) and must not take this with it, or the keyboard reference stays up over
  // the composer that press just opened. Hence one function, called from both.
  // The two side panels are absent from it on purpose. A float answers the press in front
  // of it and stands down behind it; the comment panel and the leaves tray are
  // workspaces the reader stood up, kept through a reload (PANEL_KEY, TRAY_KEY) and so
  // through a click all the more — a tray any press removes cannot be watched while
  // working, which is the tray's point. Each closes by its own button, its key, or Esc.
  function standDown(target) {
    if (!target.closest?.(".lf-fab, .lf-composer")) {
      showFab(null);
      // Keep a composer that holds unsent text open so a stray click can't drop it;
      // Cancel discards explicitly, and the draft is persisted regardless. Asked only of a
      // composer that is up, so an ordinary press in the page repaints nothing.
      if (composerIsOpen() && !composerInput.value) hideComposer();
    }
    if (referenceIsOpen() && !target.closest?.(".lf-help")) hideReference();
    // The press on the button itself is its own toggle, so it is not an outside click;
    // without that the open and this close would both run and the menu could never open.
    if (versionMenuIsOpen() && !target.closest?.(".lf-version-menu, .lf-version"))
      showVersionMenu(false);
  }
  document.addEventListener("mousedown", (ev) => standDown(ev.target));

  // What a click on the page means, decided once. A mark under the pointer opens its thread;
  // otherwise a diagram or image is a find handed to updateFab, which raises the same 💬
  // button on an element anchor — the id the visual lives under — unless a selection
  // outranks it.
  //
  // Once, because the hit-test reads layout and opening the panel rewrites it. Two handlers
  // each asking `markAt` looked independent and were not: the first one's setPanel() reflowed
  // the document out from under the second, which then missed the very mark it had just
  // opened and raised the comment button on top of it — leaving an element anchor set, which
  // midComposition() reads, so the page quietly stopped following new versions. The rule this
  // file already carries covers it: a guard that reads state another function wrote is a sign
  // the two are one function.
  // What a click anchors on whole, because there is no text in it to select: the page's
  // own pictures, and every widget that declares it renders as one.
  const visualSel = () =>
    [...tagsDeclaring((e) => e["x-visual"]), "svg", "img", "figure"].join(",");
  // The outermost match is the seat: a rendered diagram's inner svg carries an id
  // its renderer coined, and an anchor on that names nothing a version holds. The
  // id-bearing element around it is what answers, so a picture under no authored id
  // takes no anchor rather than one the next load would number differently.
  const visualAt = (target) => {
    const selector = visualSel();
    let element = target.closest?.(selector);
    if (!element) return null;
    while (element.parentElement?.closest(selector))
      element = element.parentElement.closest(selector);
    const id = element.closest("[id]:not(.lf-ui)")?.id;
    return id ? { element, id, part: visualPartAt(element, target) } : null;
  };

  document.addEventListener("click", (ev) => {
    if (!pageWords(ev.target)) return;
    // A press design mode did not take at the press is a press on prose: a drag that
    // selected words has the 💬 (updateFab, on the mouseup) and is not a click on the
    // block; a plain click comments on the block it landed in.
    if (designIsOn()) {
      if (pageSelection()) return;
      const target = designTarget(ev.target);
      if (target) openOnDesign(target, { left: ev.clientX + 6, top: ev.clientY - 40 });
      return;
    }
    const threadId = markAt(ev.clientX, ev.clientY);
    if (threadId) return showThread(threadId);
    // A link keeps its ordinary navigation. The universal Alt-click aim reaches a
    // commentable part inside it without letting either gesture do both things.
    if (ev.target.closest?.("a")) return;
    const visual = visualAt(ev.target);
    if (!visual) return;
    updateFab({
      anchor: visual.part
        ? { section: visual.id, visual: visual.part.part }
        : { section: visual.id },
      x: ev.clientX,
      y: ev.clientY,
    });
  });

  const fabAnchorAt = () => fabAnchor;
  return {
    BANNER_CLEAR,
    beside,
    fabAnchorAt,
    openOnItem,
    openOnVisual,
    placeClear,
    placeComposer,
    showFab,
    standDown,
    updateFab,
    visualAt,
  };
}
