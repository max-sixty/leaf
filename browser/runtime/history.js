/* The entries this document adds to session history, and the traversals among them.
 *
 * Every same-document entry is a place the user can come Back to. `pushEntry` adds one,
 * leaving the entry the user was on with the scroll offset the browser saves on it;
 * `replaceEntry` renames the entry the user is on and keeps its state. A new entry
 * starts with no state of its own, since state belongs to the entry that set it.
 * Travel prepares its outgoing checkpoint before revealing a destination and commits
 * it only after arrival succeeds. Failed or canceled routes add no return stop.
 *
 * Only a route the user's gesture began on the entry being left adds an entry: a
 * followed link, a walk's step, a list's row, Undo's trip (anchor-travel.js,
 * `prepareNavigationStep`). A return, an arrival, a revision or news never adds one,
 * nor does a view opened, put away or handed to another reader where the user stands,
 * which renames the entry at most (thread views, thread/address.js): each opens its
 * thread with `travel: false` or `history: false` (thread/destination.js), and so takes
 * no departure. Browsers keep that rule too: Chromium marks
 * a document's entries skippable by Back once one is added without the user's
 * activation, and Firefox 135 and later skip such entries, so an entry added without a
 * gesture would cost the user the Back steps they made. A rename waits for a
 * navigation under way to end (`replaceEntry`), since a history write aborts it. A
 * reload's rename doesn't wait (`reloadAt`): the reload ends any navigation under way
 * anyway, and an intercepted navigation commits its URL at once, so the address the
 * reload marks is the entry the user is on.
 *
 * Which thread view an entry shows is its URL's (`?thread=`, thread/address.js), which
 * claims each traversal first, to open or put away that view. A working-place
 * checkpoint owns the viewport offset, focus and selection together, and where focus
 * was in a thread view, that thread, the route's request for that view, and its
 * scroll, since the view the return opens is a new drawing of it (`returnPlace`).
 *
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
 * placement, and focus Firefox dropped to the body as it applied the traversal goes
 * back to where the return put it (notes/browser-support.md, "Firefox drops focus as
 * it applies a same-document traversal"). Scroll anchoring holds that block still
 * through a change above it, but a change inside it in that frame moves it as the
 * browser does, and a pinned block
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
import {
  deepFocus,
  drawn,
  focusDestination,
  readCaret,
  landAtReading,
} from "./focus.js";

import { retainUserIntent } from "./user-intent.js";
import { placeOf } from "./current-target.js";
import { closestAcross, inChrome, upFrom } from "./shadow-tree.js";
import { presented } from "./geometry.js";
import { unconcealedReadingRegions } from "./reading-regions.js";
import { readingBlock } from "./reading-place.js";
import {
  moveScrollerBy,
  pageScroller,
  scrollGoal,
  stopBrowserScroll,
  stopGlide,
} from "./scrolling.js";
import { drawnThreadId, THREAD, THREAD_VIEW, wholeThread } from "./thread/selectors.js";
import { nextRender } from "./rendering.js";
import { aborted } from "./abort.js";

/** @typedef {[WeakRef<Node>, number]} HeldSelectionEnd
 * @typedef {{id: string, reader: "primary" | null, scroll: number | null}} ThreadPlace
 * @typedef {{focus: WeakRef<Element> | null, place: WeakRef<Element> | null,
 * caret: import("./focus.js").Caret | null, ends: [HeldSelectionEnd, HeldSelectionEnd] | null,
 * thread: ThreadPlace | null, offset: [number, number]}} WorkingPlace
 * @typedef {() => void | boolean | Promise<void | boolean>} TraversalHandler
 * @typedef {(url: URL) => TraversalHandler | null | undefined} TraversalClaim
 * @typedef {(url: URL, place: WorkingPlace | null) => TraversalHandler | null | undefined} ThreadClaim
 */
/** @type {Set<TraversalClaim>} */
const claims = new Set();
/** @type {Map<string, WorkingPlace>} */
const places = new Map();

// The user's working place, read once before something borrows it: leaving an entry, or
// stepping into the floating panel, whose place-keeping commands hand it back. `focus` is
// the node they had focused, when the reading comes after focus has left it. `thread`
// is the thread view that node stood in, which outlasts the view's drawing
// (`returnPlace`). Plain
// endpoints keep a removed passage from being silently retargeted by a live Range. pageRange
// shares the declared-shadow reading used for commenting; the selection's direction also
// keeps its working end. The offset is where the page is headed (`scrollGoal`), as a
// key pressed while Leaf still moves the page acts as if the motion had landed: a second
// `m` pressed while the first still glides leaves the obligation the first landed on,
// so Back returns there rather than to wherever the glide had reached.
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
    thread: threadPlaceOf(focus),
    offset: [scrollX, scrollGoal(pageScroller)],
  };
}

// The thread view `focus` stands in, which the field's presence says the user was in:
// the whole of the thread drawn there, a margin card's or the floating panel's; the
// route's `reader` request that opens it in that view again (thread/destination.js),
// the primary reader's for a chrome's view of one thread; and its scroll where that box
// scrolls the thread, as the panel's view does. A card keeps its own reading as it
// closes and opens.
/** @param {Element | null} focus @returns {ThreadPlace | null} */
function threadPlaceOf(focus) {
  const drawn = focus && closestAcross(focus, THREAD);
  if (!drawn || !inChrome(drawn)) return null;
  const whole = wholeThread(drawn);
  const id = drawnThreadId(whole);
  if (!id) return null;
  return {
    id,
    reader: whole.matches(THREAD_VIEW) ? "primary" : null,
    scroll: whole.scrollHeight > whole.clientHeight ? whole.scrollTop : null,
  };
}

// Put the user back in a place `readPlace` read. A live revision may have removed or
// shortened what it named since, so a node no longer drawn is not returned to, and a
// selection end past its node's current length returns to what is left of that node,
// its end. The thread view that drew the focused node may have closed since: travel
// puts the panel's view away where it would stand over the place it lands on, and a
// card closes as the user leaves its passage. The traversal's claimant has opened the
// view the entry names again by then (thread/address.js), a new drawing, so the user
// goes into that drawing of the thread they were in, at the offset they had read it to.
// Elsewhere the user returns to the node's page target, the same working place seen
// from the page. The return settles once they are there, so a command acting on the
// returned place awaits it.
/** @param {WorkingPlace} checkpoint @returns {Promise<void>} */
export async function returnPlace(checkpoint) {
  const focus = checkpoint.focus?.deref();
  const thread = checkpoint.thread;
  const drawing = thread && threadDrawing?.(thread.id);
  if (focus !== document.body && focus?.isConnected && presented(focus)) {
    focusDestination(focus, "return", { caret: checkpoint.caret });
    // A field's caret is its whole selection, and clearing the document's would
    // collapse it.
    if (checkpoint.caret) return;
  } else if (thread && drawing && presented(drawing)) {
    focusDestination(drawing, "return");
    if (thread.scroll !== null)
      moveScrollerBy(drawing, thread.scroll - drawing.scrollTop);
  } else returnToPlace(checkpoint);
  returnSelection(checkpoint);
}

/** @param {WorkingPlace} checkpoint */
function returnToPlace(checkpoint) {
  const place = checkpoint.place?.deref();
  if (place?.isConnected && presented(place)) focusDestination(place, "return");
  else landAtReading();
}

/** @param {WorkingPlace} checkpoint */
function returnSelection(checkpoint) {
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

// Each entry this document writes names the thread view standing open as it is
// written (thread/address.js, `name`), so no URL a route, a widget or a waiting rename
// captured earlier carries a thread name the page no longer shows.
/** @type {(url: URL) => URL} */
let nameThread = (url) => url;
/** @param {string | URL | null | undefined} url */
const named = (url) => nameThread(new URL(url ?? location.href, location.href));

/** @param {string | URL | null | undefined} url @param {unknown} state */
export function pushEntry(url, state = null) {
  write("pushState", state, named(url));
}

// A rename renames the entry the user is on, at `url`, or at its own address where
// `url` is absent. One asked for while a navigation is under way waits for it to end,
// since a history write aborts the navigation in Chromium and Firefox alike, and a
// rename is no step of the user's that should end one, as a tab set naming the view a
// traversal's claimant opened would end that traversal before its place came back. It
// renames only the entry it was asked on: where a newer navigation has moved the user to
// another, it is dropped. Without `state`, the entry keeps its own, read when the rename
// is written. A rename that would change nothing writes nothing, and one the browser
// refuses over its rate limit, as Safari does by throwing past 100 in 30 seconds, is
// dropped, since the next write names the entry again.
/** @param {string | URL | null | undefined} [url] @param {unknown} [state] */
export function replaceEntry(url, state) {
  const transition = window.navigation.transition;
  if (transition) {
    const asked = window.navigation.currentEntry?.key;
    const rename = () => {
      if (window.navigation.currentEntry?.key === asked) replaceEntry(url, state);
    };
    transition.finished.then(rename, rename);
    return;
  }
  const address = named(url);
  const kept = state === undefined ? history.state : state;
  if (address.href === location.href && kept === history.state) return;
  try {
    write("replaceState", kept, address);
  } catch (error) {
    if (!(error instanceof DOMException && error.name === "SecurityError")) throw error;
  }
}

/** Rename the entry the user is on to `url` and reload it, without waiting for a
 * navigation under way. @param {URL} url */
export function reloadAt(url) {
  write("replaceState", history.state, named(url));
  location.reload();
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
      write("replaceState", sourceState, sourceUrl);
    setScroll(pageScroller, { left: offset[0], top: offset[1], behavior: "instant" });
    pushEntry(url);
    setScroll(pageScroller, { ...arrival, behavior: "instant" });
    if (key) places.set(key, place);
  };
}

// `claim(url)` returns the handler that reveals the destination of a traversal, or
// nothing when the entry is not the claimant's. The first claim to answer takes it. The
// thread view the entry names opens or goes after it, whoever claimed the traversal
// (`mountHistory`).
// A handler places the viewport itself unless it resolves to false, handing placement
// back to the entry's checkpoint (or the browser when no checkpoint was captured).
// Travel follows it where the entry's fragment names a place its view doesn't show.
/** @param {TraversalClaim} claim @param {{signal?: AbortSignal}} [options] */
export function claimTraversals(claim, { signal } = {}) {
  claims.add(claim);
  signal?.addEventListener("abort", () => claims.delete(claim), { once: true });
}

// The thread view an entry names (thread/address.js): `claim` opens it or puts it away
// on a traversal, as it reads the entry's saved place, and resolves to false, since it
// places nothing; `drawing` is the drawing of a thread a return puts the user in
// (`returnPlace`), wherever the thread's route drew it (thread/destination.js); and
// `name` names the open thread in a URL this document writes.
/** @type {((id: string) => Element | null) | null} */
let threadDrawing = null;
let mounted = false;
/** @param {{followFragment: (url: URL) => TraversalHandler | null | undefined | false,
 * returnToFragment: (url: URL) => TraversalHandler | null | undefined,
 * thread: {claim: ThreadClaim, drawing: (id: string) => Element | null,
 * name: (url: URL) => URL}}} options */
export function mountHistory({ followFragment, returnToFragment, thread }) {
  if (mounted) return;
  mounted = true;
  threadDrawing = thread.drawing;
  nameThread = thread.name;
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
      const place = places.get(event.destination.key);
      const claim = claimed(url);
      const mayReturn = retainUserIntent({ available: () => !event.signal.aborted });
      const applied = traversalApplied(event.signal);
      event.intercept({
        scroll: "manual",
        focusReset: "manual",
        handler: async () => {
          if (!mayReturn()) return;
          // Cancel the outgoing placement, including its nested reading regions: a
          // return goes back to a place, so a glide under way stops where it stands.
          // The browser's compositor update can outlive this task, so restore only after
          // a complete rendering update has carried the cancellation to the browser.
          const scrollers = new Set([
            pageScroller,
            ...unconcealedReadingRegions().map((region) => region.body),
          ]);
          for (const box of scrollers) stopGlide(box);
          await stopBrowserScroll(scrollers);
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
          if (!placed && !place) event.scroll();
          else if (!placed && place)
            setScroll(pageScroller, {
              left: place.offset[0],
              top: place.offset[1],
              behavior: "instant",
            });
          // The thread view opens or goes once the page stands where the entry left it,
          // so a card takes its side against the page the user returns to: opened
          // against the page they leave, it stood below its words and over them once
          // the page moved back. What it does is decided then too, from the views the
          // earlier steps left open: revealing the fragment can put away the panel's
          // view of the very thread the entry names.
          work = undefined;
          mayReturn.handoff(() => {
            work = thread.claim(url, place ?? null)?.();
          });
          await work;
          if (!mayReturn() || (!placed && !place)) return;
          if (place) mayReturn.handoff(() => void returnPlace(place));
          // Firefox and WebKit may apply the traversal after this placement and move
          // the page as they do (above). Once they have, the first block on screen goes
          // back to where the placement stood it. Firefox also drops focus to the body
          // as it applies the traversal (Firefox 160), so the node the return put the
          // user on takes it back.
          const returned = place ? deepFocus() : null;
          const mark = readingBlock() ?? document.documentElement;
          const stood = mark.getBoundingClientRect().top;
          await applied;
          if (!mayReturn()) return;
          if (
            returned &&
            returned !== document.body &&
            returned.isConnected &&
            deepFocus() === document.body
          )
            mayReturn.handoff(() =>
              focusDestination(returned, "return", {
                caret: returned === place?.focus?.deref() ? place.caret : null,
              }),
            );
          if (!mark.isConnected) return;
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
  /** @type {Promise<void>} */
  const applied = new Promise((resolve) =>
    addEventListener("popstate", () => nextRender(() => resolve()), {
      once: true,
      signal,
    }),
  );
  return Promise.race([applied, aborted(signal)]);
}

/** @param {URL} url */
function claimed(url) {
  for (const claim of claims) {
    const handler = claim(url);
    if (handler) return handler;
  }
  return null;
}
