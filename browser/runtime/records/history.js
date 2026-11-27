// Compiled from history.ts by build/typescript.mjs; edit that file.
/* The entries this document adds to session history, and the traversals among them.
 *
 * Every same-document entry is a place the user can come Back to. `pushEntry` adds one;
 * `replaceEntry` renames the entry the user is on and keeps its `history.state`. A new
 * entry starts with no state of its own, since state belongs to the entry that set it.
 * Travel prepares the record of where the user is before revealing a destination and
 * commits it only after arrival succeeds. Failed or canceled routes add no return stop.
 *
 * Only a route the user's gesture began on the entry being left adds an entry: a
 * followed link, a walk's step, a list's row (features/anchor-travel.js,
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
 * The record holds the page, by what stood on screen (readings/reading-place.js,
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
 * place beside the page's landmark (dom/focus.js, `landAtReading`); a draft's box opens
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
 * (measured: Firefox drops one made at `pagehide` as the page reloads). A hidden page
 * may never see that moment, since a phone or a desktop's memory saver discards a
 * hidden tab without it, so the record is written as the page is hidden too, and
 * written again at whatever departure follows. The user arrives
 * at an entry by a traversal within the document, or by a reload or a traversal from
 * another document, and each returns them to its record the same way, as one
 * restoration under one intent, which every route it starts runs under
 * (`beginRestoration`): a newer one or a navigation away ends it, one taken while the
 * page still starts returns once the page has presented, and until it settles a
 * departure writes what it owes. Rejected: a map of live nodes and pixel offsets by
 * entry key, which a reload emptied, so Back after it had nothing to return to, and whose offsets
 * named content a revision had moved.
 *
 * A revision's reload is a reload, so it returns to this record too; its handoff
 * (features/version.js) adds only what history never puts back: each reading region's place,
 * the values typed, the words being written with their native editing session, the
 * comparison and the pointer. Both hold where the user was writing, and the handoff's
 * is the newer, since words typed through the reload move its caret (bootstrap.js,
 * `typeBack`). Focus on a control of the page's own is the handoff's to put back, with
 * its caret where the control has one; the record's return leaves focus there and
 * returns only the selection (`returnTo`). A draft's box stays the record's: its return
 * reopens the box and puts the user in it, and the handoff's restore, which runs after,
 * moves the caret to where the handoff has it (features/version.js, `restoreEditingContinuity`).
 * The two aren't one rule because that restore declines once another tab has rewritten
 * the draft, while the record's return, which doesn't check the draft, still puts the
 * user in the box, with the caret where the record had it. The record's thread opens where the user stands, moving
 * no scroller, so a card whose passage the revision hid opens in the floating panel
 * (thread/address.js, `claim`). The panel's hold of where the user stepped in from
 * (`readPlace`) reads the same page place, focus identity and thread reading, and stays
 * apart from this record: it is read as the user steps into the panel and used while
 * they stand there, in this document, so it keeps the node they left and its page
 * place, read before the step put away the card that drew it, where a record could
 * name only what the arriving document draws.
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
 * stays put while the browser scrolls. The view's reveal and travel read the page before
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
 * So every same-document traversal comes through here, through the Navigation API.
 * Where the entry's fragment names a place in another of the page's views, such as a
 * root tab set's, that view is revealed first (`mountHistory`'s `view`, views.js), and
 * the entry's record then returns the user to where they were in it. Travel takes the
 * traversal after that (`mountHistory`'s `returnToFragment`, features/anchor-travel.js)
 * where the entry's fragment still names a place the page doesn't show, such as a
 * widget's key whose part the widget no longer draws inside the view just
 * opened: the record was read over a page that has changed, so travel reveals
 * the place and lands on it. Any other traversal is
 * intercepted to restore its record, or the browser's saved offset
 * for an entry without one. Back and Forward restore that place after the
 * view is shown, so the next command reads the returned place from the browser.
 * A record is where the user was, never a reading of where they are now; a newer
 * gesture cancels a delayed return, and what it names that the page no longer draws
 * is not returned to.
 *
 * A fragment navigation, a followed `#id` link, is not a traversal: it adds its entry
 * and is a navigation step to the element it names. Travel claims it (`followFragment`) where the
 * fragment names an element of the page, and lands it through the browser's own
 * fragment placement rule once travel has cleared and revealed the way; any other fragment
 * keeps native landing. An entry this document writes through `pushEntry` or
 * `replaceEntry`, as travel and a switch between the page's views do, is not a fragment
 * navigation and is never claimed. */

import { pageRange, selectEnds, selectionBackward } from "../dom/native-selection.js";
import { setScroll } from "../dom/arrivals.js";
import {
  deepFocus,
  drawn,
  enteredInputCount,
  entryInputCount,
  focusDestination,
  readCaret,
  landAtReading,
} from "../dom/focus.js";

import { restrictUserIntent, retainUserIntent } from "../dom/user-intent.js";
import { placeOf } from "./current-target.js";
import { closestAcross, renderedUnder, upFrom } from "../lib/shadow-tree.js";
import { inChrome } from "../base/ui-marks.js";
import { presented } from "../dom/geometry.js";
import { unconcealedReadingRegions } from "../readings/reading-regions.js";
import {
  capturePlace,
  hasLandmark,
  rawOffsetFits,
  readingBlock,
  restorePlace,
} from "../readings/reading-place.js";
import {
  pageScroller,
  scrollGoal,
  stopBrowserScroll,
  stopGlide,
} from "../dom/scrolling.js";
import { drawnThreadId, THREAD, wholeThread } from "./thread/selectors.js";
import { readingIn, showReading } from "./thread/reply-landing.js";
import {
  anchorForRange,
  anchoringIsReady,
  resolveAnchor,
} from "../readings/anchor-resolution.js";
import { targetSegments } from "../readings/resolved-target.js";
import {
  authoredScope,
  blockAt,
  DATUM,
  findQuote,
  MESSAGE_BODY,
  messageReading,
  pageDocument,
  pageWords,
  passageIn,
  pointAt,
  readingHolding,
  runReading,
  segmentsIn,
  spanIn,
} from "../readings/passages.js";
import { focusByKey, focusKey } from "./carry.js";
import { draftFocus } from "./drafts.js";
import { nextRender } from "../lib/frame-pass.js";
import { afterPresentation } from "../readings/presentation.js";
import { pagePresented } from "../base/page-paint.js";
import { aborted } from "../base/abort.js";
import { reloadDocument } from "../transport/layer-client.js";

// The user's working place, read once as they step into the floating panel, whose
// place-keeping commands hand it back. `focus` is the node they had focused, when the
// reading comes after focus has left it. `thread` is the thread view that node stood
// in, which outlasts the view's drawing (`returnPlace`). Plain endpoints keep a removed
// passage from being silently retargeted by a live Range. pageRange shares the
// declared-shadow reading used for commenting; the selection's direction also keeps its
// working end.
export function readPlace(focus = deepFocus()) {
  const place = placeOf(focus);
  const selection = getSelection();
  const range = selection?.rangeCount ? pageRange(selection) : null;
  let ends = null;
  if (range) {
    ends = [
      [new WeakRef(range.startContainer), range.startOffset],
      [new WeakRef(range.endContainer), range.endOffset],
    ];
    if (selection && selectionBackward(selection, range)) ends.reverse();
  }
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
function returnSelection(ends) {
  const selection = getSelection();
  if (!selection) return;
  selection.removeAllRanges();
  if (ends?.[0] && ends[1]) selectEnds(ends[0], ends[1]);
}

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
// its entry comes back where the browser restores it. While a restoration still owes the
// user its record, that record is where they are (`beginRestoration`).
function readRecord() {
  if (restoring?.owes()) return restoring.record;
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
const unnamed = (part, open) =>
  part && "thread" in part && part.thread === open?.id
    ? { ...part, thread: null }
    : part;

// The page's selection: the passage a comment on its words would quote, or on its
// block's words for a caret or a run of spaces (readings/anchor-resolution.js, `anchorForRange`),
// found again by its words in whatever revision draws them; and each of its ends, anchor
// end first, as how far it stands from that passage's start in the reading of the page
// that holds it (readings/passages.js, `spanIn`, `pointAt`). The quote alone can't hold the ends:
// it trims the spaces at its edges and holds no caret, so a caret before a space came
// back after it. Words selected in Leaf's own interface are no passage of the page.
function readSelection() {
  const selection = getSelection();
  const range = selection?.rangeCount ? pageRange(selection) : null;
  if (!selection || !range) return null;
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
  const reading = passageReading(segments);
  const [base] = spanIn(reading, segments);
  const start = readingIndex(reading, range.startContainer, range.startOffset);
  const end = readingIndex(reading, range.endContainer, range.endOffset);
  if (start === null || end === null) return null;
  return { anchor, ends: directed([start - base, end - base]) };
}
// A selection inside one message of a thread, which the page's reading doesn't hold:
// the message, by its thread and its id, and the passage the selection is, in the
// reading of the message's body (readings/passages.js, `messageReading`, `passageIn`), with each
// end as how far it stands from that passage's start, as a page selection keeps its
// ends. The message's head, whose age changes as time passes, is no part of that
// reading, and a rewrite of the message finds the words again by the quote rules,
// never by an offset among copies (`messageEnds`).
function inMessage(turn, range, directed) {
  const drawing = closestAcross(turn, THREAD);
  const thread = drawing && drawnThreadId(wholeThread(drawing));
  const message = turn.getAttribute("data-lf-message");
  const body = authoredScope(range.startContainer);
  if (!thread || !message || !turn.contains(body) || !body.contains(range.endContainer))
    return null;
  const reading = messageReading(body);
  const start = readingIndex(reading, range.startContainer, range.startOffset);
  const end = readingIndex(reading, range.endContainer, range.endOffset);
  // A caret holds no words to find it again by.
  if (start === null || end === null || start === end) return null;
  const passage = passageIn(reading, Math.min(start, end), Math.max(start, end));
  if (!passage) return null;
  const { at, ...quoted } = passage;
  return { thread, message, ...quoted, ends: directed([start - at, end - at]) };
}
// The words of the block holding `node`, as a range.
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
function readingIndex(reading, node, offset) {
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

// Put the user back where a record says they were, once the views the entry names
// stand open and the page stands where the record places it: at the reading
// they had in the open thread's view, then on what focus was on (carry.js,
// `focusByKey`), or, where the page no longer draws it, at the reading place beside the
// page's landmark, unless focus was in the floating panel's list, which the address's
// claim has shown standing on its row (thread/address.js). The return settles once they
// are there, so a command acting on the returned place awaits it. Where the arrival's
// handoff puts focus back on a control of the page's own itself (`returnsFocus`
// false), focus and its caret are the handoff's, so the return leaves focus where the
// handoff put it and returns the selection only where no caret is the selection
// (features/version.js, `installArrival`).
async function returnTo(record, intent, returnsFocus = true) {
  const open = threadParts?.open() ?? null;
  const drawing = open && threadParts?.focusTarget(open.id, "thread");
  if (record.thread && drawing) showReading(drawing, record.thread);
  const key = record.focus;
  const drawingOf = (id) => threadParts?.focusTarget(id, "thread") ?? null;
  // A draft's box opens again where the user stands, by its owner's Resume writing
  // route, with the user on the box or in its words at their caret.
  if (key && "draft" in key) {
    await draftReturn?.(key, intent);
    return;
  }
  const thread = key?.thread === null ? (open?.id ?? null) : key?.thread;
  // Focus that puts the user somewhere: on a drawn element, not the page's body, whether
  // the record returns it or the handoff did, which finds nothing where the revision
  // dropped the control.
  const lands = (target) =>
    target !== null && target !== document.body && presented(target);
  const handed = deepFocus();
  const focus = !returnsFocus
    ? lands(handed)
      ? handed
      : null
    : key && thread !== null
      ? focusByKey({ ...key, thread }, drawingOf, lands)
      : null;
  // A field's caret is its whole selection, and clearing the document's would
  // collapse it.
  if (focus && key?.caret) return;
  if (!focus && !record.list) landAtReading();
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
function passageEnds({ anchor, ends }) {
  const segments = targetSegments(resolveAnchor(anchor));
  // Words the page draws, since a passage resolves through what a reader has shut too.
  if (!segments[0] || !segments.every(({ node }) => drawn(upFrom(node)))) return null;
  return endsFrom(passageReading(segments), segments, ends);
}

// The ends `ends` name from the start of the passage `segments` in `reading`.
function endsFrom(reading, segments, ends) {
  const [base] = spanIn(reading, segments);
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

// The ends a message selection names in the drawing of its thread: from the start of
// its passage, found in the message's body by the quote rules a comment is found by, a
// unique match in its context or its sole copy (readings/passages.js, `findQuote`); none where
// the message is gone or shut, or a rewrite took the words out or leaves no one copy.
function messageEnds({ message, quote, ends, ...context }, thread) {
  const drawing = thread ? threadParts?.focusTarget(thread, "thread") : null;
  const turn = drawing?.querySelector(`[data-lf-message="${CSS.escape(message)}"]`);
  const body = turn?.querySelector(MESSAGE_BODY);
  if (!body || !drawn(body)) return null;
  const reading = messageReading(body);
  const segments = findQuote(reading, quote, context);
  return segments[0] ? endsFrom(reading, segments, ends) : null;
}

// The reading a passage of the page is read in, the one its anchor is captured and
// found again in: its part's, or the run of words from the datum it starts in to the one
// it ends in, for a passage across data (readings/passages.js, `runReading`).
function passageReading([head, ...rest]) {
  const first = head && closestAcross(head.node, DATUM);
  const last = closestAcross((rest.at(-1) ?? head)?.node ?? null, DATUM);
  return first && last && first !== last
    ? runReading(first, last)
    : readingHolding(head?.node ?? pageDocument());
}

// Whether a record can place the page itself: a landmark it can find again, its start,
// or a raw offset read in this scroller at this width and revision (readings/reading-place.js).
const placesPage = (page) =>
  Boolean(page.start) || hasLandmark(page) || rawOffsetFits(page, pageScroller);

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

// Each entry this document writes names the thread view standing open as it is
// written (thread/address.js, `name`), so no URL a route, a widget or a waiting rename
// captured earlier carries a thread name the page no longer shows.
let nameThread = (url) => url;
const named = (url) => nameThread(new URL(url ?? location.href, location.href));

export function pushEntry(url, state = null) {
  write("pushState", state, named(url));
}

// A rename renames the entry the user is on, at `url`, or at its own address where
// `url` is absent. One asked for while a navigation is under way waits for it to end,
// since a history write aborts the navigation in Chromium and Firefox alike, and a
// rename is no step of the user's that should end one, as naming the view a traversal
// revealed would end that traversal before its place came back. It
// renames only the entry it was asked on: where a newer navigation has moved the user to
// another, it is dropped. Without `state`, the entry keeps its own, read when the rename
// is written. A rename that would change nothing writes nothing, and one the browser
// refuses over its rate limit, as Safari does by throwing past 100 in 30 seconds, is
// dropped, since the next write names the entry again.
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

/** Rename the entry the user is on to `url` and reload it as Leaf's own reload
 * (transport/layer-client.js, `reloadDocument`), without waiting for a navigation under way. */
export function reloadAt(url) {
  write("replaceState", history.state, named(url));
  reloadDocument();
}

// A route can reveal or hydrate before it knows whether arrival will succeed. Read
// where the user is now, before anything moves, and write it to the entry they leave
// only as the step is pushed, on success (`leaving`).
let leaving = null;
export function prepareEntry() {
  const record = readRecord();
  const sourceUrl = location.href;
  const sourceState = history.state;
  return (url) => {
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

// The view of the page a traversal's entry names (views.js, `entryView`): the handler
// that reveals it, or nothing where the entry names none or it already shows. A
// handler places the viewport itself unless it resolves to false, handing placement
// back to the entry's record (or the browser for an entry without one), as this one
// does. Travel follows it where the entry's fragment names a place the view doesn't
// show.
let entryView = null;

// The thread view an entry names (thread/address.js): `claim` opens it or puts it away
// on a traversal, as it reads the entry's record, and resolves to false, since it places
// nothing; `open` is the thread view standing open, the floating panel's or a margin
// card's, and the reader it is; `focusTarget` is a part of a thread, its drawing or its
// reply, wherever the thread's route drew it (thread/destination.js); and `name` names
// the open thread in a URL this document writes. `listShown` is the list the floating
// panel shows, which a thread opened from it stands over.
let threadParts = null;
let listShown = null;
let threadClaim = null;
let draftReturn = null;

// ---------- returning to an entry ----------
// One restoration at a time returns the user to the record of an entry they arrive at:
// the document's own arrival, by a reload or by Back or Forward from another document
// (`beginArrival`, `arrive`), or a traversal within the document (`mountHistory`). Each
// is one ordered operation under one intent, which its every step and every route it
// starts runs under: a newer restoration, or any navigation but this document's own
// rename, aborts it, as the platform aborts a traversal's own (`NavigateEvent.signal`),
// and the user's own input within the entry ends it, for a route that moves no focus
// as for one that does (`stands`; dom/focus.js, `entryInputCount`), and the intent it runs
// under counts that input alone. A step Back or Forward is no such input: every
// restoration begins once the document handles its traversals (`mountHistory`), so a
// later step is a navigation, which aborts it, and an earlier one brought the user to
// the entry it returns to. Nor is leaving the window, from which the user comes back
// to the same place. Until it settles, a departure, the hidden page's checkpoint or the
// handoff of a reload Leaf asked for writes the record it owes, rather than a reading
// of the page it is still putting back (`owes`, `readRecord`), the step that leaves the
// entry among them, and the document hands on the handoff such a reload brought as it
// came (features/version.js, `installArrival`). It settles once every piece of work it runs has
// (`run`), its fresh thread arrival and last fragment landing among them (leaf.js), so
// a navigation finds it to abort until the last has run, and keys held for it wait
// until then (`settled`, features/version.js `installArrival`).
let restoring = null;
function beginRestoration(record, intent, ended = null, since = entryInputCount()) {
  restoring?.abort();
  const controller = new AbortController();
  const signal = ended
    ? AbortSignal.any([ended, controller.signal])
    : controller.signal;
  const moved = () => entryInputCount() !== since;
  const stands = () => !signal.aborted && !moved();
  const settled = Promise.withResolvers();
  const restoration = {
    record,
    intent: restrictUserIntent(intent, stands),
    abort: () => {
      controller.abort();
      settle();
    },
    run: async (work) => {
      held += 1;
      try {
        await work();
      } finally {
        held -= 1;
        if (!held) settle();
      }
    },
    owes: () => restoring === restoration && Boolean(record) && !moved(),
    settled: settled.promise,
  };
  let held = 0;
  const settle = () => {
    if (restoring === restoration) restoring = null;
    settled.resolve();
  };
  restoring = restoration;
  return restoration;
}

// The document's arrival at the entry it stands on as the arrival begins: the
// restoration of the record that entry kept, where the document came by a reload or by
// Back or Forward from another document (the Navigation API's `activation`), and of
// none for a fresh visit, whose address alone says where to go, under the arrival's
// intent still. Its intent counts the user's inputs within that entry from the latest
// step to it, or from the document's start, as a document arrival's does
// (dom/user-intent.js; dom/focus.js, `enteredInputCount`).
export function beginArrival() {
  const entry = window.navigation.currentEntry;
  const type = window.navigation.activation?.navigationType;
  const record =
    type === "reload" || type === "traverse" ? (entry?.getState() ?? null) : null;
  const since = enteredInputCount();
  const intent = retainUserIntent({ count: entryInputCount, since });
  return beginRestoration(record, intent, null, since);
}
// The restoration under way, whose record a departure writes while it owes it.
export const pendingRestoration = () => restoring;

// The document's arrival run as one operation: `land`, the handoff's own landing
// (features/version.js, `installArrival`), returning to the record where it calls for it
// (`returnToRecord`), then settled.
export const arrive = (restoration, land) =>
  restoration.run(() =>
    land((returnsFocus) => returnToRecord(restoration, returnsFocus)),
  );

// Return to an arrival's record once the page has presented, as a traversal within the
// document returns to its destination's: the page placed by its record, the thread or
// list the entry shows opened by the URL's claim (thread/address.js), then where the user
// was in it (`returnTo`).
async function returnToRecord({ record, intent }, returnsFocus) {
  await afterPresentation(() => undefined);
  if (!record || !intent()) return;
  if (record.page && placesPage(record.page)) restorePlace(record.page, null, intent);
  await claimAndReturn(new URL(location.href), record, intent, returnsFocus);
}
// The thread view `url` names opened or put away by its claim (thread/address.js), then
// the user put back where `record` says they were (`returnTo`), under `intent`.
async function claimAndReturn(url, record, intent, returnsFocus) {
  let work;
  intent.handoff(() => {
    work = threadClaim?.(url, record, intent)?.();
  });
  await work;
  if (!record || !intent()) return;
  intent.handoff(() => {
    work = returnTo(record, intent, returnsFocus);
  });
  await work;
}
let mounted = false;
export function mountHistory({
  followFragment,
  returnToFragment,
  view,
  thread,
  list,
  draft,
}) {
  if (mounted) return;
  mounted = true;
  entryView = view;
  threadParts = thread;
  nameThread = thread.name;
  threadClaim = thread.claim;
  listShown = list;
  draftReturn = draft;
  // A document the browser keeps no entries for, as a sample's sandboxed frame, whose
  // origin is opaque, has no entry to keep a record in.
  if (!window.navigation.currentEntry) return;
  // Leaving for another document, by a reload or a link out of the page, leaves the
  // entry too, and hiding the page may be the last the page sees of it (the header).
  const keep = () => {
    if (anchoringIsReady())
      window.navigation.updateCurrentEntry({ state: readRecord() });
  };
  addEventListener("beforeunload", keep);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") keep();
  });
  window.navigation.addEventListener("navigate", (event) => {
    if (!event.destination.sameDocument || !event.canIntercept) return;
    const url = new URL(event.destination.url);
    if (event.navigationType !== "replace")
      window.navigation.updateCurrentEntry({ state: leaving ?? readRecord() });
    // Any navigation but this document's own rename ends the restoration under way.
    if (!writing || event.navigationType !== "replace") restoring?.abort();
    if (event.navigationType === "traverse") {
      const record = event.destination.getState();
      const restoration = beginRestoration(
        record ?? null,
        retainUserIntent({ count: entryInputCount }),
        event.signal,
      );
      const mayReturn = restoration.intent;
      const claim = entryView?.(url, mayReturn) ?? null;
      const applied = traversalApplied(event.signal);
      const traverse = async () => {
        // A traversal taken while the page still starts returns once it has presented.
        if (!pagePresented()) await afterPresentation(() => undefined);
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
        // The view the entry names is revealed first, so travel reads the place the
        // fragment names in the page that view leaves. Either one places the viewport
        // unless it resolves to false.
        let work;
        mayReturn.handoff(() => {
          work = claim?.();
        });
        let placed = Boolean(claim) && (await work) !== false;
        if (!mayReturn()) return;
        work = undefined;
        mayReturn.handoff(() => {
          work = returnToFragment(url, mayReturn)?.();
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
        await claimAndReturn(url, record ?? null, mayReturn);
        if (!mayReturn() || (!placed && !record)) return;
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
      };
      event.intercept({
        scroll: "manual",
        focusReset: "manual",
        handler: () => restoration.run(traverse),
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
function traversalApplied(signal) {
  const applied = new Promise((resolve) =>
    addEventListener("popstate", () => nextRender(() => resolve()), {
      once: true,
      signal,
    }),
  );
  return Promise.race([applied, aborted(signal)]);
}
