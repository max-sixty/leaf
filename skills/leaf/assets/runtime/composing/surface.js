import { sameAnchor } from "../anchors.js";
import { documentPoint } from "../geometry.js";

export function createSelectionSurface({
  anchoringIsReady,
  anchorLabel,
  banner,
  blockAt,
  composerIsOpen,
  closeVersionMenu,
  collapseKeyline,
  designIsOn,
  designTarget,
  fab,
  fabBar,
  fabInput,
  hideComposer,
  hideReference,
  hasOtherResponses,
  inChrome,
  isReactArmed,
  keylineEl,
  leavePageControl,
  markAt,
  noteClass,
  openComposer,
  openOnDesign,
  pageRange,
  pageSelection,
  pageText,
  pageWords,
  paintAnchors,
  paintHere,
  panel,
  panelCovers,
  paintStanding,
  pointerAt,
  reactionContextContains,
  reactionsOn,
  referenceIsOpen,
  resolveAnchor,
  selectionAnchor,
  setReact,
  showThread,
  snapSelection,
  shownParts,
  shownRect,
  takesLetters,
  versionMenuIsOpen,
  visualActionAnchor,
  visualAt,
}) {
  // ---------- selection → comment ----------
  // Floating UI stays inside the document layout shell. Body already ends at a standing
  // right panel's edge through its margin, while the root scrollport owns the browser's
  // gutter. A covering sheet is the one strip body does not yield, so its width comes off
  // here.
  const rightEdge = () =>
    (panelCovers()
      ? innerWidth - panel.offsetWidth
      : Math.min(innerWidth, document.body.getBoundingClientRect().right)) - 8;
  // The floats live in the document — they scroll with the passage they stand beside —
  // while every caller reasons in viewport terms: rects, the pointer, the banner's own
  // band. The fixed floor covers the ordinary one-line banner; its live box takes over
  // when compact chrome wraps to a second line.
  const BANNER_CLEAR = 48;
  const topEdge = () =>
    Math.max(BANNER_CLEAR, banner.getBoundingClientRect().bottom + 6);
  const leftEdge = (node, left) =>
    Math.max(8, Math.min(left, rightEdge() - node.offsetWidth));
  const bottomEdge = (left, width) => {
    const keyline = keylineEl.getBoundingClientRect();
    return keyline.height && left < keyline.right && left + width > keyline.left
      ? keyline.top - 8
      : innerHeight - 8;
  };
  // So the one writer of their position is where the coordinates change space: clamp in
  // the viewport and above any key line it would cross, then store in the document.
  function place(node, left, top) {
    const x = leftEdge(node, left);
    const bottom = bottomEdge(x, node.offsetWidth);
    const at = documentPoint(
      x,
      Math.max(topEdge(), Math.min(top, bottom - node.offsetHeight)),
    );
    node.style.left = at.left + "px";
    node.style.top = at.top + "px";
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

  // The response bar carries the anchor its field will submit on, so targeting and typing
  // cannot come to different conclusions about what the reader picked. Visibility is
  // derived from that anchor and never read back off the stylesheet.
  const beside = (rect) => [rect.right + 6, rect.top - 6];
  // The viewport, the target and the page's controls define one set of free bands.
  // Walking down past controls and then clamping to the viewport could put a growing
  // editor back on its target. Choose a band first; CSS can then size the field to it.
  function placeClear(node, left, top, target) {
    const x = leftEdge(node, left);
    const bottom = bottomEdge(x, node.offsetWidth);
    const sharing = [...pageControls().map((c) => c.getBoundingClientRect()), target]
      .filter((r) => r.width && r.left < x + node.offsetWidth + 6 && x < r.right + 6)
      .sort((a, b) => a.top - b.top);
    const bands = [];
    let start = topEdge();
    for (const r of sharing) {
      const end = Math.min(bottom, r.top - 6);
      if (end > start) bands.push({ top: start, bottom: end });
      start = Math.max(start, r.bottom + 6);
    }
    if (start < bottom) bands.push({ top: start, bottom });
    const minimum = composerIsOpen()
      ? parseFloat(getComputedStyle(fabInput).minHeight)
      : node.offsetHeight;
    const candidates = bands
      .filter((band) => band.bottom - band.top >= minimum)
      .map((band) => {
        const height = Math.min(node.offsetHeight, band.bottom - band.top);
        const y = Math.max(band.top, Math.min(top, band.bottom - height));
        const distance = Math.max(target.top - y - height, y - target.bottom, 0);
        return { left: x, top: y, height, room: band.bottom - y, distance };
      });
    // Stay associated with the target, then keep as much writing visible as that band
    // allows. A distant gap is not a better seat just because it is taller. A target
    // filling the entire viewport leaves no free band, so the ordinary viewport clamp
    // remains the last resort.
    return (
      candidates.sort(
        (a, b) =>
          a.distance - b.distance ||
          b.height - a.height ||
          Math.abs(a.top - top) - Math.abs(b.top - top),
      )[0] ?? { left: x, top, room: node.offsetHeight }
    );
  }
  let fabAnchor = null;
  let fabOrigin = null;
  let fabFloating = true;
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
      if (current && sameAnchor(anchor, current))
        return pageRange(selection).getBoundingClientRect();
      // Entering the compact field deliberately collapses the browser selection after
      // its durable passage has been captured. Resolve that passage again so layout can
      // keep the field beside it; an ordinary selection collapse still returns null and
      // lets updateFab dismiss the response surface.
      // The reactions palette temporarily owns focus and may itself be re-seated during
      // a responsive layout change. The open composer is the durable proof that this
      // captured passage still belongs to the response transaction; native selection is
      // no longer available once the textarea took focus.
      if (!composerIsOpen() && !fabHoldsCapturedPassage()) return null;
      const found = resolveAnchor(anchor, pageText());
      if (!found?.segments?.length) return null;
      const range = document.createRange();
      range.setStart(found.segments[0].node, found.segments[0].start);
      range.setEnd(found.segments.at(-1).node, found.segments.at(-1).end);
      return range.getBoundingClientRect();
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
  // The passage remains the exact anchor, but its containing paragraph is not spare
  // space: a short selection cannot lend the words after it to the response field.
  // Keep the bar beside that whole block, or above/below it when the rail is too narrow.
  function placeFab(target = anchorBox(fabAnchor)) {
    if (!fabAnchor || !target) return false;
    const block = fabAnchor.quote && fabTargetAt();
    const clips = new Map();
    const keepClear =
      (block &&
        union(
          shownParts(block)
            .map((part) => shownRect(part, clips))
            .filter(Boolean),
        )) ||
      target;
    if (composerIsOpen()) {
      // CSS owns content sizing. Geometry contributes only the real room the field
      // can use, including the bar's other controls, before deciding where it stands.
      fabBar.style.setProperty("--lf-response-room", `${rightEdge() - 8}px`);
      fabBar.style.removeProperty("--lf-response-height-room");
      const controls = fabBar.offsetWidth - fabInput.offsetWidth;
      const besideRoom = rightEdge() - keepClear.right - 6 - controls;
      const minimum = parseFloat(getComputedStyle(fabInput).minWidth);
      fabBar.style.setProperty(
        "--lf-response-room",
        `${besideRoom >= minimum ? besideRoom : rightEdge() - 8 - controls}px`,
      );
    }
    const left =
      keepClear.right + 6 + fabBar.offsetWidth <= rightEdge()
        ? keepClear.right + 6
        : keepClear.right - fabBar.offsetWidth;
    const at = placeClear(fabBar, left, target.top - 6, keepClear);
    fabBar.style.setProperty("--lf-response-height-room", `${at.room}px`);
    place(fabBar, at.left, at.top);
    return true;
  }
  function showFab(
    anchor,
    target = null,
    { returnFocus = "target", origin = null, place = true } = {},
  ) {
    const previous = fabAnchor;
    const previousOrigin = fabOrigin;
    const leavingBar = !anchor && fabBar.contains(document.activeElement);
    const returnTarget =
      leavingBar && previous && !previous.quote
        ? previousOrigin?.isConnected
          ? previousOrigin
          : previousOrigin
            ? visualActionAnchor(previous)
            : null
        : null;
    if (!anchor && composerIsOpen()) hideComposer();
    fabAnchor = anchor;
    fabFloating = !fabAnchor || place;
    fabOrigin = fabAnchor && origin?.isConnected ? origin : null;
    fabBar.style.display = fabAnchor ? "inline-flex" : "none";
    fabInput.style.display = fabAnchor && composerIsOpen() ? "block" : "none";
    const responses = fabBar.querySelector(":scope > .lf-react-trigger");
    if (responses) responses.hidden = !fabAnchor || !hasOtherResponses(fabAnchor);
    // Comment returns from the bar's choice state to this same field. At rest the input
    // itself is the comment affordance.
    fab.style.display = fabAnchor ? "" : "none";
    if (fabAnchor) {
      const label = anchorLabel(fabAnchor).replace(/^§\s*/, "");
      fabBar.setAttribute("aria-label", label ? `Respond to ${label}` : "Respond");
      fabInput.setAttribute("aria-label", label ? `Comment on ${label}` : "Comment");
      // The tokens already standing on this very anchor read pressed, and a press on one
      // takes it back (reactHere): the bar is the strip's shape on the page.
      paintStanding(fabBar, reactionsOn(fabAnchor));
      // A docked margin control can name an item whose rendered box is currently off
      // screen. `r` still needs the durable anchor so it can extend that existing item;
      // in that route the floating bar is never painted and placement is deliberately
      // skipped. Every route that actually shows the bar keeps the geometry gate.
      if (place && !placeFab(target ?? anchorBox(fabAnchor))) {
        fabAnchor = null;
        fabOrigin = null;
        if (composerIsOpen()) hideComposer();
        fabBar.style.display = "none";
        fabInput.style.display = "none";
        fab.style.display = "none";
      }
    }
    if (!sameAnchor(previous, fabAnchor)) paintAnchors();
    paintHere(); // the c row names this anchor, so the line is one more rendering of it
    if (!fabAnchor && returnFocus !== "none") {
      if (leavingBar && returnFocus === "target" && returnTarget?.isConnected)
        returnTarget.focus({ preventScroll: true });
      else if (
        leavingBar ||
        (returnFocus === "page" && document.activeElement === previousOrigin)
      )
        leavePageControl();
    }
  }
  let dismissedSelectionKeyup = false;
  function dismissFab() {
    dismissedSelectionKeyup = Boolean(pageSelection() || fabAnchor?.quote);
    pageSelection()?.removeAllRanges();
    if (composerIsOpen()) hideComposer();
    showFab(null);
  }
  function refreshFab() {
    // A target row holds its anchor without floating the bar; layout cannot reject that
    // semantic place merely because the target's rendered box has scrolled away.
    if (!fabAnchor || !fabFloating) return;
    if (fabAnchor.quote && (composerIsOpen() || fabHoldsCapturedPassage())) {
      if (!placeFab()) showFab(null, null, { returnFocus: "page" });
    } else if (fabAnchor.quote) updateFab();
    else if (!placeFab()) showFab(null, null, { returnFocus: "page" });
  }
  // The durable anchor names the authored coordinate an event can replay, while the
  // margin needs the rendered block the gesture is visibly on. Those are deliberately
  // different for selected words inside a paragraph without an ID: the event names its
  // enclosing section, but both the temporary picker and the standing receipt sit at
  // the paragraph. Match seatReactions' shadow-boundary rule so live and replay agree.
  const fabTargetAt = () => {
    if (!fabAnchor) return null;
    const found = resolveAnchor(fabAnchor, pageText());
    if (!found) return null;
    if (!fabAnchor.quote) return found.element;
    const block = blockAt(found.segments?.[0]?.node);
    if (!block) return found.element ?? null;
    const root = block.getRootNode();
    return root instanceof ShadowRoot ? root.host : block;
  };
  const fabReturnTo = () =>
    fabAnchor && !fabAnchor.quote
      ? fabOrigin?.isConnected
        ? fabOrigin
        : visualActionAnchor(fabAnchor)
      : null;
  // The one way an item under a gesture becomes the composer's anchor, so no two routes
  // can come to write different anchors for the same press.
  function openOnItem(item) {
    openComment({ section: item.id }, "", { carry: true });
  }
  // Keyboard selection names the target and immediately lands in its Comment field.
  function selectResponseTarget({ anchor }) {
    openComment(anchor, "", { carry: true });
  }
  // Alt-click already names Comment, so the field takes focus in the same transaction.
  function focusTargetComment({ anchor }) {
    openComment(anchor, "", { carry: true });
  }
  // Focusing text entry collapses a native page selection. Hold that browser-authored
  // selectionchange out of updateFab: the durable anchor is already captured, and letting
  // the collapse re-read it as no selection dismisses the field the reader just entered.
  function focusFabComment() {
    if (!fabAnchor) return;
    clearTimeout(selectionUpdate);
    selectionUpdate = null;
    fabInputTakingFocus = true;
    if (composerIsOpen()) fabInput.focus({ preventScroll: true });
    else openComment(structuredClone(fabAnchor), "");
  }
  const fabOptionsAvailable = () =>
    Boolean(fabBar.querySelector(":scope > .lf-react-trigger:not([hidden])"));
  function showFabOptions() {
    fabBar.querySelector(":scope > .lf-react-trigger")?.click();
  }
  // The response field follows the selection. What counts as one is measured on the quote it would
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
      openComment(found.anchor, "");
      if (origin) showFab(found.anchor, null, { origin });
      return;
    }
    const sel = pageSelection();
    const anchor = sel ? selectionAnchor(sel) : null;
    if (anchor?.quote.length >= MIN_QUOTE) {
      // Selecting words is still the browser's gesture. Open Leaf's response field beside
      // them without moving focus into it, so the live Selection remains available to Copy
      // and the native context menu. An explicit Comment press uses the same field and
      // focuses it through focusFabComment below.
      openComment(anchor, "", { focus: false });
    } else if (fabAnchor?.quote && !fabHoldsCapturedPassage()) showFab(null);
  }
  // Where the pointer stopped is not the question; where the selection is, is. The guard
  // exists so a mouseup inside the runtime's layer — a click in the panel, the composer —
  // can't re-decide the response surface out from under an open draft. A drag that ends on a widget's
  // control is the opposite case: the user was selecting that control's label, and a
  // tab's name runs to within a few pixels of the strip button's padding, so the mouseup
  // lands on chrome while the selection is the page's. The snap runs in the same queued
  // step that raises the field, so the bar lands beside the selection as snapped and
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
  let fabInputTakingFocus = false;
  function openComment(anchor, text, options = {}) {
    // Chromium may collapse the native page Selection before dispatching the textarea's
    // focus event. Mark the handoff first so that intermediate selectionchange cannot
    // dismiss the durable anchor the composer is opening on.
    fabInputTakingFocus = options.focus !== false;
    return openComposer(anchor, text, options);
  }
  function fabHoldsCapturedPassage() {
    return fabInputTakingFocus || fabBar.contains(document.activeElement);
  }
  fabInput.addEventListener("focus", () => {
    clearTimeout(selectionUpdate);
    selectionUpdate = null;
    fabInputTakingFocus = true;
  });
  fabInput.addEventListener("blur", () => {
    fabInputTakingFocus = false;
  });
  let primaryPointerPressed = false;
  // Whether the page's own words stood selected when the key line was last painted for
  // this press. The bar waits for the release; the Escape rung cannot, because from the
  // first glyph a drag takes, Escape clears the selection rather than letting go of the
  // control the reader is standing on, and until now nothing repainted the line inside a
  // press — the word only became true when the frame the press itself scheduled happened
  // to land after the drag had moved, and stayed a lie for a whole heartbeat when it
  // landed before. Only the crossing is painted: a drag growing a selection that already
  // stands says the same word, and repainting the chrome on every move of a drag would
  // put a whole `paintHere` inside every frame of one.
  let selectionStood = false;
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
      primaryPointerPressed = ev.isPrimary && ev.button === 0;
      pointerSelecting = ev.isPrimary && ev.button === 0 && pageWords(ev.target);
      selectionChangedDuringPress = false;
      selectionDragged = false;
      selectionRangeDuringPress = null;
      selectionPressPoint = pointerSelecting ? { x: ev.clientX, y: ev.clientY } : null;
      // Read here, ahead of the browser's own collapse, so the first crossing this press
      // makes is measured against what the line already says rather than against nothing.
      selectionStood = Boolean(pageSelection());
      const selection = pointerSelecting ? pageSelection() : null;
      if (selection) {
        const range = pageRange(selection);
        if (range.intersectsNode(ev.target)) rememberPointerSelection();
      }
      actionPress = Boolean(ev.target.closest?.(".lf-react-surface, .lf-composer"));
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
  const finishPointerSelection = (ev) => {
    // A mouse pointer is followed by the compatibility mouseup below, which performs the
    // sentence snap before opening the field. Opening from pointerup first would focus the
    // textarea and collapse the still-unsnapped Selection before mouseup can finish it.
    // Touch/pen and cancellation owe us no compatibility mouse event, so they keep this
    // direct route.
    if (
      primaryPointerPressed &&
      ev.type === "pointerup" &&
      ev.pointerType === "mouse"
    ) {
      // Keep selectionchange in the in-progress branch until compatibility mouseup.
      setTimeout(() => {
        actionPress = false;
      });
      return;
    }
    if (primaryPointerPressed) scheduleSelectionUpdate();
    primaryPointerPressed = false;
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
    if (primaryPointerPressed) {
      selectionChangedDuringPress = true;
      rememberPointerSelection();
      const stands = Boolean(pageSelection());
      if (stands !== selectionStood) {
        selectionStood = stands;
        paintHere();
      }
      return;
    }
    if (
      actionPress ||
      targetActivation ||
      fabHoldsCapturedPassage() ||
      takesLetters(document.activeElement)
    )
      return;
    scheduleSelectionUpdate();
  });
  document.addEventListener("mouseup", (ev) => {
    primaryPointerPressed = false;
    pointerSelecting = false;
    if (actionPress) return;
    if (!pageWords(ev.target) && !pageSelection()) return;
    clearTimeout(selectionUpdate);
    selectionUpdate = setTimeout(() => {
      selectionUpdate = null;
      if (ev.button === 0) snapSelection();
      updateFab();
    });
  });
  // Selections made from the keyboard (shift-arrows, ⌘A) deserve the same response bar. Typing in
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
      !target.closest?.(".lf-react-surface, .lf-composer") &&
      !reactionContextContains(target)
    ) {
      if (composerIsOpen()) hideComposer();
      showFab(null, null, { returnFocus: "page" });
      // The armed react press goes with the bar it was armed on.
      setReact(false);
    }
    if (referenceIsOpen() && !target.closest?.(".lf-help")) hideReference();
    if (!target.closest?.(".lf-help, .lf-keyline")) collapseKeyline();
    // The press on the button itself is its own toggle, so it is not an outside click;
    // without that the open and this close would both run and the menu could never open.
    if (versionMenuIsOpen() && !target.closest?.(".lf-version-menu, .lf-version"))
      closeVersionMenu();
  }
  document.addEventListener("mousedown", (ev) => standDown(ev.target));

  // What a click on the page means, decided once. A mark under the pointer opens its thread;
  // otherwise a diagram or image is a find handed to updateFab, which raises the same compact
  // field on an element anchor — the id the visual lives under. A newly dragged passage
  // outranks the compatibility click at its endpoint; an older retained selection does not.
  //
  // Once, because the hit-test reads layout and opening the panel rewrites it. Two handlers
  // each asking `markAt` looked independent and were not: the first one's setPanel() reflowed
  // the document out from under the second, which then missed the very mark it had just
  // opened and raised the comment field on top of it — leaving an element anchor set, which
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
      if (target) openOnDesign(target);
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
    fabOptionsAvailable,
    fabTargetAt,
    fabReturnTo,
    focusFabComment,
    openOnItem,
    focusTargetComment,
    placeClear,
    refreshFab,
    selectResponseTarget,
    showFab,
    showFabOptions,
    standDown,
    updateFab,
  };
}
