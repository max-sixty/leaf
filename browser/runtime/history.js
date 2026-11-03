/* The entries this document adds to session history, and the traversals among them.
 *
 * Every same-document entry is a place the user can come Back to. `pushEntry` adds one,
 * leaving the entry the user was on with the scroll offset the browser saves on it;
 * `replaceEntry` renames the entry the user is on and keeps its state. A new entry
 * starts with no state of its own, since state belongs to the entry that set it.
 * Travel prepares its outgoing checkpoint before revealing a destination and commits
 * it only after arrival succeeds. Failed or canceled routes add no return stop.
 *
 * A working-place checkpoint owns the viewport offset, focus and selection together.
 * Chrome's native restoration can lose the saved offset when Back interrupts a smooth
 * arrival; its pending compositor update can also overwrite an immediate restoration.
 * A traversal cancels the outgoing placement, waits for that cancellation's rendering
 * update, then places the page. The browser applies the traversal some time after its
 * navigate event, and Firefox and WebKit change the page as they do, even though the
 * traversal is intercepted with `scroll: "manual"`. Both reveal the element the
 * entry's fragment names, WebKit then scrolls to it, and Firefox restores the
 * destination's saved offset (Firefox 157 and WebKit 27.2; Firefox's nsDocShell never
 * reads the suppression the Navigation API sets). That overwrote the placement: Back
 * to a since-hidden `#tabbed` left it 471px down in Firefox, where Chromium landed it
 * at 59px. So once the browser has applied the traversal (`traversalApplied`), the
 * page scrolls back by however far the first block on screen moved since the
 * placement. Scroll anchoring holds that block still through a change above it, but a
 * change inside it in that frame moves it as the browser does, and a pinned block
 * stays put while the browser scrolls. The claimant and travel read the page before
 * the browser applies the traversal, while it still hides what the user hid since.
 * Rejected: placing only after the browser applies the traversal, which let Firefox
 * and WebKit reveal a root view's target before travel read the page, and let a quick
 * second Back save the entry between before it was placed; putting back the
 * placement's own offset, which undid scroll anchoring; and
 * `history.scrollRestoration = "manual"`, under which Firefox put a traversal Leaf had
 * no checkpoint for at the top of the page.
 * Nested reading regions stop with that placement but keep their current offsets;
 * these checkpoints restore the document viewport.
 *
 * Without a captured checkpoint, the browser restores its saved offset, except that
 * Chrome answers a traversal to an entry whose fragment names an element by scrolling to that element
 * instead (measured: Back to `#s2` after reading 3000px down landed on `#s2` at 666).
 * So every same-document traversal comes through here, through the Navigation API. An
 * owner that claims the destination (`claimTraversals`) can reveal and place the page
 * itself, as a root tab set does for the entry of each of its views. Travel takes the
 * traversal after any claimant (`mountHistory`'s `returnToFragment`, anchor-travel.js)
 * where the entry's fragment still names a place the page doesn't show, such as a
 * widget's key whose part the widget no longer draws inside the view a tab set has
 * just opened: the offset was saved over a page that has changed, so travel reveals
 * the place and lands on it. Any other traversal is
 * intercepted to restore its working-place checkpoint, or the browser's saved offset
 * for an entry without one. Back and Forward restore that working place after its
 * owner has revealed the view, so the next command reads the returned place from the browser.
 * These are return checkpoints, never a reading of the user's current position; a
 * newer gesture cancels a delayed return, and a node removed since is not restored.
 * Checkpoints hold nodes weakly: history owns the return, not the old markup.
 *
 * A fragment navigation, a followed `#id` link, is not a traversal: it adds its entry
 * and is a navigation step to the element it names. Travel claims it (`followFragment`) where the
 * fragment names an element of the page, and lands it through the browser's own
 * fragment placement rule once travel has cleared and revealed the way; any other fragment
 * keeps native landing. An entry this document writes through `pushEntry` or
 * `replaceEntry`, as travel and a tab set do, is not a fragment navigation and is never
 * claimed. A browser without the Navigation API keeps its own traversals and fragment
 * landings. */

import { pageRange, selectEnds, selectionBackward } from "./native-selection.js";
import { setScroll } from "./arrivals.js";
import { deepFocus, drawn, focusDestination, readCaret, blurFocused } from "./focus.js";

import { retainUserIntent } from "./user-intent.js";
import { placeOf } from "./current-target.js";
import { upFrom } from "./shadow.js";
import { presented } from "./geometry.js";
import { unconcealedReadingRegions } from "./reading-regions.js";
import { readingBlock } from "./reading-place.js";
import { pageScroller, stopScroll } from "./scrolling.js";
import { nextRender } from "./rendering.js";

/** @typedef {[WeakRef<Node>, number]} HeldSelectionEnd
 * @typedef {{focus: WeakRef<Element> | null, place: WeakRef<Element> | null,
 * caret: import("./focus.js").Caret | null, ends: [HeldSelectionEnd, HeldSelectionEnd] | null,
 * offset: [number, number]}} WorkingPlace
 * @typedef {() => void | boolean | Promise<void | boolean>} TraversalHandler
 * @typedef {(url: URL) => TraversalHandler | null | undefined} TraversalClaim
 */
/** @type {Set<TraversalClaim>} */
const claims = new Set();
/** @type {Map<string, WorkingPlace>} */
const places = new Map();

// The user's working place, read once before something borrows it: leaving an entry, or
// stepping into the floating panel, whose place-keeping commands hand it back. `focus` is
// the node they had focused, when the reading comes after focus has left it. Plain endpoints
// keep a removed passage from being silently retargeted by a live Range. pageRange
// shares the declared-shadow reading used for commenting; the selection's direction also
// keeps its working end.
/** @param {Element | null} focus @returns {WorkingPlace} */
export function readPlace(focus = deepFocus()) {
  const place = placeOf(focus);
  const selection = getSelection();
  const range = selection?.rangeCount ? pageRange(selection) : null;
  /** @type {[HeldSelectionEnd, HeldSelectionEnd] | null} */
  const ends = range && [
    [new WeakRef(range.startContainer), range.startOffset],
    [new WeakRef(range.endContainer), range.endOffset],
  ];
  if (ends && selection && range && selectionBackward(selection, range)) ends.reverse();
  return {
    focus: focus && new WeakRef(focus),
    place: place && new WeakRef(place),
    caret: readCaret(focus),
    ends,
    offset: [scrollX, scrollY],
  };
}

// Put the user back in a place `readPlace` read. A live revision may have removed or
// shortened what it named since, so a node no longer drawn is not returned to, and a
// selection end past its node's current length returns to what is left of that node,
// its end.
/** @param {WorkingPlace} checkpoint */
export function returnPlace(checkpoint) {
  const focus = checkpoint.focus?.deref();
  const place = checkpoint.place?.deref();
  const { caret } = checkpoint;
  if (focus !== document.body && focus?.isConnected && presented(focus)) {
    focusDestination(focus, "return", { caret });
    // A field's caret is its whole selection, and clearing the document's would
    // collapse it.
    if (caret) return;
  }
  // A thread card may have closed on departure, still painted but inert during
  // its closing fade. Its page target is the same working place from the other
  // side, and remains a browser focus destination on return.
  else if (place?.isConnected && presented(place)) focusDestination(place, "return");
  else blurFocused();
  const selection = getSelection();
  if (!selection) return;
  selection.removeAllRanges();
  // Editing the passage can remove its saved endpoint. That checkpoint then has no
  // selection to restore, and the returned viewport supplies the next walk's origin.
  const anchor = checkpoint.ends && returnEnd(checkpoint.ends[0]);
  const end = checkpoint.ends && returnEnd(checkpoint.ends[1]);
  if (anchor && end) selectEnds(anchor, end);
}

/** @param {HeldSelectionEnd} end @returns {import("./native-selection.js").SelectionEnd | null} */
function returnEnd([ref, offset]) {
  const node = ref.deref();
  if (!node || !drawn(node instanceof Element ? node : upFrom(node))) return null;
  const length = node instanceof CharacterData ? node.length : node.childNodes.length;
  return [node, Math.min(offset, length)];
}

// Whether this document is writing an entry itself. The Navigation API fires `navigate`
// synchronously inside `pushState` and `replaceState`, and those events look like a
// press on a link to the fragment the page already shows: both are a same-document
// `replace` or `push` with no hash change. Only the writer can tell them apart.
let writing = false;
/** @param {"pushState" | "replaceState"} method @param {unknown} state
 * @param {string | URL | null | undefined} url */
function write(method, state, url) {
  writing = true;
  try {
    history[method](state, "", url);
  } finally {
    writing = false;
  }
}

/** @param {string | URL | null | undefined} url @param {unknown} state */
export function pushEntry(url, state = null) {
  write("pushState", state, url);
}

/** @param {string | URL | null | undefined} url @param {unknown} state */
export function replaceEntry(url, state = history.state) {
  write("replaceState", state, url);
}

// A route can reveal or hydrate before it knows whether arrival will succeed. Capture
// its outgoing checkpoint now, but write only on success. A synchronous round trip to
// the source offset lets native history save that offset too, without an intermediate
// paint, including in browsers without the Navigation API. The Navigation listener's
// live focus reading is replaced with the original working place after the write.
export function prepareEntry() {
  const key = window.navigation?.currentEntry?.key;
  const place = readPlace();
  const offset = place.offset;
  const sourceUrl = window.location.href;
  const sourceState = history.state;
  return /** @param {string | URL} url */ (url) => {
    const arrival = { left: scrollX, top: scrollY };
    // Exposing another view renames this entry. Its original URL and state belong to
    // the outgoing checkpoint; the exposed destination belongs to the new entry.
    if (window.location.href !== sourceUrl || history.state !== sourceState)
      replaceEntry(sourceUrl, sourceState);
    setScroll(pageScroller, { left: offset[0], top: offset[1], behavior: "instant" });
    pushEntry(url);
    setScroll(pageScroller, { ...arrival, behavior: "instant" });
    if (key) places.set(key, place);
  };
}

// `claim(url)` returns the handler that reveals the destination of a traversal, or
// nothing when the entry is not the claimant's. The first claim to answer takes it.
// A handler places the viewport itself unless it resolves to false, handing placement
// back to the entry's checkpoint (or the browser when no checkpoint was captured).
// Travel follows it where the entry's fragment names a place its view doesn't show.
/** @param {TraversalClaim} claim @param {{signal?: AbortSignal}} [options] */
export function claimTraversals(claim, { signal } = {}) {
  claims.add(claim);
  signal?.addEventListener("abort", () => claims.delete(claim), { once: true });
}

let mounted = false;
/** @param {{followFragment: TraversalClaim, returnToFragment: TraversalClaim}} options */
export function mountHistory({ followFragment, returnToFragment }) {
  if (mounted) return;
  mounted = true;
  const navigation = window.navigation;
  navigation?.addEventListener("navigate", (event) => {
    if (!event.destination.sameDocument || !event.canIntercept) return;
    const url = new URL(event.destination.url);
    if (event.navigationType !== "replace") {
      const live = new Set(navigation.entries().map((entry) => entry.key));
      for (const key of places.keys()) if (!live.has(key)) places.delete(key);
      const key = navigation.currentEntry?.key;
      if (key) places.set(key, readPlace());
    }
    if (event.navigationType === "traverse") {
      const claim = claimed(url);
      const place = places.get(event.destination.key);
      const mayReturn = retainUserIntent({ available: () => !event.signal.aborted });
      const applied = traversalApplied(event.signal);
      event.intercept({
        scroll: "manual",
        focusReset: "manual",
        handler: async () => {
          if (!mayReturn()) return;
          // Cancel the outgoing placement, including its nested reading regions.
          // Its compositor update can outlive this task, so restore only after a
          // complete rendering update has carried the cancellation to the browser.
          const scrollers = new Set([
            pageScroller,
            ...unconcealedReadingRegions().map((region) => region.body),
          ]);
          await stopScroll(scrollers);
          if (!mayReturn()) return;
          // The claimant reveals its view first, so travel reads the place the fragment
          // names in the page that view leaves. Either one places the viewport unless it
          // resolves to false.
          /** @type {unknown} */
          let work;
          mayReturn.handoff(() => {
            work = claim?.();
          });
          let placed = Boolean(claim) && (await work) !== false;
          if (!mayReturn()) return;
          work = undefined;
          mayReturn.handoff(() => {
            work = returnToFragment(url)?.();
          });
          if (work !== undefined) placed = (await work) !== false || placed;
          if (!mayReturn()) return;
          if (!placed && !place) {
            event.scroll();
            return;
          }
          if (!placed && place)
            setScroll(pageScroller, {
              left: place.offset[0],
              top: place.offset[1],
              behavior: "instant",
            });
          if (place) mayReturn.handoff(() => returnPlace(place));
          // Firefox and WebKit may apply the traversal after this placement and move
          // the page as they do (above). Once they have, the first block on screen goes
          // back to where the placement stood it.
          const mark = readingBlock() ?? document.documentElement;
          const stood = mark.getBoundingClientRect().top;
          await applied;
          if (!mayReturn() || !mark.isConnected) return;
          const moved = mark.getBoundingClientRect().top - stood;
          if (moved)
            mayReturn.handoff(() =>
              setScroll(pageScroller, {
                top: pageScroller.scrollTop + moved,
                behavior: "instant",
              }),
            );
        },
      });
      return;
    }
    // A followed link again to the fragment already shown is a `replace` with no hash
    // change, and still a navigation step: its target may have been shut since.
    if (writing || event.formData || !url.hash) return;
    const handler = followFragment(url);
    if (handler)
      event.intercept({
        scroll: "manual",
        focusReset: "manual",
        handler: async () => {
          await handler();
        },
      });
  });
}

// Resolves in the first rendering update after the traversal's `popstate`, which every
// engine fires as it applies a same-document traversal, or when the traversal is
// aborted. Firefox restores the entry's saved offset just after that `popstate`, in
// the same task, so the rendering update is the first point past it that comes
// before the next paint.
/** @param {AbortSignal} signal @returns {Promise<void>} */
function traversalApplied(signal) {
  return new Promise((resolve) => {
    addEventListener("popstate", () => nextRender(() => resolve()), {
      once: true,
      signal,
    });
    signal.addEventListener("abort", () => resolve(), { once: true });
  });
}

/** @param {URL} url */
function claimed(url) {
  for (const claim of claims) {
    const handler = claim(url);
    if (handler) return handler;
  }
  return null;
}
