/* Keyboard reachability for scrollable page and shadow content. */

import { shadowRootsIn } from "./shadow.js";

// Anything a mouse can scroll, a keyboard can reach. A `pre` too wide for the column
// scrolls, and a user working from the keyboard had no way at all to the half of the
// line off the right of it — which is a phone's every code block, since the column there
// is 372px and a line of code is not. Asked of the computed overflow rather than of a list
// of tags, so a widget that scrolls is covered by scrolling and the twelfth one needs no
// entry, and it reaches the runtime's own boxes on the same terms as the page's — and
// into the trees an x-shadow widget renders in, which the walk alone does not enter.
//
// Asked of the content first, because a box holding a control of its own is already
// reachable (lf-board, through its grips) and a tab stop over the whole board would
// stand between the user and the card they were tabbing to.
//
// Two things every caller owes it, both learned by getting them wrong. It runs after a
// widget has rendered rather than as one stages, because the look a scroll box has is
// the theme's `:host(.lf-rendered)` rule and a widget adds that class once its render
// returns — so a sweep at `shadowStage` time reads a box the stylesheet has not reached
// and tags nothing. And it runs on a tree that is in the document, because
// `getComputedStyle` answers "" for every property of a detached element, which is the
// silent version of the same failure: a sweep that walks everything and tags nothing.
const FOCUSABLE =
  'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])';
// The declaration picks the candidates and the measurement decides. A rule saying a box
// may scroll is not the same fact as a box with something out of sight: the theme sets
// `table { display: block; overflow-x: auto }` on every table there is, so the declaration
// alone gave all fourteen tables in the keyboard reference a tab stop, none of which
// overflows — and leaving that reference by Tab went from one press to fifteen, each stop
// wearing the browser's own ring rather than the layer's.
//
// But overflow is a fact about the current layout, and the sweep runs once. Measured at
// sweep time alone, a `pre` that fits a desk and scrolls on a phone got no stop at all,
// which is the very case the sweep was written for. So the two questions are asked at the
// two times each is answerable: the declaration once, when a tree arrives, and the
// measurement again whenever the layout moves. The candidate set is what the declaration
// leaves behind, so the re-measure walks a handful of boxes rather than the document.
const overflows = (el) =>
  el.scrollWidth > el.clientWidth || el.scrollHeight > el.clientHeight;
const mayScroll = new Set();
export function reachScrollers(root) {
  for (const scope of [root, ...shadowRootsIn(root)])
    for (const el of scope.querySelectorAll("*")) {
      // A box that already carries a stop of its own is somewhere the reader can be put,
      // whoever put it there; this sweep neither adds to it nor takes it away.
      if (el.tabIndex >= 0 && !mayScroll.has(el)) continue;
      const style = getComputedStyle(el);
      if (
        !/^(auto|scroll)$/.test(style.overflowX) &&
        !/^(auto|scroll)$/.test(style.overflowY)
      )
        continue;
      if (el.querySelector(FOCUSABLE)) continue;
      mayScroll.add(el);
      // The box itself, not the page's: a candidate's own resize is exactly the moment
      // its answer can change, and asking it there is one observation per candidate
      // rather than a sweep per layout pass. Watching body instead read the old width —
      // the observation arrives after the frame that resized, and axe was already
      // looking.
      reachSizes.observe(el);
    }
  paintReach();
}
// Which of the candidates has something out of sight right now. Both directions, because
// a reader who widens the window is owed the stop's removal as much as its arrival: a box
// that fits carries nothing to scroll to, and a tab stop on it is a press that goes
// nowhere. Cheap enough for the layout writer — the set is what declared it may scroll,
// which on the corpus is single digits — and it writes only `tabIndex`, which moves no box
// (the rule syncLayout keeps).
const reachSizes = new ResizeObserver(() => paintReach());
function paintReach() {
  for (const el of mayScroll) {
    if (!el.isConnected) {
      mayScroll.delete(el);
      reachSizes.unobserve(el);
      continue;
    }
    const wanted = overflows(el) ? 0 : -1;
    if (el.tabIndex !== wanted) el.tabIndex = wanted;
  }
}
