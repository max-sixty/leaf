export function createBannerShelf({ banner, el, pageScroller }) {
  const bannerActions = el("div", "lf-banner-actions");

  // Overflow is useful only when the destination a reader reaches is fully visible.
  // Native focus scrolling is inconsistent for the last few pixels of an overflow row,
  // and it does not account for an outset ring. Spend the shelf's reserved ring room
  // explicitly.
  function revealFocus(control) {
    if (!bannerActions.contains(control) || !control.getClientRects().length) return;
    const shelf = bannerActions.getBoundingClientRect();
    const box = control.getBoundingClientRect();
    const style = getComputedStyle(control);
    const outset =
      (Number.parseFloat(style.outlineWidth) || 0) +
      (Number.parseFloat(style.outlineOffset) || 0);
    if (box.left - outset < shelf.left)
      bannerActions.scrollLeft -= shelf.left - box.left + outset;
    else if (box.right + outset > shelf.right)
      bannerActions.scrollLeft += box.right + outset - shelf.right;
  }
  bannerActions.addEventListener("focusin", (event) => revealFocus(event.target));

  // The controls the banner's news arrives as, each present only while it has something
  // to say. Room a control has once taken is room it keeps for the rest of the page's
  // life. A live root pays nothing for news it may never get. A pinned version is
  // different: falling behind is part of its contract, so it reserves the future chip
  // before publication can move Comments or approval under a reaching pointer. Once any
  // news has stood, the rest of the row cannot close ranks over its place when it goes
  // quiet again.
  //
  // One setter stating the whole outcome, per showComposer and showFab, so no caller has
  // to know which of the two ways of being absent this control is currently in.
  function showNews(control, on) {
    // News can arrive while a deferred activation leaves the reader working in this live
    // banner. Keep a focused later address at the same screen coordinate as a control is
    // added or removed before it; focus remaining on an element nobody can see is not
    // preservation. The shelf gains exactly the new room, so this adjustment has the same
    // range as the displacement it answers.
    const focused = bannerActions.contains(document.activeElement)
      ? document.activeElement
      : null;
    const focusedLeft = focused?.getBoundingClientRect().left;
    const siblings = [...bannerActions.children];
    const focusedIndex = siblings.indexOf(control);
    const focusTransfer =
      focused === control && !on
        ? [
            ...siblings.slice(focusedIndex + 1),
            ...siblings.slice(0, focusedIndex).reverse(),
          ].find((candidate) => {
            const style = getComputedStyle(candidate);
            return (
              candidate.getClientRects().length &&
              style.display !== "none" &&
              style.visibility !== "hidden" &&
              !candidate.matches(":disabled, [aria-disabled='true']")
            );
          })
        : null;
    if (on) reserveNewsSlot(control);
    control.classList.toggle("lf-news-shown", on);
    control.style.display = on || control.dataset.lfReserved ? "" : "none";
    control.style.visibility = on ? "" : "hidden";
    if (focusTransfer) {
      focusTransfer.focus({ preventScroll: true });
      revealFocus(focusTransfer);
    } else if (focused && focused !== control && focused.getClientRects().length) {
      // A scroll assignment may quantize a fractional layout delta to the nearest device
      // pixel. Read the residual once and spend it too, so news cannot leave a focused
      // destination a single CSS pixel from the place the reader was holding.
      for (let pass = 0; pass < 2; pass++) {
        const delta = focused.getBoundingClientRect().left - focusedLeft;
        if (Math.abs(delta) < 0.01) break;
        bannerActions.scrollLeft += delta;
      }
      revealFocus(focused);
    }
  }

  function reserveNewsSlot(control) {
    control.dataset.lfReserved = "1";
  }

  // A hidden scrollbar keeps the banner calm, but it must not turn overflow into a
  // trackpad-only route. A vertical wheel first travels along a shelf that can still
  // move; any remainder goes to the page scroller explicitly, because Chromium keeps
  // an ordinary uncancelled wheel captured by the overflow box even at its boundary.
  bannerActions.addEventListener(
    "wheel",
    (event) => {
      // Chromium reports pinch-to-zoom as Ctrl+wheel. Leave browser zoom, modified mouse
      // gestures, and gestures already carrying a horizontal intention to the platform.
      if (
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        Math.abs(event.deltaY) <= Math.abs(event.deltaX)
      )
        return;
      const shelfUnit =
        event.deltaMode === 1
          ? 16
          : event.deltaMode === 2
            ? bannerActions.clientWidth
            : 1;
      const pageUnit =
        event.deltaMode === 1
          ? 16
          : event.deltaMode === 2
            ? pageScroller.clientHeight
            : 1;
      const shelfDelta = event.deltaY * shelfUnit;
      const before = bannerActions.scrollLeft;
      const limit = Math.max(0, bannerActions.scrollWidth - bannerActions.clientWidth);
      bannerActions.scrollLeft = Math.max(0, Math.min(limit, before + shelfDelta));
      const consumed = bannerActions.scrollLeft - before;
      const remainder = shelfDelta
        ? 1 - Math.min(1, Math.abs(consumed / shelfDelta))
        : 0;
      const pageBefore = pageScroller.scrollTop;
      const pageLocked = getComputedStyle(pageScroller).overflowY === "hidden";
      if (remainder && !pageLocked)
        pageScroller.scrollTop += event.deltaY * pageUnit * remainder;
      if (bannerActions.scrollLeft !== before || pageScroller.scrollTop !== pageBefore)
        event.preventDefault();
    },
    { passive: false },
  );

  // The document deliberately scrolls in body so its bar sits beside a standing panel.
  // Native touch that begins in fixed chrome never retargets to that non-root scroller,
  // leaving a dead strip across the top of touch laptops and phones. Lock a one-finger
  // gesture after a small intentional move: vertical travel follows the page under the
  // finger, while horizontal travel in the shelf and every multi-touch gesture remain
  // the browser's, preserving its native horizontal pan and pinch zoom.
  let touch = null;
  banner.addEventListener(
    "touchstart",
    (event) => {
      if (event.touches.length !== 1) {
        touch = null;
        return;
      }
      const point = event.touches[0];
      touch = {
        id: point.identifier,
        x: point.clientX,
        y: point.clientY,
        lastY: point.clientY,
        axis: null,
      };
    },
    { passive: true },
  );
  banner.addEventListener(
    "touchmove",
    (event) => {
      if (!touch || event.touches.length !== 1) {
        touch = null;
        return;
      }
      const point = [...event.touches].find(
        (candidate) => candidate.identifier === touch.id,
      );
      if (!point) {
        touch = null;
        return;
      }
      if (!touch.axis) {
        const dx = point.clientX - touch.x;
        const dy = point.clientY - touch.y;
        if (Math.max(Math.abs(dx), Math.abs(dy)) < 4) return;
        touch.axis = Math.abs(dy) > Math.abs(dx) ? "page" : "horizontal";
      }
      if (touch.axis !== "page") return;
      const before = pageScroller.scrollTop;
      const delta = touch.lastY - point.clientY;
      touch.lastY = point.clientY;
      if (getComputedStyle(pageScroller).overflowY !== "hidden")
        pageScroller.scrollTop += delta;
      if (pageScroller.scrollTop !== before) event.preventDefault();
    },
    { passive: false },
  );
  for (const event of ["touchend", "touchcancel"])
    banner.addEventListener(event, () => (touch = null), { passive: true });

  return { bannerActions, reserveNewsSlot, revealFocus, showNews };
}
