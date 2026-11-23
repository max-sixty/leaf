/* The entries this document adds to session history, and the traversals among them.
 *
 * Every same-document entry is a place the user can come Back to. `pushEntry` adds one;
 * `replaceEntry` renames the entry the user is on and keeps its `history.state`. A new
 * entry starts with no state of its own, since state belongs to the entry that set it.
 * Travel prepares the record of where the user is before revealing a destination and
 * commits it only after arrival succeeds. Failed or canceled routes add no return stop.
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
 * Which thread view an entry shows is its URL's (`?thread=`, thread/address.js). Where
 * the user was on it is the entry's record (`readRecord`), which history keeps in the
 * entry's own state, the Navigation API's, which outlives a reload of the document.
 *
 * The record holds the page, by what stood on screen (reading-place.js,
 * `capturePlace`); the reply or summary at the top of the open thread's view and how far
 * into it (thread/reply-landing.js, `readingIn`), since the view a return opens is a
 * new drawing of the thread; focus, where it is in a draft's own box, as a new
 * comment's or a message's being rewritten, by that draft (drafts.js, `draftFocus`),
 * since the arriving document draws that box only once its owner's route reopens it,
 * and anywhere else, a thread's reply included, by the identity a revision's reload
 * carries it by, with the caret (carry.js, `focusKey`); the selection
 * (`readSelection`); and the list
 * the floating panel showed, with the row the user was on, which the URL's claim shows
 * again (thread/address.js). It holds no copy of the thread the URL names: a part of
 * the open view names that view's thread as `null`. Until the reader a thread opens in
 * is the tab's setting, it also holds which reader the open view was, which the URL's
 * claim passes on. Where what focus was on is gone, the user comes back to the reading
 * place beside the page's landmark (focus.js, `landAtReading`); a draft's box opens
 * again by its owner's Resume writing route, its words coming from the drafts store,
 * which history never copies.
 *
 * The user leaves an entry whenever they leave it for another entry, by a reload, or
 * for another document, and history writes the record then, and never earlier: the
 * user may change where they are on an entry until they leave it, and a rename, which
 * writes the entry's URL with `history.state`, drops the entry's own state in Chromium
 * and Firefox alike. A route reads its record before it reveals anything, and the push
 * it commits writes that record (`prepareEntry`); a departure from the document writes
 * it at `beforeunload`, the last moment both engines keep the write through a reload
 * (measured: Firefox drops one made at `pagehide` as the page reloads). The user arrives
 * at an entry by a traversal within the document, or by a reload or a traversal from
 * another document (`arrivalRecord`), and each returns them to its record the same way
 * (`returnOnArrival`). Rejected: a map of live nodes and pixel offsets by entry key,
 * which a reload emptied, so Back after it had nothing to return to, and whose offsets
 * named content a revision had moved.
 *
 * A revision's handoff (version.js) and the floating panel's hold of where the user
 * stepped in from (`readPlace`) read the same page place, focus identity and thread
 * reading, and stay apart from this record where they need what it must not hold. The
 * handoff restores a revision's reload itself, in place of this record: besides what
 * that reload alone owes, each reading region's place, the words being written and the
 * values typed, which history never puts back, the comparison and the pointer, it
 * reopens the thread views by the margin's and the panel's own rules for a revision,
 * as a card whose passage the revision hid opening in the panel, and hands a reply
 * being written back with its words. The hold is read as the user steps into the panel
 * and used while they stand there, in this document, so it keeps the node they left
 * and its page place, read before the step put away the card that drew it, where a
 * record could name only what the arriving document draws.
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
 * no record for at the top of the page.
 * Nested reading regions stop with that placement but keep their current offsets;
 * a record restores the document viewport.
 *
 * Without a record, the browser restores its saved offset, except that
 * Chrome answers a traversal to an entry whose fragment names an element by scrolling to that element
 * instead (measured: Back to `#s2` after reading 3000px down landed on `#s2` at 666).
 * So every same-document traversal comes through here, through the Navigation API. An
 * owner that claims the destination (`claimTraversals`) can reveal and place the page
 * itself, as a root tab set does for the entry of each of its views. Travel takes the
 * traversal after any claimant (`mountHistory`'s `returnToFragment`, anchor-travel.js)
 * where the entry's fragment still names a place the page doesn't show, such as a
 * widget's key whose part the widget no longer draws inside the view a tab set has
 * just opened: the record was read over a page that has changed, so travel reveals
 * the place and lands on it. Any other traversal is
 * intercepted to restore its record, or the browser's saved offset
 * for an entry without one. Back and Forward restore that place after its
 * owner has revealed the view, so the next command reads the returned place from the browser.
 * A record is where the user was, never a reading of where they are now; a newer
 * gesture cancels a delayed return, and what it names that the page no longer draws
 * is not returned to.
 *
 * A fragment navigation, a followed `#id` link, is not a traversal: it adds its entry
 * and is a navigation step to the element it names. Travel claims it (`followFragment`) where the
 * fragment names an element of the page, and lands it through the browser's own
 * fragment placement rule once travel has cleared and revealed the way; any other fragment
 * keeps native landing. An entry this document writes through `pushEntry` or
 * `replaceEntry`, as travel and a tab set do, is not a fragment navigation and is never
 * claimed. */

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
import { closestAcross, inChrome, renderedUnder, upFrom } from "./shadow-tree.js";
import { presented } from "./geometry.js";
import { unconcealedReadingRegions } from "./reading-regions.js";
import {
  capturePlace,
  hasLandmark,
  rawOffsetFits,
  readingBlock,
  restorePlace,
} from "./reading-place.js";
import { pageScroller, scrollGoal, stopBrowserScroll, stopGlide } from "./scrolling.js";
import { drawnThreadId, THREAD, wholeThread } from "./thread/selectors.js";
import { readingIn, showReading } from "./thread/reply-landing.js";
import {
  anchorForRange,
  anchoringIsReady,
  resolveAnchor,
} from "./anchor-resolution.js";
import { targetSegments } from "./resolved-target.js";
import {
  blockAt,
  pageDocument,
  pageWords,
  pointAt,
  readingHolding,
  segmentsIn,
  spanIn,
} from "./passages.js";
import { focusKey, focusedBy } from "./carry.js";
import { draftFocus } from "./drafts.js";
import { nextRender } from "./rendering.js";
import { aborted } from "./abort.js";

/** @typedef {[WeakRef<Node>, number]} HeldSelectionEnd
 * @typedef {{id: string, reading: import("./thread/reply-landing.js").ThreadReading | null}} ThreadPlace
 * @typedef {{focus: WeakRef<Element> | null, place: WeakRef<Element> | null,
 * caret: import("./focus.js").Caret | null, ends: [HeldSelectionEnd, HeldSelectionEnd] | null,
 * thread: ThreadPlace | null}} WorkingPlace
 * @typedef {import("./thread/reply-landing.js").ThreadReading & {reader: "primary" | null}} ViewReading
 * @typedef {(Omit<import("./carry.js").FocusKey, "thread"> & {thread?: string | null})
 * | NonNullable<ReturnType<typeof draftFocus>>} RecordFocus
 * @typedef {{anchor: import("./anchor-resolution.js").CapturedAnchor, ends: [number, number]}
 * | {thread: string | null, message: string, ends: [number, number]}} RecordSelection
 * @typedef {{view: string, row: string | null}} RecordList
 * @typedef {{page: import("./reading-place.js").ReadingPlace | null,
 * focus: RecordFocus | null, selection: RecordSelection | null,
 * thread: ViewReading | null, list: RecordList | null}} EntryRecord
 * @typedef {import("./thread/address.js").OpenThread} OpenThread
 * @typedef {() => void | boolean | Promise<void | boolean>} TraversalHandler
 * @typedef {(url: URL) => TraversalHandler | null | undefined} TraversalClaim
 * @typedef {(url: URL, record: EntryRecord | null) => TraversalHandler | null | undefined} ThreadClaim
 */
/** @type {Set<TraversalClaim>} */
const claims = new Set();

// The user's working place, read once as they step into the floating panel, whose
// place-keeping commands hand it back. `focus` is the node they had focused, when the
// reading comes after focus has left it. `thread` is the thread view that node stood
// in, which outlasts the view's drawing (`returnPlace`). Plain endpoints keep a removed
// passage from being silently retargeted by a live Range. pageRange shares the
// declared-shadow reading used for commenting; the selection's direction also keeps its
// working end.
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
  };
}

// The thread view `focus` stands in: the whole of the thread drawn there, a margin
// card's or the floating panel's, and where it was read to (thread/reply-landing.js).
/** @param {Element | null} focus @returns {ThreadPlace | null} */
function threadPlaceOf(focus) {
  const drawn = focus && closestAcross(focus, THREAD);
  if (!drawn || !inChrome(drawn)) return null;
  const whole = wholeThread(drawn);
  const id = drawnThreadId(whole);
  return id ? { id, reading: readingIn(whole) } : null;
}

// Put the user back in a place `readPlace` read. A live revision may have removed or
// shortened what it named since, so a node no longer drawn is not returned to, and a
// selection end past its node's current length returns to what is left of that node,
// its end. The thread view that drew the focused node may have closed since, as a card
// closes when the user leaves its passage; where a route has drawn the thread again, the
// user goes into that drawing of it, at the offset they had read it to. Elsewhere the
// user returns to the node's page target, the same working place seen from the page.
// The return settles once they are there, so a command acting on the returned place
// awaits it.
/** @param {WorkingPlace} checkpoint @returns {Promise<void>} */
export async function returnPlace(checkpoint) {
  const focus = checkpoint.focus?.deref();
  const thread = checkpoint.thread;
  const drawing = thread && threadParts?.focusTarget(thread.id, "thread");
  if (focus !== document.body && focus?.isConnected && presented(focus)) {
    focusDestination(focus, "return", { caret: checkpoint.caret });
    // A field's caret is its whole selection, and clearing the document's would
    // collapse it.
    if (checkpoint.caret) return;
  } else if (thread && drawing && presented(drawing)) {
    focusDestination(drawing, "return");
    if (thread.reading) showReading(drawing, thread.reading);
  } else {
    const place = checkpoint.place?.deref();
    if (place?.isConnected && presented(place)) focusDestination(place, "return");
    else landAtReading();
  }
  const ends = checkpoint.ends;
  returnSelection(ends && [returnEnd(ends[0]), returnEnd(ends[1])]);
}

// Select between two ends, or none where either is gone. Editing the passage can remove
// a saved end; the place returned to then supplies the next walk's origin.
/** @param {[import("./native-selection.js").SelectionEnd | null, import("./native-selection.js").SelectionEnd | null] | null} ends */
function returnSelection(ends) {
  const selection = getSelection();
  if (!selection) return;
  selection.removeAllRanges();
  if (ends?.[0] && ends[1]) selectEnds(ends[0], ends[1]);
}

/** @param {HeldSelectionEnd} end @returns {import("./native-selection.js").SelectionEnd | null} */
function returnEnd([ref, offset]) {
  const node = ref.deref();
  if (!node || !drawn(node instanceof Element ? node : upFrom(node))) return null;
  const length = node instanceof CharacterData ? node.length : node.childNodes.length;
  return [node, Math.min(offset, length)];
}

// ---------- an entry's record ----------
// Where the user is, as the record an entry keeps (the header). The page is read where
// it is headed (`scrollGoal`), as a key pressed while Leaf still moves the page acts as
// if the motion had landed: a second `m` pressed while the first still glides leaves
// the obligation the first landed on, so Back returns there rather than to wherever the
// glide had reached. The reading is taken over the goal in one synchronous round trip,
// which the glide, holding the box only while it stands where the glide wrote it, goes
// on from. Before the page's words can be anchored, the page has no place to read, and
// its entry comes back where the browser restores it.
/** @returns {EntryRecord} */
function readRecord() {
  const goal = scrollGoal(pageScroller);
  const top = pageScroller.scrollTop;
  const gliding = Math.abs(goal - top) >= 1;
  if (gliding) setScroll(pageScroller, { top: goal, behavior: "instant" });
  const page = anchoringIsReady() ? capturePlace(null) : null;
  if (gliding) setScroll(pageScroller, { top, behavior: "instant" });
  const open = threadParts?.open() ?? null;
  const drawing = open && threadParts?.focusTarget(open.id, "thread");
  const reading = drawing && readingIn(drawing);
  const at = deepFocus();
  // Focus in a draft's own box names the draft, whose owner draws the box again only
  // as its route reopens it; its words stay in the drafts store.
  const focus = draftFocus(at) ?? focusKey(at);
  return {
    page,
    // The open view's thread is the one the entry's URL names (the header).
    focus: unnamed(focus, open),
    selection: anchoringIsReady() ? unnamed(readSelection(), open) : null,
    thread: open && reading ? { ...reading, reader: open.reader } : null,
    list: listShown?.() ?? null,
  };
}

// `part`, with the open view's thread, which the entry's URL names, named as `null`
// (the header).
/** @template {object | null} T @param {T} part @param {OpenThread | null} open @returns {T} */
const unnamed = (part, open) =>
  part && "thread" in part && part.thread === open?.id
    ? { ...part, thread: null }
    : part;

// The page's selection: the passage a comment on its words would quote, or on its
// block's words for a caret or a run of spaces (anchor-resolution.js, `anchorForRange`),
// found again by its words in whatever revision draws them; and each of its ends, anchor
// end first, as how far it stands from that passage's start in the reading of the page
// that holds it (passages.js, `spanIn`, `pointAt`). The quote alone can't hold the ends:
// it trims the spaces at its edges and holds no caret, so a caret before a space came
// back after it. Words selected in Leaf's own interface are no passage of the page.
/** @returns {EntryRecord["selection"]} */
function readSelection() {
  const selection = getSelection();
  const range = selection?.rangeCount ? pageRange(selection) : null;
  if (!selection || !range) return null;
  /** @param {[number, number]} ends @returns {[number, number]} */
  const directed = (ends) =>
    selectionBackward(selection, range) ? [ends[1], ends[0]] : ends;
  const turn = closestAcross(range.startContainer, "[data-lf-message]");
  if (turn && renderedUnder(range.endContainer, turn))
    return inMessage(turn, range, directed);
  if (!pageWords(range.startContainer)) return null;
  const words = /\S/.test(range.toString()) ? range : blockWords(range.startContainer);
  const anchor = words && anchorForRange(words);
  const segments = anchor?.quote ? targetSegments(resolveAnchor(anchor)) : [];
  if (!anchor || !segments[0]) return null;
  const reading = readingHolding(segments[0].node);
  const [base] = spanIn(reading, segments);
  const start = readingIndex(reading, range.startContainer, range.startOffset);
  const end = readingIndex(reading, range.endContainer, range.endOffset);
  if (start === null || end === null) return null;
  return { anchor, ends: directed([start - base, end - base]) };
}
// A selection inside one message of a thread, which the page's reading doesn't hold:
// the message, by its thread and its id, and each end as how many of its characters
// come before it, which name the same place in every drawing of the message, since its
// words are the log's.
/** @param {Element} turn @param {AbstractRange} range @param {(ends: [number, number]) => [number, number]} directed
 * @returns {RecordSelection | null} */
function inMessage(turn, range, directed) {
  const drawing = closestAcross(turn, THREAD);
  const thread = drawing && drawnThreadId(wholeThread(drawing));
  const message = turn.getAttribute("data-lf-message");
  if (!thread || !message) return null;
  /** @param {Node} node @param {number} offset */
  const before = (node, offset) => {
    const words = document.createRange();
    words.setStart(turn, 0);
    words.setEnd(node, offset);
    return words.toString().length;
  };
  const start = before(range.startContainer, range.startOffset);
  const end = before(range.endContainer, range.endOffset);
  return { thread, message, ends: directed([start, end]) };
}
// The words of the block holding `node`, as a range.
/** @param {Node} node */
function blockWords(node) {
  const block = blockAt(node);
  if (!block) return null;
  const words = document.createRange();
  words.selectNodeContents(block);
  return words;
}
// Where a point stands in `reading`: its text's place there and its offset, or, for a
// point between elements, the first character after it in its block, else the end of
// the last before it; null for a point the reading doesn't hold.
/** @param {import("./passages.js").PageReading} reading @param {Node} node @param {number} offset */
function readingIndex(reading, node, offset) {
  /** @type {Node} */
  let text = node;
  let at = offset;
  if (!(node instanceof Text)) {
    const block = blockAt(node) ?? pageDocument();
    const after = document.createRange();
    after.setStart(node, offset);
    after.setEnd(block, block.childNodes.length);
    const before = document.createRange();
    before.setStart(block, 0);
    before.setEnd(node, offset);
    const next = segmentsIn(after)[0];
    const last = next ? null : segmentsIn(before).at(-1);
    if (next) [text, at] = [next.node, next.start];
    else if (last) [text, at] = [last.node, last.end];
    else return null;
  }
  const start = text instanceof Text ? reading.positions.get(text) : undefined;
  return start === undefined ? null : start + at;
}

// Put the user back where a record says they were, once the claimants have revealed
// what the entry shows and the page stands where the record places it: at the reading
// they had in the open thread's view, then on what focus was on (carry.js,
// `focusedBy`), or, where the page no longer draws it, at the reading place beside the
// page's landmark, unless focus was in the floating panel's list, which the address's
// claim has shown standing on its row (thread/address.js). The return settles once they
// are there, so a command acting on the returned place awaits it.
/** @param {EntryRecord} record */
function returnTo(record) {
  const open = threadParts?.open() ?? null;
  const drawing = open && threadParts?.focusTarget(open.id, "thread");
  if (record.thread && drawing) showReading(drawing, record.thread);
  const key = record.focus;
  /** @param {string} id */
  const drawingOf = (id) => threadParts?.focusTarget(id, "thread") ?? null;
  // A draft's box opens again where the user stands, by its owner's Resume writing
  // route, with the user on the box or in its words at their caret.
  if (key && "draft" in key) {
    void draftReturn?.(key);
    return;
  }
  /** @type {Element | null} */
  let focus = null;
  if (key) {
    const thread = key.thread === null ? (open?.id ?? null) : key.thread;
    if (thread !== null)
      focus = focusedBy(
        /** @type {import("./carry.js").FocusKey} */ ({ ...key, thread }),
        drawingOf,
      );
  }
  const caret = key?.caret ?? null;
  if (focus && focus !== document.body && presented(focus)) {
    focusDestination(focus, "return", { caret });
    // A field's caret is its whole selection, and clearing the document's would
    // collapse it.
    if (caret) return;
  } else if (!record.list) landAtReading();
  const { selection } = record;
  returnSelection(
    selection &&
      ("message" in selection
        ? messageEnds(selection, selection.thread ?? open?.id ?? null)
        : passageEnds(selection)),
  );
}

// The ends a record's selection names now, or none where its words are gone. An end
// standing on an edge between elements, which holds no character, comes back just after
// the character before it.
/** @param {Extract<RecordSelection, {anchor: unknown}>} selection
 * @returns {[import("./native-selection.js").SelectionEnd, import("./native-selection.js").SelectionEnd] | null} */
function passageEnds({ anchor, ends }) {
  const segments = targetSegments(resolveAnchor(anchor));
  // Words the page draws, since a passage resolves through what a reader has shut too.
  if (!segments[0] || !segments.every(({ node }) => drawn(upFrom(node)))) return null;
  const reading = readingHolding(segments[0].node);
  const [base] = spanIn(reading, segments);
  /** @param {number} i @returns {import("./native-selection.js").SelectionEnd | null} */
  const point = (i) => {
    const at = pointAt(reading, base + i);
    if (at) return [at.node, at.offset];
    const before = pointAt(reading, base + i - 1);
    return before ? [before.node, before.offset + 1] : null;
  };
  const from = point(ends[0]);
  const to = point(ends[1]);
  return from && to ? [from, to] : null;
}

// The ends a message selection names in the drawing of its thread, or none where the
// message is gone or shut.
/** @param {Extract<RecordSelection, {message: string}>} selection @param {string | null} thread
 * @returns {[import("./native-selection.js").SelectionEnd, import("./native-selection.js").SelectionEnd] | null} */
function messageEnds({ message, ends }, thread) {
  const drawing = thread ? threadParts?.focusTarget(thread, "thread") : null;
  const turn = drawing?.querySelector(`[data-lf-message="${CSS.escape(message)}"]`);
  if (!turn || !drawn(turn)) return null;
  /** @param {number} count @returns {import("./native-selection.js").SelectionEnd | null} */
  const point = (count) => {
    const texts = document.createTreeWalker(turn, NodeFilter.SHOW_TEXT);
    let left = count;
    for (let text = texts.nextNode(); text; text = texts.nextNode()) {
      const { length } = /** @type {Text} */ (text);
      if (left <= length) return [text, left];
      left -= length;
    }
    return null;
  };
  const from = point(ends[0]);
  const to = point(ends[1]);
  return from && to ? [from, to] : null;
}

// Whether a record can place the page itself: a landmark it can find again, its start,
// or a raw offset read in this scroller at this width and revision (reading-place.js).
/** @param {import("./reading-place.js").ReadingPlace} page */
const placesPage = (page) =>
  Boolean(page.start) || hasLandmark(page) || rawOffsetFits(page, pageScroller);

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

// A route can reveal or hydrate before it knows whether arrival will succeed. Read
// where the user is now, before anything moves, and write it to the entry they leave
// only as the step is pushed, on success (`leaving`).
/** @type {EntryRecord | null} */
let leaving = null;
export function prepareEntry() {
  const record = readRecord();
  const sourceUrl = location.href;
  const sourceState = history.state;
  return /** @param {string | URL} url */ (url) => {
    // Exposing another view renames this entry. Its original URL and state belong to
    // the entry left; the exposed destination belongs to the new entry.
    if (location.href !== sourceUrl || history.state !== sourceState)
      write("replaceState", sourceState, sourceUrl);
    leaving = record;
    try {
      pushEntry(url);
    } finally {
      leaving = null;
    }
  };
}

// `claim(url)` returns the handler that reveals the destination of a traversal, or
// nothing when the entry is not the claimant's. The first claim to answer takes it. The
// thread view the entry names opens or goes after it, whoever claimed the traversal
// (`mountHistory`).
// A handler places the viewport itself unless it resolves to false, handing placement
// back to the entry's record (or the browser for an entry without one).
// Travel follows it where the entry's fragment names a place its view doesn't show.
/** @param {TraversalClaim} claim @param {{signal?: AbortSignal}} [options] */
export function claimTraversals(claim, { signal } = {}) {
  claims.add(claim);
  signal?.addEventListener("abort", () => claims.delete(claim), { once: true });
}

// The thread view an entry names (thread/address.js): `claim` opens it or puts it away
// on a traversal, as it reads the entry's record, and resolves to false, since it places
// nothing; `open` is the thread view standing open, the floating panel's or a margin
// card's, and the reader it is; `focusTarget` is a part of a thread, its drawing or its
// reply, wherever the thread's route drew it (thread/destination.js); and `name` names
// the open thread in a URL this document writes. `listShown` is the list the floating
// panel shows, which a thread opened from it stands over.
/** @type {{open: () => OpenThread | null, focusTarget: (id: string, part: "thread" | "reply") => Element | null} | null} */
let threadParts = null;
/** @type {(() => RecordList | null) | null} */
let listShown = null;
/** @type {ThreadClaim | null} */
let threadClaim = null;
/** @type {((key: NonNullable<ReturnType<typeof draftFocus>>) => unknown) | null} */
let draftReturn = null;

// The record of the entry this document arrived at by a reload, or by Back or Forward
// from another document (the Navigation API's `activation`), which history wrote as the
// user left it; null for a fresh visit, whose address alone says where to go.
/** @returns {EntryRecord | null} */
export function arrivalRecord() {
  const type = window.navigation.activation?.navigationType;
  if (type !== "reload" && type !== "traverse") return null;
  const record = /** @type {EntryRecord | undefined} */ (
    window.navigation.currentEntry?.getState()
  );
  return record ?? null;
}

// Return to an arrival's record once the page is presented, as a traversal within the
// document returns to its destination's: the page placed by its record, the thread or
// list the entry shows opened by the URL's claim (thread/address.js), then where the user
// was in it (`returnTo`).
/** @param {EntryRecord} record @param {ReturnType<typeof retainUserIntent>} intent */
export async function returnOnArrival(record, intent) {
  if (!intent()) return;
  if (record.page && placesPage(record.page)) restorePlace(record.page, null, intent);
  /** @type {unknown} */
  let work;
  intent.handoff(() => {
    work = threadClaim?.(new URL(location.href), record)?.();
  });
  await work;
  if (intent()) intent.handoff(() => returnTo(record));
}
let mounted = false;
/** @param {{followFragment: (url: URL) => TraversalHandler | null | undefined | false,
 * returnToFragment: (url: URL) => TraversalHandler | null | undefined,
 * thread: {claim: ThreadClaim, open: () => OpenThread | null,
 * focusTarget: (id: string, part: "thread" | "reply") => Element | null,
 * name: (url: URL) => URL}, list: () => RecordList | null,
 * draft: (key: NonNullable<ReturnType<typeof draftFocus>>) => unknown}} options */
export function mountHistory({
  followFragment,
  returnToFragment,
  thread,
  list,
  draft,
}) {
  if (mounted) return;
  mounted = true;
  threadParts = thread;
  nameThread = thread.name;
  threadClaim = thread.claim;
  listShown = list;
  draftReturn = draft;
  // A document the browser keeps no entries for, as a sample's sandboxed frame, whose
  // origin is opaque, has no entry to keep a record in.
  if (!window.navigation.currentEntry) return;
  // Leaving for another document, by a reload or a link out of the page, leaves the
  // entry too (the header).
  addEventListener("beforeunload", () => {
    if (anchoringIsReady())
      window.navigation.updateCurrentEntry({ state: readRecord() });
  });
  window.navigation.addEventListener("navigate", (event) => {
    if (!event.destination.sameDocument || !event.canIntercept) return;
    const url = new URL(event.destination.url);
    if (event.navigationType !== "replace")
      window.navigation.updateCurrentEntry({ state: leaving ?? readRecord() });
    if (event.navigationType === "traverse") {
      const record = /** @type {EntryRecord | undefined} */ (
        event.destination.getState()
      );
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
          if (!placed && record?.page && placesPage(record.page))
            restorePlace(record.page, null, mayReturn);
          else if (!placed) event.scroll();
          // The thread view opens or goes once the page stands where the entry left it,
          // so a card takes its side against the page the user returns to: opened
          // against the page they leave, it stood below its words and over them once
          // the page moved back. What it does is decided then too, from the views the
          // earlier steps left open: revealing the fragment can put away the panel's
          // view of the very thread the entry names.
          work = undefined;
          mayReturn.handoff(() => {
            work = thread.claim(url, record ?? null)?.();
          });
          await work;
          if (!mayReturn() || (!placed && !record)) return;
          if (record) mayReturn.handoff(() => returnTo(record));
          // Firefox and WebKit may apply the traversal after this placement and move
          // the page as they do (above). Once they have, the first block on screen goes
          // back to where the placement stood it. Firefox also drops focus to the body
          // as it applies the traversal (Firefox 160), so the node the return put the
          // user on takes it back, with its caret.
          const returned = record ? deepFocus() : null;
          const caret = readCaret(returned);
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
            mayReturn.handoff(() => focusDestination(returned, "return", { caret }));
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
