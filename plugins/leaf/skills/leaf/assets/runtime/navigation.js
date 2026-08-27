export function createNavigation({
  BANNER_CLEAR,
  REDUCED,
  SCROLL,
  beside,
  inChrome,
  inPanel,
  openOnItem,
  openThreads,
  pageScroller,
  panelCovers,
  panelIsOpen,
  scrollToElement,
  scrollToThread,
  setPanel,
  shownBox,
  shownRect,
  threadsBox,
}) {
  // Where a comment about this item is written: the composer, on the item, which is what a
  // click through the ⌥ aim already opens. It reached for the widget's own conversation seat
  // first for a while, on the reasoning that a widget holding a box for its conversation
  // should not be given a second one. That was the wrong shape. `openOnItem` writes
  // `{section: item.id}`, which is exactly the anchor `renderConversations` collects into
  // that seat — so the words land in the same conversation by either route, and the seat was
  // buying a focus landing at the price of five separate questions: escaping an
  // author-written id into a selector, whether the box can take focus at all (a settled
  // group's seat is inside `hidden="until-found"` and silently swallowed the press), which
  // box when the seat holds several threads, what design mode files, and where the reader
  // was already standing. One route answers all five by not asking them.
  //
  // The scroll is for the standing that has gone stale — an address or a Tab leaves the item
  // on screen, but focus outlives the scroll that put it there, and a box about something
  // off screen is a box about nothing the reader can see.
  function commentOnItem(item) {
    // Only where the item is not already in front of the reader. Travelling every time moved
    // the page under someone who could see the thing perfectly well: Tab leaves an item at an
    // edge (`block: nearest`), so centring took the page a third of a viewport with nothing on
    // screen to explain it — on the route this press exists for, and where the ⌥ aim it is the
    // twin of moves nothing at all. The travel is for the standing that has gone stale, focus
    // outliving the scroll that put it there: a box about something off screen is a box about
    // nothing the reader can see.
    //
    // What the page shows of it, which is the reading the aim's own paint takes
    // (`refreshAim`) — this being its keyboard twin, the two decide "is this in front of the
    // reader" the same way or they are not twins. `shownBox` alone is the box the item would
    // have, unclipped: an item scrolled out of a board's sideways scroller still reports one
    // inside the window, so a gate reading that called it showing and opened the box on
    // something off screen, which the unconditional travel it replaced never did. Any part
    // showing is enough, which is also what keeps a box taller than the window from jumping
    // to its top under a reader halfway down it.
    //
    // A collapsed ancestor zeroes its descendants' boxes, so a thing inside a shut
    // disclosure is never showing and takes the travel, `reveal` with it. Standing on the
    // summary itself is the one motion this drops: the disclosure stays shut and the box
    // opens on it where it is, rather than springing it open and reflowing the page under
    // the reader who was looking at it.
    //
    // Instant, and before the box is measured. Placing reads the item's box, so that has to
    // be the box the item keeps; and opening focuses the textarea, whose scroll-into-view
    // cancels a glide already under way — which is what left the item flush against an edge
    // rather than framed, and is not `openComposer`'s to give up, three other presses opening
    // that box against a passage they have not moved.
    const seen = shownRect(item, new Map());
    if (!seen || seen.bottom <= BANNER_CLEAR) scrollToElement(item, "instant");
    const [left, top] = beside(shownBox(item));
    openOnItem(item, { left, top });
  }
  // j/k walk the open threads: panel focus and the page highlight move as a pair — they are
  // two views of the same thread. Clamped at the ends, not wrapped; never empty, because the
  // keys are live only while open threads exist, and hasThreads counts what renderThreads
  // wrote here in the same synchronous pass.
  function stepThread(dir) {
    if (!panelIsOpen()) setPanel(true);
    const threads = openThreads();
    const at = threads.indexOf(document.activeElement?.closest?.(".lf-thread"));
    const next =
      threads[
        at === -1
          ? dir > 0
            ? 0
            : threads.length - 1
          : Math.max(0, Math.min(threads.length - 1, at + dir))
      ];
    // Landing the thread is the list's, off the focus it is about to take. A press at
    // either end of the walk is the exception the list cannot answer: it names the thread
    // the reader already stands on, so no focus moves and nothing fires, while the page
    // half of the press still travels. Both halves therefore go where they were pointed.
    const standing = next === document.activeElement;
    next.focus({ preventScroll: true });
    if (standing) next.scrollIntoView({ behavior: SCROLL, block: "nearest" });
    scrollToThread(next.dataset.id);
  }

  // Put the comment the reader is standing on against one edge of its list. This is
  // placement inside the panel, not travel to the passage the comment is about, so it
  // moves only the thread scroller and keeps the card's focus. Native scroll placement
  // reads the list's declared scroll-padding, including its sticky heading and focus-ring
  // room, from the same authority the j/k walk uses.
  function placeThreadEdge(thread, edge) {
    thread.scrollIntoView({ behavior: SCROLL, block: edge });
  }

  // d and u step the reader half a page down and up — less's pair, and half a page rather
  // than a whole one so the lines they were reading are still on screen to read on from.
  // The browser's own keys are left to the browser (Space, Home/End, PageUp/Down all reach
  // it untouched, and a test pins that); these are the runtime's.
  //
  // They move the region the reader is reading, which is the thread list wherever the
  // reader stands in the panel or the panel covers the page. Scrolling a region the
  // reader is not in reads to them as the key doing nothing, and then the document is
  // somewhere else when they look back at it.
  //
  // The step moves at the pace of the browser's own paging keys. Native paging is a quick
  // glide — PageDown covers a page here in ~140ms, and Space and the arrows ride the same
  // animator — but that animator is the compositor's and JS cannot ask for it, while
  // scrollTo's smooth takes three times as long over the same distance and has no dial,
  // which is what read as gradual when the step rode it. So the runtime drives the step
  // itself: PAGE_MS of easing out, each write `instant` rather than `auto` since a page is
  // free to set `scroll-behavior: smooth` on the box it scrolls (jumpBy says the same) and
  // a glide built from smooth writes would never land. A press mid-flight retargets from
  // the goal, so two quick presses move exactly a page; the goal is clamped, so pressing on
  // at the foot banks no debt for u to press back through; and the step stands down the
  // moment the box moves under another hand — a wheel, a centering — because the reader's
  // own gesture outranks a key's. Under reduced motion the step is a jump, the answer the
  // rest of the runtime's motion already gives (SCROLL).
  //
  // The page the step halves is the one the reader can see. The document's box lends its
  // top edge to the fixed banner, and scroll-padding-top — declared on that scroller, read
  // exactly so by scrollToElement — is where the box already says how much of itself stands
  // covered. The thread list says the same thing about itself: a stuck run heading covers
  // its top, so a half-page step there is half of what is left rather than half of the
  // box, which is the answer the reader wants — a step that landed them under the heading
  // would be a step onto words they cannot read.
  const PAGE_MS = 140;
  let glide = null; // {box, goal, wrote, raf}
  // The glide's claim on the box: it holds only while the box is where the glide last
  // wrote it. The tick asks before every write, and a press asks the same question before
  // trusting the goal — the reader can take the box between frames, and a press landing
  // in that gap otherwise measures from a goal the box has already left.
  const holding = (box) =>
    glide?.box === box && Math.abs(box.scrollTop - glide.wrote) <= 1;
  // The visible box used by page-edge navigation. A covering panel replaces the page;
  // beside it, the document keeps its own top and bottom.
  const seenScroller = () => (panelCovers() ? threadsBox : pageScroller);
  // Half-page keys follow the region the reader is working in. Focus can put them in a
  // panel beside the page; a covering panel remains the only visible region even when
  // focus is still on the banner control that opened it.
  const stepScroller = () => (inPanel() || panelCovers() ? threadsBox : pageScroller);
  // Which box scrolls a given element, for anything that has to name its scroller rather
  // than search for one. The document's for everything the document holds — and the
  // panel's own list for a widget an agent put in a reply, which is scrolled by that and
  // by nothing else. A drag naming the wrong one sits at the edge waiting for a scroll
  // that never comes.
  const scrollerFor = (el) => (inChrome(el) ? threadsBox : pageScroller);
  function stepPage(fraction) {
    const box = stepScroller();
    const clear = parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
    const from = holding(box) ? glide.goal : box.scrollTop;
    glideTo(box, from + fraction * (box.clientHeight - clear));
  }
  // One eased travel to a goal, shared by the half-page step and the chord's edges. The
  // goal is clamped here, so a step pressed on at the foot banks no debt for u to press
  // back through, and an edge may be asked for as the height it cannot exceed.
  function glideTo(box, goal) {
    goal = Math.max(0, Math.min(box.scrollHeight - box.clientHeight, goal));
    if (REDUCED) {
      box.scrollTo({ top: goal, behavior: "instant" });
      return;
    }
    cancelAnimationFrame(glide?.raf);
    const start = box.scrollTop;
    const t0 = performance.now();
    const tick = (now) => {
      if (!holding(box)) {
        glide = null; // the box moved under another hand; theirs wins
        return;
      }
      // Floored as well as capped: a rAF timestamp is its frame's start, which can precede
      // the press that scheduled the tick, and an unfloored t walks the ease out past the
      // start — to a write the box clamps, which the next tick then read as another hand.
      const t = Math.max(0, Math.min(1, (now - t0) / PAGE_MS));
      box.scrollTo({
        top: goal - (goal - start) * (1 - t) ** 3,
        behavior: "instant",
      });
      // Where the write left the box, not what it asked for: the box clamps at its ends
      // and snaps to pixels, and the claim the next tick tests is about the box.
      glide.wrote = box.scrollTop;
      if (t < 1) glide.raf = requestAnimationFrame(tick);
      else glide = null;
    };
    glide = { box, goal, wrote: start, raf: requestAnimationFrame(tick) };
  }

  return {
    commentOnItem,
    glideTo,
    placeThreadEdge,
    scrollerFor,
    seenScroller,
    stepPage,
    stepThread,
  };
}
