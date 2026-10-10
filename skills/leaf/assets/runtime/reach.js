/* Keyboard reachability, containment, the sticky-header slot, and continuation paint for
   scrollable page and shadow content. */

import { wearsLentStop } from "./focus.js";
import { LENT_REACH_STOP, TAB_STOP, TEXT_BOX } from "./control-selectors.js";
import { scrollsBy, skipped } from "./geometry.js";
import { afterScript, nextFrame, nextRender, sizeObserver } from "./rendering.js";
import { PAGE_PAINT_ATTRIBUTE } from "./page-paint.js";
import { shadowRootsIn, upFrom } from "./shadow.js";
import { LAYOUT } from "./widget-elements.js";
import { keeps } from "./keeps.js";

// Anything a mouse can scroll, a keyboard can reach. A `pre` too wide for the column
// scrolls, and a user working from the keyboard had no way at all to the half of the
// line off the right of it — which is a phone's every code block, since the column there
// is 372px and a line of code is not. Asked of the computed overflow rather than of a list
// of tags, so a widget that scrolls is covered by scrolling and the twelfth one needs no
// entry, and it reaches the runtime's own boxes on the same terms as the page's — and
// into the trees an x-shadow widget renders in, which the walk alone does not enter.
//
// A box holding a control is already reachable (lf-board, through its grips). Re-read
// that content when layout changes: an initially empty Page Map list must give up its
// container stop once actions arrive inside it.
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
// user scrolls nor clips it at its edge. A widget's word for a user listening is one,
// clipped to a pixel (.lf-quiet): standing past the far edge of a line of code wider
// than its box, it would have the page itself scrolling sideways to reach a word nobody
// can see. So every static box this finds declaring a scroll is marked, and the
// theme positions the mark ([data-lf-holds]). Off the declaration and not the
// measurement below, on purpose: the stop is owed only while something is out of
// sight, while containment has to hold at whatever width the user's window turns
// out to be. Read from the composed box rather than declared beside each overflow
// rule, so a page author's scroller and a package's are held on the same terms as the
// theme's own, and nobody is asked to declare anything for the sake of a word they did
// not write. Only a static box: relative is the one position that moves nothing, and a
// box positioned some other way already holds its own. The mark stays on a box that
// stops scrolling, which costs nothing, and the word is held from the first layout
// after the mark, whichever of the two lands first. Held when a sweep reaches the box,
// which is what the callers above owe this: a scroller a module builds outside its
// own settlement calls this on the subtree, as it would for the stop.
// The declaration picks the candidates and the measurement decides. A rule saying a box
// may scroll is not the same fact as a box with something out of sight: the theme sets
// `table { display: block; overflow-x: auto }` on every table there is, so the declaration
// alone gave all fourteen tables in the command reference a tab stop, none of which
// overflows — and leaving that reference by Tab went from one press to fifteen, each stop
// wearing the browser's own ring rather than the layer's.
//
// But overflow is a fact about the current layout. Measured at sweep time alone, a `pre`
// that fits a desk and scrolls on a phone got no stop at all, which is the very case the
// sweep was written for. So the two questions are asked at the times each can change:
// the measurement whenever the layout moves a candidate, and the declaration when a
// tree arrives, when a box in it is first rendered, and whenever what the computed
// style answers can move (`queries`, below). The candidate set is what the declaration
// leaves behind, so the re-measure walks a handful of boxes rather than the document.
//
// A box the user can scroll. `hidden` scrolls too, for a script, and is a sticky box's
// scroller (`scrollsBy`, geometry.js), but no stop or edge mark reaches what it hides.
const SCROLLS = /^(auto|scroll)$/;
// until-found retains its own box, unlike its skipped descendants. That hidden
// box cannot be inspected, so its apparent overflow earns no keyboard stop.
const overflows = (el) =>
  !el.hasAttribute("hidden") &&
  (el.scrollWidth > el.clientWidth || el.scrollHeight > el.clientHeight);
const holdsOwnStop = (el) => el.querySelector(TAB_STOP) !== null;
// Each candidate with the `tabindex` its author gave it, or null for none. The pass
// writes only the stop it lends, `0`, and takes back only that, to the author's value:
// a box that stops scrolling is the box it was before, not one a click can now focus.
// A box focus.js has lent a `-1` for an arrival goes back to that `-1`, which focus.js
// takes back on the blur.
const mayScroll = new Map();
// A control beside a scroller can require its stop even when its contents fit.
// Keep that request with the owner of the stop so a later layout pass cannot
// take it back as though it were a stop this pass had lent for overflow.
const claimedStops = new WeakSet();
// Keep the borrowed state with the lending owner. Consumers of authored working
// regions must never infer a region from this layout-dependent keyboard stop.
function lendStop(el) {
  keeps(el, LENT_REACH_STOP, "");
  keeps(el, "tabindex", 0);
}
export function claimReachStop(el) {
  if (claimedStops.has(el)) return;
  const authored = mayScroll.has(el) ? mayScroll.get(el) : el.getAttribute("tabindex");
  if (authored !== null) return;
  claimedStops.add(el);
  lendStop(el);
}

export function releaseReachStop(el) {
  if (!claimedStops.has(el)) return;
  claimedStops.delete(el);
  if (el.getAttribute("tabindex") !== "0") {
    keeps(el, LENT_REACH_STOP, null);
    return;
  }
  if (mayScroll.has(el) && overflows(el) && !holdsOwnStop(el)) lendStop(el);
  else returnStop(el, null);
}
// Takes back the stop this pass lent: to `-1` where focus.js has lent one for an
// arrival, which it takes back on the blur, and otherwise to the author's value.
function returnStop(el, authored) {
  keeps(el, LENT_REACH_STOP, null);
  if (el.getAttribute("tabindex") === "0")
    keeps(el, "tabindex", wearsLentStop(el) ? -1 : authored);
}
// The same measurement spent on the eye. Scrolling is the layer's honest degrade for a
// box whose content is wider than the room it was given — a diagram at the size it was
// drawn, a board's columns, a line of code — and on a platform that draws overlay
// scrollbars the only sign of it is a bar the platform hides until it is used. Measured:
// a twelve-node flowchart in a tab panel showed seven, cut 356px of 1026 at every window
// width from 1200 to 1920, with nothing on the page saying so. A user can guess that a
// line of code continues; nobody can guess a graph does.
//
// `paintReach` already asks whether each candidate has something out of sight whenever
// layout moves it. The scroll listener adds which side still has content beyond it. The
// marks sit on the composed box like the stop above, so authored, package, and theme
// scrollers follow the same rule without separate declarations.
//
// Across the box and not down it, which is the axis every reading of a cut takes: a box
// cut off below its container is usually cut on purpose — a collapsed disclosure, a
// draft's box, a shot's frame are all a height with the rest hidden — where one cut at
// the side never is. The page itself is the down direction and the window's own bar
// answers for it.
//
// The marks are paint (theme.css, [data-lf-more-before/after]). Writing them from a
// resize observation moves nothing and cannot feed itself. Its candidate set is every
// box whose computed `overflow-x` is `auto` or `scroll`, including boxes reached through
// their own controls: a board needs no container stop, and is cut exactly as silently
// as anything else. Computed, not declared, is
// wider than it sounds and is the set on purpose: `overflow-x: visible` computes to
// `auto` whenever `overflow-y` is not visible, so a box that only ever meant to scroll
// down — the panel's list, a drawer, the sidebar — is in here too. It earns the mark on the
// same terms as the rest, by actually holding more across than it shows; a box that
// scrolls only downwards never does, and the ones that do were cutting a word off with
// nothing to say so.
const sideways = new Set();
// A reading region is the narrower vertical case. Ordinary vertical overflow is often
// intentional and self-explanatory (a text box, disclosure, or the document itself),
// so `reachScrollers` must not infer this mark from overflow-y. Reading-region owners
// opt their bounded body in when they register it. The cue follows remaining content,
// because the pane's fixed lower edge would otherwise keep promising another part of
// the reading after the user reaches the end.
const downwards = new Set();
const readingScrolled = (event) => paintReadingReach(event.currentTarget);
const sidewaysScrolled = (event) => paintSidewaysReach(event.currentTarget);
export function reachReadingScroller(el) {
  downwards.add(el);
  watchReach(el);
  el.addEventListener("scroll", readingScrolled, { passive: true });
  paintReadingReach(el);
  // A host moved in one script lets go of its body and registers it again before the
  // script ends, so the cue leaves when the script does, and only a body nobody reached again
  // by then loses it.
  return () => {
    downwards.delete(el);
    if (!watched(el)) unwatchReach(el);
    el.removeEventListener("scroll", readingScrolled);
    afterScript(() => {
      if (!downwards.has(el)) el.removeAttribute(PAGE_PAINT_ATTRIBUTE.moreBelow);
    });
  };
}

function paintReadingReach(el) {
  // End-following owners finish their scroll after registering or resizing the
  // region. Paint its remaining-content cue from that final place in this turn.
  afterScript(() => {
    if (!downwards.has(el) || unpainted(el)) return;
    const style = getComputedStyle(el);
    const scrolling = SCROLLS.test(style.overflowY);
    el.toggleAttribute(
      PAGE_PAINT_ATTRIBUTE.moreBelow,
      scrolling && el.scrollTop + el.clientHeight < el.scrollHeight - 1,
    );
  });
}

// Every element in the scope is asked, except content the browser skips (`skipped`,
// which says why): asking about a box in a hidden tab's panel or a closed disclosure
// makes the browser style and lay out that whole subtree first, which on the corpus was
// nearly all of a revision's sweep. So the walk stops at the first skipped box on each
// path and leaves its subtree waiting, observed: a box in skipped content has no size,
// and the size observer hears it come to have one, which is the first moment its
// answers could matter to anyone. It is swept then. Every other element is asked,
// whoever's rule made it scroll — theme, package, runtime chrome, or the page's own
// stylesheet — so nobody declares a scroller, and a revision that swaps the page's CSS
// is read afresh by the sweep its install runs.
const waiting = new Set();

export function reachScrollers(root) {
  sweep(root);
  paintReach();
}

const wait = (el) => {
  waiting.add(el);
  reachSizes.observe(el);
};
function sweep(root) {
  if (root.nodeType === Node.ELEMENT_NODE && skipped(root)) return wait(root);
  // The x-shadow trees the walk enters, which it reaches through their hosts, so a
  // host in skipped content leaves its tree unasked too.
  const trees = new Set(shadowRootsIn(root));
  const walk = (scope) => {
    const walker = document.createTreeWalker(scope, NodeFilter.SHOW_ELEMENT, (el) => {
      if (!skipped(el)) return NodeFilter.FILTER_ACCEPT;
      wait(el);
      return NodeFilter.FILTER_REJECT;
    });
    // The root too: a rebuilt widget is handed as itself, and the panel's thread list
    // is its own scroller.
    let el = scope.nodeType === Node.ELEMENT_NODE ? scope : walker.nextNode();
    for (; el; el = walker.nextNode()) {
      // Swept from the size observer's own callback too, when a waiting box is drawn,
      // so its observation is dropped only once nothing is left to watch: dropping and
      // taking it again inside the callback is a fresh observation the same delivery
      // cannot reach, which the browser reports as a ResizeObserver loop.
      const waited = waiting.delete(el);
      classify(el);
      if (waited) release(el);
      if (trees.has(el.shadowRoot)) walk(el.shadowRoot);
    }
  };
  walk(root);
}

// And a box that scrolls is the scroller for whatever sticks inside it, so it starts the
// sticky-header slot `--lf-top` again at its own top (theme.css, at `--lf-top`). Without
// that, a diff's file header in it pinned the banner's height below the box's top.
// Marked here, from the composed box, for the same reason as the containment above: an
// author's scroller, made by a page rule, an inline style or a script, restarts on the
// same terms as a package's and the theme's own. Which boxes those are is geometry.js's
// answer (`scrollsBy`), the one its reading of what sticky headers cover takes, so an
// `overflow: hidden` box, which the user cannot scroll but a sticky box sticks in all the
// same, restarts too. The mark ([data-lf-scrolls], state.css) overrides a value a
// sticky header's holder stacks onto the box, since a header outside the box covers
// nothing the box scrolls, and restarts the slot at `--lf-top-start`, 0 unless the box
// states otherwise (a workspace pane's body starts at minus its top padding). The root,
// whose slot starts at the banner, is never swept. Two scrolling boxes keep the slot
// they met. A text box holds nothing. A sticking box reads the slot
// for its own `top`, so a restart there would stick the box itself at 0, behind the
// banner; a sticking box that scrolls headers restarts the slot for them itself (a
// column's sidebar, layouts.css). Read with the declaration, so a box that stops
// scrolling at another width stops restarting the slot, or its headers would pin behind
// the banner.
function paintSlot(el, style) {
  el.toggleAttribute(
    PAGE_PAINT_ATTRIBUTE.scrolls,
    scrollsBy(style) && style.position !== "sticky" && !el.matches(TEXT_BOX),
  );
}

function classify(el) {
  asked.add(el);
  const style = getComputedStyle(el);
  noteQueries(el, style);
  paintSlot(el, style);
  // The rest is for a box the user can scroll. One that no longer is gives back the
  // stop this pass lent it.
  if (
    el.hasAttribute("hidden") ||
    (!SCROLLS.test(style.overflowX) && !SCROLLS.test(style.overflowY))
  ) {
    if (!mayScroll.has(el)) return;
    const authored = mayScroll.get(el);
    mayScroll.delete(el);
    if (!claimedStops.has(el)) returnStop(el, authored);
    if (!watched(el)) unwatchReach(el);
    return;
  }
  // Not a text box, which scrolls its own value and can hold nothing laid out inside
  // it: the mark would claim containment of a box that contains nothing. Written once,
  // because the attribute is observed (design.js) and this runs on every panel
  // reconcile.
  if (
    style.position === "static" &&
    !el.matches(TEXT_BOX) &&
    !el.hasAttribute(PAGE_PAINT_ATTRIBUTE.holds)
  )
    el.setAttribute(PAGE_PAINT_ATTRIBUTE.holds, "1");
  // A text box is out of the continuation marks for its own reason: it scrolls a
  // value its user is writing and already knows continues.
  if (SCROLLS.test(style.overflowX) && !el.matches(TEXT_BOX) && !sideways.has(el)) {
    sideways.add(el);
    watchReach(el);
    el.addEventListener("scroll", sidewaysScrolled, { passive: true });
  }
  // A box that already carries a stop of its own is somewhere the user can be put,
  // whoever put it there; this pass neither adds to it nor takes it away.
  if (!mayScroll.has(el)) {
    if (el.tabIndex >= 0 && !claimedStops.has(el)) return;
    mayScroll.set(
      el,
      wearsLentStop(el) || claimedStops.has(el) ? null : el.getAttribute("tabindex"),
    );
  }
  // The box itself, not the page's: a candidate's own resize is exactly the moment
  // its answer can change, and asking it there is one observation per candidate
  // rather than a sweep per layout pass. Watching body instead read the old width —
  // the observation arrives after the frame that resized, and axe was already
  // looking.
  watchReach(el);
}
// What a box holds moves its overflow as much as its own size does, and can move
// without it: text rewrapping at a new width inside a pane of fixed height, frames a
// widget sizes a pass after its host. So a candidate's children are watched beside it,
// whichever children it holds: one a widget swaps in is watched from its arrival, which
// is itself a change to what the box holds, and one it takes out is let go.
const childrenWatched = new WeakSet();
const childLists = new MutationObserver((records) => {
  for (const { target, addedNodes, removedNodes } of records) {
    if (!childrenWatched.has(target)) continue;
    for (const node of removedNodes)
      if (node.nodeType === Node.ELEMENT_NODE) release(node);
    for (const node of addedNodes)
      if (node.nodeType === Node.ELEMENT_NODE) reachSizes.observe(node);
  }
});
function watchReach(el) {
  reachSizes.observe(el);
  if (childrenWatched.has(el)) return;
  childrenWatched.add(el);
  for (const child of el.children) reachSizes.observe(child);
  childLists.observe(el, { childList: true });
}
// A MutationObserver lets go of no single target, so a box no longer watched is only
// left out of what its deliveries do.
function unwatchReach(el) {
  const heldChildren = childrenWatched.delete(el);
  release(el);
  if (heldChildren) for (const child of el.children) release(child);
}
// One observation serves every reason to watch a box: a candidate in its own right,
// and the child of one. It ends only when neither holds, so a nested scroller moved
// out of its parent keeps the watch it has as a candidate.
function release(node) {
  if (!watched(node) && !childrenWatched.has(node.parentElement))
    reachSizes.unobserve(node);
}
const depth = (el) => {
  let levels = 0;
  for (let node = el; node; node = upFrom(node)) levels++;
  return levels;
};
const watched = (el) =>
  mayScroll.has(el) || sideways.has(el) || downwards.has(el) || waiting.has(el);
// Re-read each candidate after layout moves it. A user who widens the window is owed
// the stop's removal as much as its arrival: a box that fits carries nothing to scroll
// to, and a tab stop on it is a press that goes nowhere. The candidate sets keep the
// pass to the boxes that scroll, about a hundred of the corpus's ten thousand elements.
// `tabIndex` and the paint attributes move no box, which keeps the pass safe inside
// syncLayout.
const reachSizes = sizeObserver(() => paintReach());
// A pixel of tolerance, where the stop takes any overflow at all: the stop is owed
// wherever the keyboard cannot reach something, and a fade drawn for sub-pixel rounding
// is a promise of more with nothing behind it. scrollLeft follows the inline direction:
// it starts at zero and becomes negative in a right-to-left scroller.
function paintSidewaysReach(el) {
  if (!sideways.has(el) || unpainted(el)) return;
  const style = getComputedStyle(el);
  const scrolling =
    SCROLLS.test(style.overflowX) && el.scrollWidth > el.clientWidth + 1;
  const maximum = Math.max(0, el.scrollWidth - el.clientWidth);
  const raw = Math.abs(el.scrollLeft);
  const position = Math.min(maximum, Math.max(0, raw));
  keeps(el, PAGE_PAINT_ATTRIBUTE.scrollDirection, scrolling ? style.direction : null);
  el.toggleAttribute(PAGE_PAINT_ATTRIBUTE.moreBefore, scrolling && position > 1);
  el.toggleAttribute(
    PAGE_PAINT_ATTRIBUTE.moreAfter,
    scrolling && position < maximum - 1,
  );
}
function gone(el) {
  if (el.isConnected) return false;
  mayScroll.delete(el);
  if (sideways.delete(el)) el.removeEventListener("scroll", sidewaysScrolled);
  downwards.delete(el);
  waiting.delete(el);
  if (queried.delete(el)) queries.unobserve(el);
  unwatchReach(el);
  return true;
}
// A box that stands in skipped content keeps what it last wore until it is drawn: measuring
// it would force that content's style, and a box on no screen is no stop and shows no
// edge. The reading and sideways edge paints ask it themselves, since a reading region
// is painted as it registers, and a block can register in a hidden panel (bounds.js).
const unpainted = (el) => gone(el) || skipped(el);
function paintReach() {
  for (const el of waiting) if (!unpainted(el)) sweep(el);
  // A box holding a scroller that takes a stop holds a stop, so an outer box's answer
  // waits on its inner boxes': the deepest are asked first, and each box is written once.
  const levels = new Map([...mayScroll.keys()].map((el) => [el, depth(el)]));
  for (const [el, authored] of [...mayScroll].sort(
    ([a], [b]) => levels.get(b) - levels.get(a),
  )) {
    if (unpainted(el)) continue;
    if (claimedStops.has(el)) continue;
    if (overflows(el) && !holdsOwnStop(el)) lendStop(el);
    else returnStop(el, authored);
  }
  for (const el of sideways) paintSidewaysReach(el);
  for (const el of downwards) paintReadingReach(el);
}

// Which boxes scroll is read from the computed style, and the computed style moves with
// layout as well as with markup: a media query answers the window, and a container
// query its container's size. So a box can start scrolling long after it arrived, as a
// side list's column of tabs turns into a row at a phone's width, or a box in a pane
// dragged narrow does, and a box can stop. The declaration is read again where those
// inputs move: the whole page when the window resizes, a container's subtree when the
// size its queries read changes, and a subtree a module announces it rearranged
// (LAYOUT, below), which is how a class a page's script adds, or an attribute the
// runtime writes for a Layout (content-layout.js), reaches here. A style that moves
// with none of them, such as a rule on `:checked`, is read at the next one, since the
// browser announces nothing when it applies.
//
// A re-read waits until what asked for it has held still, then sweeps the outermost of
// the boxes due, once. A window dragged wider resizes the page every frame, a sweep
// reads the style of every box under it, ten thousand on the corpus, and what it
// decides matters once the window stops. Waiting also keeps the sweep out of a size
// delivery, where a box first observed at the depth that delivery reached is one the
// browser reports as a ResizeObserver loop. Each box waits on its own asking, so a box
// that keeps moving holds back only what is under it.
//
// A re-read is work toward a resting state, so the frames it waits through are counted
// (rendering.js) and the page reads as settled only after the sweep: a box is due once
// a frame passes without it being asked for again. A container that keeps moving for
// longer than `PLAYING_MS` is the exception: whatever moves it, its own animation, a
// sibling's or a script's, the page is playing rather than coming to rest, as a meter
// pulsing for as long as work runs does. Its asks stop holding the page, and its box is
// due once it has held still for `STILL_MS`, which a timer waits for. Its watch is
// uncounted (`queries`, below) for the same reason. A transition, a drag or any motion
// that ends within `PLAYING_MS` stays counted, so the page settles after its sweep; one
// that runs longer settles up to `STILL_MS` before it. Questions from the window or a module
// stay apart from a container's own, so announcing a playing container still settles.
const STILL_MS = 100;
const PLAYING_MS = 1000;
const rereads = new Map();
let lastTick = -Infinity;
let tickFrame = 0;
let tickTimer = 0;
function reread(root, byContainer) {
  const now = performance.now();
  const asked = rereads.get(root) ?? { at: null, moved: null, movingSince: null };
  if (!byContainer) asked.at = now;
  else {
    if (asked.moved === null || now - asked.moved >= STILL_MS) asked.movingSince = now;
    asked.moved = now;
  }
  rereads.set(root, asked);
  waitToReread();
}
const playing = (asked) => asked.moved - asked.movingSince > PLAYING_MS;
const counts = (asked) =>
  asked.at !== null || (asked.moved !== null && !playing(asked));
function waitToReread() {
  const pending = [...rereads.values()];
  if (pending.some(counts)) tickFrame ||= nextFrame(rereadFrame);
  else if (pending.length) tickTimer ||= setTimeout(rereadTimer, STILL_MS);
}
function rereadFrame() {
  tickFrame = 0;
  const since = lastTick;
  lastTick = performance.now();
  rereadDue(lastTick, since);
}
function rereadTimer() {
  tickTimer = 0;
  rereadDue(performance.now(), -Infinity);
}
// What was asked for before `since`, the previous counted frame, has held still a
// frame; a playing container has held still once `STILL_MS` has passed.
function rereadDue(now, since) {
  const roots = [];
  for (const [root, asked] of rereads) {
    let due = false;
    if (asked.at !== null && asked.at < since) {
      asked.at = null;
      due = true;
    }
    const still = playing(asked) ? now - asked.moved >= STILL_MS : asked.moved < since;
    if (asked.moved !== null && still) {
      asked.moved = null;
      due = true;
    }
    if (due) roots.push(root);
    if (asked.at === null && asked.moved === null) rereads.delete(root);
  }
  const outermost = roots.filter((el) => {
    for (let node = upFrom(el); node; node = upFrom(node))
      if (roots.includes(node)) return false;
    return !unpainted(el);
  });
  for (const root of outermost) sweep(root);
  if (outermost.length) paintReach();
  waitToReread();
}

// Each container is held with the size its queries last read, an inline size or both,
// taken from its first observation. It is observed from the next frame, not as the
// sweep finds it, since a sweep of a waiting box runs inside a size delivery (above).
const queried = new Map();
const unobserved = new Set();
function noteQueries(el, { containerType }) {
  const kinds = containerType.split(" ");
  const both = kinds.includes("size");
  if (!both && !kinds.includes("inline-size")) {
    if (queried.delete(el)) queries.unobserve(el);
    return;
  }
  if (queried.get(el)?.both === both) return;
  queried.set(el, { both, size: null });
  if (!unobserved.size) nextRender(observeQueried);
  unobserved.add(el);
}
function observeQueried() {
  for (const el of unobserved) if (queried.has(el)) queries.observe(el);
  unobserved.clear();
}
const queries = sizeObserver(
  (entries) => {
    for (const { target, contentBoxSize } of entries) {
      const query = queried.get(target);
      if (!query || gone(target)) continue;
      const [{ inlineSize, blockSize }] = contentBoxSize;
      const size = query.both ? `${inlineSize} ${blockSize}` : `${inlineSize}`;
      if (query.size !== null && query.size !== size) reread(target, true);
      query.size = size;
    }
  },
  { counted: false },
);
addEventListener("resize", () => reread(document.body));
// A widget can rearrange descendants without changing its outer box. ResizeObserver
// cannot hear that case; the layer's shared geometry signal can. One repaint updates
// every candidate and registered reading region after the new layout is stated, and
// what was rearranged is read again, since a box in it may scroll now. A box no sweep
// has reached yet, itself or through what holds it, is left to the sweep the page's
// install runs, which a widget rearranging itself as it upgrades would otherwise run
// early.
const asked = new WeakSet();
const reached = (el) => {
  for (let node = el; node; node = upFrom(node)) if (asked.has(node)) return true;
  return false;
};
document.addEventListener(LAYOUT, (event) => {
  const [changed] = event.composedPath();
  if (changed?.nodeType === Node.ELEMENT_NODE && reached(changed)) reread(changed);
  paintReach();
});
