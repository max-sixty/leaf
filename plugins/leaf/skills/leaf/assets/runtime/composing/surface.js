import { sameAnchor } from "../anchors.js";

export function createSelectionSurface({
  anchoringIsReady,
  anchorLabel,
  composer,
  composerInput,
  composerIsOpen,
  collapseKeyline,
  designIsOn,
  designTarget,
  fab,
  fabBar,
  hideComposer,
  hideReference,
  inChrome,
  isReactArmed,
  keylineEl,
  leavePageControl,
  markAt,
  noteClass,
  openComposer,
  openOnDesign,
  pageRange,
  pageScroller,
  pageSelection,
  pageText,
  pageWords,
  paintAnchors,
  paintHere,
  panel,
  panelCovers,
  paintStanding,
  pendingMarkParts,
  pointerAt,
  reactionsOn,
  referenceIsOpen,
  resolveAnchor,
  selectionAnchor,
  setReact,
  showThread,
  showVersionMenu,
  snapSelection,
  shownParts,
  shownRect,
  takesLetters,
  versionMenuIsOpen,
  visualActionAnchor,
  visualAt,
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
  // the viewport and above any key line it would cross, then store in the document.
  function place(node, left, top) {
    const x = Math.max(8, Math.min(left, rightEdge() - node.offsetWidth));
    node.style.left = x + "px";
    const keyline = keylineEl.getBoundingClientRect();
    const overlapsKeyline =
      keyline.height && x < keyline.right && x + node.offsetWidth > keyline.left;
    const bottom = overlapsKeyline ? keyline.top - 8 : innerHeight - 8;
    node.style.top =
      Math.max(BANNER_CLEAR, Math.min(top, bottom - node.offsetHeight)) +
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
    const marks = pendingMarkParts();
    const rects = marks.flatMap((where) =>
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
    const whole = marks.some((where) => where instanceof Element);
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
  // Two controls out here still belong to the layer. The line saying how many comments a
  // block holds and the visual's keyboard proxies wear the marker because a screen reader
  // reaches them by Tab. Both are clipped to a pixel where they stand and take a box only
  // on focus, fixed under the banner — so a float stepping down past either would step
  // around nothing anyone can see, exactly the movement this walk exists to prevent.
  const pageControls = () =>
    [...document.querySelectorAll(`[data-lf-offer]:not(.${noteClass()})`)].filter(
      (control) =>
        !inChrome(control) && !control.matches(".lf-visual-actions, .lf-visual-action"),
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
      // Keep the same small gutter sideways that the walk leaves below a row. A
      // one-glyph difference between system fonts must not decide whether two
      // controls almost touch or the float steps clear.
      .filter((r) => r.width && r.left < box.right + 6 && box.left < r.right + 6)
      .sort((a, b) => a.top - b.top);
    let y = box.top;
    for (const r of sharing)
      if (r.top < y + box.height && y < r.bottom) y = r.bottom + 6;
    if (y !== box.top) place(node, left, y);
  }
  let fabAnchor = null;
  let fabOrigin = null;
  const union = (rects) => {
    if (!rects.length) return null;
    const left = Math.min(...rects.map((rect) => rect.left));
    const top = Math.min(...rects.map((rect) => rect.top));
    const right = Math.max(...rects.map((rect) => rect.right));
    const bottom = Math.max(...rects.map((rect) => rect.bottom));
    return { left, top, right, bottom, width: right - left, height: bottom - top };
  };
  // A visual's durable anchor is also the geometry authority. Resolve it again after a
  // reflow instead of remembering where inside the target the pointer happened to land.
  function anchorBox(anchor) {
    if (anchor?.quote) {
      const selection = pageSelection();
      const current = selection ? selectionAnchor(selection) : null;
      return current && sameAnchor(anchor, current)
        ? pageRange(selection).getBoundingClientRect()
        : null;
    }
    const found = anchor ? resolveAnchor(anchor, pageText()) : null;
    if (!found?.element) return null;
    const clips = new Map();
    return union(
      (found.marks ?? shownParts(found.element))
        .map((part) => shownRect(part, clips))
        .filter(Boolean),
    );
  }
  // The bar stands beside its target where there is room and above it where clamping
  // would otherwise cover the thing that says what the actions are about.
  function placeFab(target = anchorBox(fabAnchor)) {
    if (!fabAnchor || !target) return false;
    placeClear(fabBar, ...beside(target));
    const box = fabBar.getBoundingClientRect();
    if (
      box.left < target.right &&
      box.right > target.left &&
      box.top < target.bottom &&
      box.bottom > target.top
    )
      placeClear(fabBar, target.right - box.width, target.top - box.height - 6);
    return true;
  }
  function showFab(
    anchor,
    target = null,
    { returnFocus = "target", origin = null } = {},
  ) {
    const previous = fabAnchor;
    const leavingBar = !anchor && fabBar.contains(document.activeElement);
    const returnTarget =
      leavingBar && previous && !previous.quote
        ? fabOrigin?.isConnected
          ? fabOrigin
          : visualActionAnchor(previous)
        : null;
    fabAnchor = anchor;
    fabOrigin = fabAnchor && origin?.isConnected ? origin : null;
    fabBar.style.display = fabAnchor ? "inline-flex" : "none";
    // Comment's own display is stated beside the bar's, being what the passage sweeps
    // read to know a passage raised the button.
    fab.style.display = fabAnchor ? "block" : "none";
    if (fabAnchor) {
      const label = anchorLabel(fabAnchor).replace(/^§\s*/, "");
      fabBar.setAttribute(
        "aria-label",
        label ? `Comment or react on ${label}` : "Comment or react",
      );
      // The tokens already standing on this very anchor read pressed, and a press on one
      // takes it back (reactHere): the bar is the strip's shape on the page.
      paintStanding(fabBar, reactionsOn(fabAnchor));
      if (!placeFab(target ?? anchorBox(fabAnchor))) {
        fabAnchor = null;
        fabOrigin = null;
        fabBar.style.display = "none";
        fab.style.display = "none";
      }
    }
    if (!sameAnchor(previous, fabAnchor)) paintAnchors();
    paintHere(); // the c row names this anchor, so the line is one more rendering of it
    if (!fabAnchor && leavingBar && returnFocus !== "none") {
      if (returnFocus === "target" && returnTarget?.isConnected)
        returnTarget.focus({ preventScroll: true });
      else leavePageControl();
    }
  }
  let dismissedSelectionKeyup = false;
  function dismissFab() {
    dismissedSelectionKeyup = Boolean(pageSelection() || fabAnchor?.quote);
    pageSelection()?.removeAllRanges();
    showFab(null);
  }
  function refreshFab() {
    if (!fabAnchor) return;
    if (fabAnchor.quote) updateFab();
    else if (!placeFab()) showFab(null, null, { returnFocus: "page" });
  }
  // The one way an item under a gesture becomes the composer's anchor, so no two routes
  // can come to write different anchors for the same press.
  function openOnItem(item, from) {
    showFab(null, null, { returnFocus: "none" });
    openComposer({ section: item.id }, "", from.left, from.top);
  }
  // The aim has one activation door for pointer and keyboard. A whole item raises the
  // cheap-answer bar; a declared visual part opens its anchored composer directly.
  function activateAimTarget({ anchor }, from) {
    if (!anchor.visual) return showFab(anchor);
    showFab(null, null, { returnFocus: "none" });
    openComposer(anchor, "", from.left, from.top);
  }
  // The button follows the selection. What counts as one is measured on the quote it would
  // store, not on the selection's own toString(): those are different strings, and gating on
  // the one the reader sees while storing the one the document holds lets a two-character
  // quote through behind a rendered three-character selection — a quote short enough to match
  // almost anywhere.
  const MIN_QUOTE = 3;

  // A visual activation is an explicit target and therefore outranks a selection retained
  // from an earlier gesture. Without one, the live selection remains the target.
  function updateFab(found, { origin = null } = {}) {
    if (!anchoringIsReady()) {
      showFab(null);
      return;
    }
    if (found) {
      showFab(found.anchor, null, { origin });
      return;
    }
    const sel = pageSelection();
    const anchor = sel ? selectionAnchor(sel) : null;
    if (anchor?.quote.length >= MIN_QUOTE) {
      const picked = pageRange(sel).getBoundingClientRect();
      showFab(anchor, picked);
    } else if (fabAnchor?.quote) showFab(null);
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
  let selectionUpdate = null;
  const scheduleSelectionUpdate = () => {
    if (selectionUpdate) return;
    selectionUpdate = setTimeout(() => {
      selectionUpdate = null;
      updateFab();
    });
  };
  let pointerSelecting = false;
  let selectionChangedDuringPress = false;
  let selectionDragged = false;
  let selectionRangeDuringPress = null;
  let selectionPressPoint = null;
  let actionPress = false;
  let targetActivation = false;
  const rememberPointerSelection = () => {
    const selection = pageSelection();
    const anchor = selection ? selectionAnchor(selection) : null;
    if (anchor?.quote?.length >= MIN_QUOTE)
      selectionRangeDuringPress = pageRange(selection).cloneRange();
  };
  document.addEventListener(
    "pointerdown",
    (ev) => {
      // Capture the old range before the browser's pointerdown default can collapse it.
      // This is needed when the reader drags across exactly the passage already selected.
      pointerSelecting = ev.isPrimary && ev.button === 0 && pageWords(ev.target);
      selectionChangedDuringPress = false;
      selectionDragged = false;
      selectionRangeDuringPress = null;
      selectionPressPoint = pointerSelecting ? { x: ev.clientX, y: ev.clientY } : null;
      const selection = pointerSelecting ? pageSelection() : null;
      if (selection) {
        const range = pageRange(selection);
        if (range.intersectsNode(ev.target)) rememberPointerSelection();
      }
      actionPress = Boolean(
        ev.target.closest?.(".lf-fab-bar, .lf-react-strip, .lf-composer"),
      );
    },
    true,
  );
  document.addEventListener("pointermove", (ev) => {
    if (!pointerSelecting || !selectionPressPoint) return;
    selectionDragged ||=
      Math.hypot(
        ev.clientX - selectionPressPoint.x,
        ev.clientY - selectionPressPoint.y,
      ) > 3;
  });
  const finishPointerSelection = () => {
    if (pointerSelecting) scheduleSelectionUpdate();
    pointerSelecting = false;
    setTimeout(() => {
      actionPress = false;
    });
  };
  document.addEventListener("pointerup", finishPointerSelection);
  document.addEventListener("pointercancel", finishPointerSelection);
  // Touch handles and browser selection commands do not owe the page a mouseup or keyup.
  // During a pointer drag, the completed gesture below remains the one that snaps and
  // places the passage; presses on the action surface must not retract their own target.
  document.addEventListener("selectionchange", () => {
    if (pointerSelecting) {
      selectionChangedDuringPress = true;
      rememberPointerSelection();
      return;
    }
    if (actionPress || targetActivation || takesLetters(document.activeElement)) return;
    scheduleSelectionUpdate();
  });
  document.addEventListener("mouseup", (ev) => {
    if (actionPress) return;
    if (!pageWords(ev.target) && !pageSelection()) return;
    clearTimeout(selectionUpdate);
    selectionUpdate = setTimeout(() => {
      selectionUpdate = null;
      if (ev.button === 0) snapSelection();
      updateFab();
    });
  });
  // Selections made from the keyboard (shift-arrows, ⌘A) deserve the same button. Typing in
  // a box never does, whatever is selected elsewhere.
  document.addEventListener("keyup", (ev) => {
    if (dismissedSelectionKeyup) {
      dismissedSelectionKeyup = false;
      if (ev.key === "Escape") return;
    }
    if (isReactArmed()) return;
    if (takesLetters(ev.target) || inChrome(ev.target)) return;
    if (!pageWords(ev.target) && !pageSelection()) return;
    scheduleSelectionUpdate();
  });
  // Floating chrome getting out of the way of a press somewhere else, which is a fact about
  // the press rather than about who receives it: the aim takes a press away from the page
  // (see claimPress) and must not take this with it, or the keyboard reference stays up over
  // the composer that press just opened. Hence one function, called from both.
  // The two side panels are absent from it on purpose. A float answers the press in front
  // of it and stands down behind it; the thread panel and the leaves tray are
  // workspaces the reader stood up, kept through a reload (PANEL_KEY, TRAY_KEY) and so
  // through a click all the more — a tray any press removes cannot be watched while
  // working, which is the tray's point. Each closes by its own button, its key, or Esc.
  function standDown(target) {
    const visual = visualAt(target);
    const sameVisual =
      visual &&
      !fabAnchor?.quote &&
      fabAnchor?.section === visual.id &&
      fabAnchor?.visual === visual.part?.part;
    if (
      !sameVisual &&
      !target.closest?.(".lf-fab-bar, .lf-react-strip, .lf-composer")
    ) {
      showFab(null, null, { returnFocus: "page" });
      // The armed react press goes with the bar it was armed on.
      setReact(false);
      // Keep a composer that holds unsent text open so a stray click can't drop it;
      // Cancel discards explicitly, and the draft is persisted regardless. Asked only of a
      // composer that is up, so an ordinary press in the page repaints nothing.
      if (composerIsOpen() && !composerInput.value) hideComposer();
    }
    if (referenceIsOpen() && !target.closest?.(".lf-help")) hideReference();
    if (!target.closest?.(".lf-help, .lf-keyline")) collapseKeyline();
    // The press on the button itself is its own toggle, so it is not an outside click;
    // without that the open and this close would both run and the menu could never open.
    if (versionMenuIsOpen() && !target.closest?.(".lf-version-menu, .lf-version"))
      showVersionMenu(false);
  }
  document.addEventListener("mousedown", (ev) => standDown(ev.target));

  // What a click on the page means, decided once. A mark under the pointer opens its thread;
  // otherwise a diagram or image is a find handed to updateFab, which raises the same 💬
  // button on an element anchor — the id the visual lives under. A newly dragged passage
  // outranks the compatibility click at its endpoint; an older retained selection does not.
  //
  // Once, because the hit-test reads layout and opening the panel rewrites it. Two handlers
  // each asking `markAt` looked independent and were not: the first one's setPanel() reflowed
  // the document out from under the second, which then missed the very mark it had just
  // opened and raised the comment button on top of it — leaving an element anchor set, which
  // midComposition() reads, so the page quietly stopped following new versions. The rule this
  // file already carries covers it: a guard that reads state another function wrote is a sign
  // the two are one function.
  function activateVisual(anchor, from = null) {
    clearTimeout(selectionUpdate);
    selectionUpdate = null;
    targetActivation = true;
    const selection = getSelection();
    if (selection?.rangeCount) selection.removeAllRanges();
    updateFab({ anchor }, { origin: from });
    if (from)
      fabBar
        .querySelector("button, [data-lf-offer][tabindex]")
        ?.focus({ preventScroll: true });
    setTimeout(() => {
      targetActivation = false;
    });
  }

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
    // The record rather than this event's own coordinates, for the reason the record is
    // kept from a pointer event at all (pointer.js): `click` is a legacy mouse event and
    // carries the pointer's place rounded to a whole pixel, while markAt measures against
    // getClientRects, whose edges are floats. Asked at the rounded point this answered a
    // different thread than refreshHover had just promised at the true one — a quote lit
    // up under the hand and a press on it opening nothing.
    //
    // A click with no press behind it carries 0,0 rather than a position — `offer` calls
    // click() to supply the keys a span doesn't come with — and the record would answer
    // for wherever the pointer is parked, so that one keeps reading the event.
    const point = ev.detail ? pointerAt() : { x: ev.clientX, y: ev.clientY };
    const threadId = markAt(point.x, point.y);
    if (threadId) return showThread(threadId);
    // Native controls, including links, keep their ordinary activation. visualAt applies
    // the same unclaimed-gesture rule used when keyboard proxies are discovered.
    const visual = visualAt(ev.target);
    if (!visual) return;
    let selection = pageSelection();
    let selected = selection ? selectionAnchor(selection) : null;
    // A pointer drag that ends over a diagram label produces a compatibility click too.
    // Selection mutation or deliberate movement says that passage was this gesture's
    // target, even when it happens to equal the passage selected before the press.
    if (
      ev.detail &&
      ((selected?.quote?.length >= MIN_QUOTE &&
        (selectionChangedDuringPress || selectionDragged)) ||
        (selectionDragged && selectionRangeDuringPress))
    ) {
      const completed =
        selected?.quote?.length >= MIN_QUOTE
          ? pageRange(selection).cloneRange()
          : selectionRangeDuringPress;
      clearTimeout(selectionUpdate);
      selectionUpdate = setTimeout(() => {
        selectionUpdate = null;
        const restored = getSelection();
        restored.removeAllRanges();
        restored.addRange(completed);
        snapSelection();
        updateFab();
      });
      return;
    }
    activateVisual(
      visual.part
        ? { section: visual.id, visual: visual.part.part }
        : { section: visual.id },
    );
  });

  const fabAnchorAt = () => fabAnchor;
  return {
    BANNER_CLEAR,
    activateVisual,
    beside,
    dismissFab,
    fabAnchorAt,
    openOnItem,
    activateAimTarget,
    placeClear,
    placeComposer,
    refreshFab,
    showFab,
    standDown,
    updateFab,
  };
}
