/* Keyboard reachability for scrollable page and shadow content. */

import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";
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
//
// And a box that scrolls holds what it scrolls, which a box does only as a containing
// block. An out-of-flow box is laid out against its containing block, and scrolling
// makes a box no such thing: a static scroller's absolutely positioned descendant is
// laid out against the page instead, where the scroller neither carries it as the
// reader scrolls nor clips it at its edge. The runtime hangs one in every block a
// comment lands on — the count a reader listening hears, clipped to a pixel
// (.lf-mark-note, and .lf-quiet beside it) — so one comment on the far column of a
// table wider than the window had the page itself scrolling sideways to reach a word
// nobody can see. So every static box this finds declaring a scroll is marked, and the
// theme positions the mark ([data-lf-holds]). Off the declaration and not the
// measurement below, on purpose: the stop is owed only while something is out of
// sight, while containment has to hold at whatever width the reader's window turns
// out to be. Read from the composed box rather than declared beside each overflow
// rule, so a page author's scroller and a package's are held on the same terms as the
// theme's own, and nobody is asked to declare anything for the sake of a word they did
// not write. Only a static box: relative is the one position that moves nothing, and a
// box positioned some other way already holds its own. The mark stays on a box that
// stops scrolling, which costs nothing, and the word is held from the first layout
// after the mark, whichever of the two lands first. Held when a sweep reaches the box,
// which is what the callers above owe this: a scroller a module builds outside its
// own settlement calls this on the subtree, as it would for the stop.
// What the platform puts in the tab order without being asked. Exported because the skip
// link needs the same reading of the banner: "the first thing in there a reader can
// stand on" and "does this box already hold a stop" are the one question.
export const FOCUSABLE =
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
// The same measurement spent on the eye. Scrolling is the layer's honest degrade for a
// box whose content is wider than the room it was given — a diagram at the size it was
// drawn, a board's columns, a line of code — and on a platform that draws overlay
// scrollbars the only sign of it is a bar the platform hides until it is used. Measured:
// a twelve-node flowchart in a tab panel showed seven, cut 356px of 1026 at every window
// width from 1200 to 1920, with nothing on the page saying so. A reader can guess that a
// line of code continues; nobody can guess a graph does.
//
// So the box says it is a window, and this is where it is said, because this is where the
// layer already knows: `paintReach` is asked whether something is out of sight on every
// layout that moves a candidate, and until now spent the answer on the keyboard alone.
// Off the composed box like the stop above, so a page author's scroller and a package's
// are marked on the same terms as the theme's own and nobody declares anything.
//
// Across the box and not down it, which is the axis every reading of a cut takes: a box
// cut off below its container is usually cut on purpose — a collapsed disclosure, a
// draft's box, a shot's frame are all a height with the rest hidden — where one cut at
// the side never is. The page itself is the down direction and the window's own bar
// answers for it.
//
// The mark is paint (theme.css, [data-lf-cut]), so writing it inside a resize observation
// moves nothing and cannot feed itself. Its candidate set is every declared sideways
// scroller and not `mayScroll`, which stops at boxes holding a control of their own: a
// board is reached through its grips and needs no stop, and is cut exactly as silently as
// anything else.
const sideways = new Set();
export const runtimeOwnsScrollerStop = (el) => mayScroll.has(el);
export function reachScrollers(root) {
  // The root too: a rebuilt widget is handed as itself, and the panel's thread list is
  // its own scroller.
  for (const scope of [root, ...shadowRootsIn(root)])
    for (const el of [
      ...(scope.nodeType === Node.ELEMENT_NODE ? [scope] : []),
      ...scope.querySelectorAll("*"),
    ]) {
      const style = getComputedStyle(el);
      if (
        !/^(auto|scroll)$/.test(style.overflowX) &&
        !/^(auto|scroll)$/.test(style.overflowY)
      )
        continue;
      // Not a textarea, which scrolls its own value and can hold nothing laid out inside
      // it: the mark would claim containment of a box that contains nothing, in every
      // page's rendered DOM and every exported copy. Written once, because the attribute
      // is observed (design.js) and this runs on every panel reconcile.
      if (
        style.position === "static" &&
        !el.matches("textarea") &&
        !el.hasAttribute(PAGE_PAINT_ATTRIBUTE.holds)
      )
        el.setAttribute(PAGE_PAINT_ATTRIBUTE.holds, "1");
      // A textarea is out of the cut mark for its own reason: it scrolls its value, which
      // the reader is writing and already knows continues.
      if (/^(auto|scroll)$/.test(style.overflowX) && !el.matches("textarea")) {
        sideways.add(el);
        reachSizes.observe(el);
      }
      // A box that already carries a stop of its own is somewhere the reader can be put,
      // whoever put it there; this sweep neither adds to it nor takes it away.
      if (el.tabIndex >= 0 && !mayScroll.has(el)) continue;
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
// Which of the candidates has something out of sight right now, asked once for both
// answers. Both directions for the stop, because a reader who widens the window is owed
// its removal as much as its arrival: a box that fits carries nothing to scroll to, and a
// tab stop on it is a press that goes nowhere. Cheap enough for chrome-layout.js — the
// sets are what declared they may scroll, which on the corpus is a couple of dozen boxes
// — and it writes `tabIndex` and one attribute the theme spends on a shadow, neither of
// which moves a box (the rule syncLayout keeps).
const reachSizes = new ResizeObserver(() => paintReach());
// A pixel of tolerance, where the stop takes any overflow at all: the stop is owed
// wherever the keyboard cannot reach something, and a shadow drawn for a sub-pixel
// rounding is a promise of more with nothing behind it.
const cutAcross = (el) => el.scrollWidth > el.clientWidth + 1;
function gone(el) {
  if (el.isConnected) return false;
  mayScroll.delete(el);
  sideways.delete(el);
  reachSizes.unobserve(el);
  return true;
}
function paintReach() {
  for (const el of mayScroll) {
    if (gone(el)) continue;
    const wanted = overflows(el) ? 0 : -1;
    if (el.tabIndex !== wanted) el.tabIndex = wanted;
  }
  for (const el of sideways) {
    if (gone(el)) continue;
    const cut = cutAcross(el);
    if (cut === el.hasAttribute(PAGE_PAINT_ATTRIBUTE.cut)) continue;
    if (cut) el.setAttribute(PAGE_PAINT_ATTRIBUTE.cut, "1");
    else el.removeAttribute(PAGE_PAINT_ATTRIBUTE.cut);
  }
}
