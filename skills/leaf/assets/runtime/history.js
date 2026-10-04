/* The entries this document adds to session history, and the traversals among them.
 *
 * Every same-document entry is a place the user can come Back to. `pushEntry` adds one,
 * leaving the entry the user stood on with the scroll offset the browser saves on it;
 * `replaceEntry` renames the entry the user stands on and keeps its state. A new entry
 * starts with no state of its own, since state belongs to the entry that set it.
 * Travel prepares its outgoing checkpoint before revealing a destination and commits
 * it only after arrival succeeds. Failed or canceled routes add no return stop.
 *
 * The browser restores a saved offset on traversal, except that Chrome answers a
 * traversal to an entry whose fragment names an element by scrolling to that element
 * instead (measured: Back to `#s2` after reading 3000px down landed on `#s2` at 666).
 * So every same-document traversal comes through here, through the Navigation API. An
 * owner that claims the destination (`claimTraversals`) places the page itself, as a
 * root tab set does for the entry of each of its views. Travel takes the traversal next
 * (`mountHistory`'s `returnToFragment`, anchor-travel.js) where the entry's fragment
 * names a place the page no longer shows: the offset was saved over a page that has
 * changed, so travel reveals the place and lands on it. Any other traversal is
 * intercepted only so the browser restores the entry's saved offset, which it does for
 * an intercepted traversal. Each entry also holds the browser focus and selection it
 * was left with. Back and Forward restore that working place after its owner has
 * revealed the view, so the next command reads the returned place from the browser.
 * These are return checkpoints, never a reading of the user's current position; a
 * newer gesture cancels a delayed return, and a node removed since is not restored.
 *
 * A fragment navigation, a followed `#id` link, is not a traversal: it adds its entry
 * and is a trip to the element it names. Travel claims it (`followFragment`) where the
 * fragment names an element of the page, and lands it through the browser's own
 * fragment placement rule once travel has cleared and revealed the way; any other fragment
 * keeps native landing. An entry this document writes through `pushEntry` or
 * `replaceEntry`, as travel and a tab set do, is not a fragment navigation and is never
 * claimed. A browser without the Navigation API keeps its own traversals and fragment
 * landings. */

import { deepFocus, focusDestination, readCaret } from "./focus.js";
import { pageRange, selectEnds, selectionBackward } from "./passages.js";
import { retainUserIntent } from "./user-intent.js";
import { placeOf } from "./standing-target.js";
import { upFrom } from "./shadow.js";

const claims = new Set();
const places = new Map();

// Read once when leaving an entry. Plain endpoints keep a removed passage from being
// silently retargeted by a live Range. pageRange shares the declared-shadow reading
// used for commenting; the selection's direction also keeps its working end.
function readPlace() {
  const focus = deepFocus();
  const selection = getSelection();
  const range = selection.rangeCount ? pageRange(selection) : null;
  const ends = range && [
    [range.startContainer, range.startOffset],
    [range.endContainer, range.endOffset],
  ];
  if (ends && selectionBackward(selection, range)) ends.reverse();
  return { focus, place: placeOf(focus), caret: readCaret(focus), ends };
}

const drawn = (node) =>
  node?.isConnected && node.checkVisibility({ visibilityProperty: true });

function returnPlace({ focus, place, caret, ends }) {
  if (focus !== document.body && drawn(focus)) focusDestination(focus, caret);
  // A thread card may have closed on departure. Its page target is the same working
  // place from the other side, and remains a browser focus destination on return.
  else if (drawn(place)) focusDestination(place);
  else deepFocus()?.blur();
  const selection = getSelection();
  selection.removeAllRanges();
  // Editing the passage can remove its saved endpoint. That checkpoint then has no
  // selection to restore, and the returned viewport supplies the next walk's origin.
  if (
    ends?.every(
      ([node, offset]) =>
        drawn(node.nodeType === 1 ? node : upFrom(node)) &&
        offset <= (node.nodeType === 3 ? node.length : node.childNodes.length),
    )
  ) {
    selectEnds(...ends);
  }
}

// Whether this document is writing an entry itself. The Navigation API fires `navigate`
// synchronously inside `pushState` and `replaceState`, and those events look like a
// press on a link to the fragment the page already shows: both are a same-document
// `replace` or `push` with no hash change. Only the writer can tell them apart.
let writing = false;
function write(method, state, url) {
  writing = true;
  try {
    history[method](state, "", url);
  } finally {
    writing = false;
  }
}

export function pushEntry(url, state = null) {
  write("pushState", state, url);
}

export function replaceEntry(url, state = history.state) {
  write("replaceState", state, url);
}

// A route can reveal or hydrate before it knows whether arrival will succeed. Capture
// its outgoing checkpoint now, but write only on success. A synchronous round trip to
// the source offset lets native history save that offset too, without an intermediate
// paint, including in browsers without the Navigation API. The Navigation listener's
// live focus reading is replaced with the original working place after the write.
export function prepareEntry() {
  const key = window.navigation?.currentEntry.key;
  const place = readPlace();
  const offset = [scrollX, scrollY];
  return (url, state, replace) => {
    if (replace) {
      replaceEntry(url, state);
      return;
    }
    const arrival = [scrollX, scrollY];
    window.scrollTo({ left: offset[0], top: offset[1], behavior: "instant" });
    pushEntry(url, state);
    window.scrollTo({ left: arrival[0], top: arrival[1], behavior: "instant" });
    if (key) places.set(key, place);
  };
}

// `claim(url)` returns the handler that places the page at a traversal to `url`, or
// nothing when the entry is not the claimant's. The first claim to answer takes it.
export function claimTraversals(claim, { signal } = {}) {
  claims.add(claim);
  signal?.addEventListener("abort", () => claims.delete(claim), { once: true });
}

let mounted = false;
export function mountHistory({ followFragment, returnToFragment }) {
  if (mounted) return;
  mounted = true;
  window.navigation?.addEventListener("navigate", (event) => {
    if (!event.destination.sameDocument || !event.canIntercept) return;
    const url = new URL(event.destination.url);
    if (event.navigationType !== "replace") {
      const live = new Set(window.navigation.entries().map((entry) => entry.key));
      for (const key of places.keys()) if (!live.has(key)) places.delete(key);
      places.set(window.navigation.currentEntry.key, readPlace());
    }
    if (event.navigationType === "traverse") {
      const handler = claimed(url) ?? returnToFragment(url);
      const place = places.get(event.destination.key);
      const mayReturn = retainUserIntent({ available: () => !event.signal.aborted });
      event.intercept({
        scroll: "manual",
        focusReset: "manual",
        handler: async () => {
          let work;
          mayReturn.handoff(() => {
            work = handler?.();
          });
          await work;
          if (!mayReturn()) return;
          if (!handler) event.scroll();
          if (place) returnPlace(place);
        },
      });
      return;
    }
    // A followed link again to the fragment already shown is a `replace` with no hash
    // change, and still a trip: its target may have been shut since.
    if (writing || event.formData || !url.hash) return;
    const handler = followFragment(url);
    if (handler) event.intercept({ scroll: "manual", focusReset: "manual", handler });
  });
}

function claimed(url) {
  for (const claim of claims) {
    const handler = claim(url);
    if (handler) return handler;
  }
  return null;
}
