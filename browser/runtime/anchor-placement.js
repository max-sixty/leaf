/* Current document targets for conversations and mechanical composition.

   Each read resolves durable anchors and pointed rows before selected presentation:
   initial admission and the final cohort move share this directory. Surface admission,
   inventory, current location and travel consume it;
   decoration consumes its resolved targets and never supplies their existence. These
   nodes and records are mechanical readings, outside the application snapshot.

   An anchor on an element an agent sent in a message, which the page itself doesn't
   hold, stands in that message, and its placement names it (`message`). While no reader
   draws the message, that is all it has (`resolvedInMessage`); while the floating panel
   draws it in its view of the message's thread, it keeps the element's reading too, so
   the element is marked there. `placedAt` tracks changes to resolved placements for
   views that read them while drawing; a source replacement can change a quote's
   status without changing its thread.

   Placement is the one record of where each passage stands, and no read of it is older
   than the page: every read settles first (`settle`), taking the changes the page's
   watcher holds undelivered, so a read in the task that made a change reads after it.
   What a quote's resolution reads, and how a change to each reaches settle:
   - the page's reading, its words, the edges and fences between them, the order its
     trees are read in, and each word's block: the page's index of quotes (passages.js,
     `trackQuotes`) keeps every copy of each quote the threads name, placed or not, and
     the words a resolution read beside a copy to tell copies apart, and compares the
     reading it last read with the page's now, however many changes came between,
     searching only where they differ, so placement places again only the threads whose
     quotes it says changed (`quotesChanged`): words moved, a copy gone, a second copy
     anywhere, or lost words put back. Registry vocabulary and settled slots change the
     reading through the same door. A quote in a datum is found in the datum's words
     alone, and changes, as the index says too, once those words do, so a page whose
     threads all quote data never reads its words whole;
   - the text nodes a change wrote or took out, whose live ranges the DOM moved and
     which may have moved into or out of a section at the same place in the reading:
     the index counts them changed wherever they stand;
   - the section an anchor names, found by its id among the page's elements and declared
     shadow trees, and which section holds each copy: the watcher reports the ids that
     came or went and the elements whose own id changed, and placement places again the
     threads naming those ids and those standing under those elements;
   - the thread's messages and the draft's anchor: application state, which a
     presentation reads (`read`);
   - for a quote in a datum, the datum's source, identity and revision attributes and
     whether its widget reported a draw: those reach placement only through the
     presentation that follows a widget's draw.
   A change that wrote or took out the text a placed passage stands in is settled after
   its script as well, since no reader draws the page's marks: the browser paints their
   live ranges, which the DOM moved. Those who draw from placement hear which threads it
   placed again (`hearPlaced`), as the anchor paint paints them and finds the pointer in
   them, so they read no change to the page themselves. A change elsewhere, as a counter
   a widget redraws each frame, places no thread again, and reads the page again only
   once something asks. */
import { anchoringIsReady, resolveAnchor } from "./anchor-resolution.js";
import { resolvedInMessage, targetElement } from "./resolved-target.js";
import {
  catchUpWords,
  hearPageWords,
  inChrome,
  quotesChanged,
  rangeOf,
  trackQuotes,
} from "./passages.js";
import { under } from "./shadow-tree.js";
import { afterScript } from "./rendering.js";
import { placePoints } from "./pointed-place.js";
import { threadKey, threadNames } from "./thread/model.js";
import { messageHolding } from "./thread/messages.js";
import { signal } from "/runtime/framework.js";
import { tick } from "./version-signal.js";

/** @typedef {import("../types/domain.js").Anchor} Anchor */
/** @typedef {ReturnType<typeof import("./thread/state.js").allThreads>[number]} Thread */
/** @typedef {import("../types/contract.js").CompleteUnion<import("./resolved-target.js").ResolvedTarget & {message?: string}>} ResolvedTarget */
/** @typedef {ResolvedTarget & {messageTarget: ReturnType<typeof messageHolding>,
 * point: Element | null, pointRow: string | null, pointWords: string | null}} Placement */
/** @typedef {{open: boolean, anchor: Anchor | null, about: string | null,
 * drawing: import("./composing/drawing-record.js").DraftDrawing | null}} ThreadDraft */
// Whether two readings of a passage stand in the same text, segment by segment: a
// revision or a script that writes words ahead of it keeps its ranges, which move with
// the words, but not where it stands.
/** @param {readonly import("./passages.js").Segment[]} a @param {readonly import("./passages.js").Segment[]} b */
const sameSegments = (a, b) =>
  a.length === b.length &&
  a.every((segment, at) => {
    const other = b[at];
    return (
      other !== undefined &&
      segment.node === other.node &&
      segment.start === other.start &&
      segment.end === other.end
    );
  });
/** @param {Partial<Placement> | undefined} a @param {Partial<Placement> | undefined} b */
const samePlacement = (a, b) =>
  a?.kind === b?.kind &&
  (a?.kind !== "passage" ||
    b?.kind !== "passage" ||
    (a.ranges === b.ranges && sameSegments(a.segments ?? [], b.segments ?? []))) &&
  a?.status === b?.status &&
  a?.exact === b?.exact &&
  a?.datumElement === b?.datumElement &&
  a?.element === b?.element &&
  a?.place === b?.place &&
  a?.surface === b?.surface &&
  a?.message === b?.message &&
  a?.point === b?.point &&
  a?.pointRow === b?.pointRow &&
  a?.pointWords === b?.pointWords &&
  a?.messageTarget?.element === b?.messageTarget?.element;

// The message of these threads that keeps the element an anchor names, if any. An anchor
// captured detached names no passage the user selected, so finding its element's message
// identifies nothing and it stays detached.
/** @param {Anchor} anchor @param {readonly Thread[]} threads */
function heldIn(anchor, threads) {
  const held =
    anchor.section && !anchor.detached ? messageHolding(anchor.section) : null;
  return held &&
    threads.some((thread) => thread.msgs.some(({ id }) => id === held.message))
    ? held
    : null;
}

// A range over each of a passage's segments, which the anchor paint paints: the last
// reading's own where they still stand where this reading resolved the passage, so a
// reading that moves nothing keeps the ranges the anchor paint painted and indexed.
/** @param {Placement | undefined} was @param {readonly import("./passages.js").Segment[]} segments */
function liveRanges(was, segments) {
  const ranges = was?.kind === "passage" ? was.ranges : undefined;
  const stand =
    ranges?.length === segments.length &&
    ranges.every((range, at) => {
      const segment = segments[at];
      return (
        segment !== undefined &&
        range.startContainer === segment.node &&
        range.startOffset === segment.start &&
        range.endContainer === segment.node &&
        range.endOffset === segment.end
      );
    });
  return stand && ranges ? ranges : segments.map((segment) => rangeOf([segment]));
}

// The key the draft's anchor is kept under beside the threads', which no thread's id is.
const DRAFT = "\u0000draft";
/** @typedef {{threads: readonly string[], pending: boolean}} Placed */

export function createAnchorPlacement() {
  /** @type {Map<string, Placement>} */
  const placed = new Map();
  const version = signal(0);
  /** @type {ReturnType<typeof resolveAnchor>} */
  let pendingPlaced = null;
  /** @type {Anchor | null} */
  let pendingAnchor = null;
  /** @type {Map<string, Thread>} */
  let names = new Map();
  // The threads the last reading placed: all of them, by id, by each quote their anchors
  // name and by each section, the draft's anchor among them (`DRAFT`); for each text
  // node a placed passage's segment stands in, its threads; whether the page's words or
  // ids changed since placement last read them (`stale`), and which ids and which
  // elements' own ids; the threads placed again whose hearers are still to hear it; and
  // those who hear which threads were.
  /** @type {readonly Thread[]} */
  let threads = [];
  /** @type {Map<string, Thread>} */
  let byId = new Map();
  /** @type {Map<string, Set<string>>} */
  let byQuote = new Map();
  /** @type {Map<string, Set<string>>} */
  let bySection = new Map();
  /** @type {Map<Node, Set<string>>} */
  const inNode = new Map();
  let stale = false;
  // The version of the page's index of quotes placement last read changes up to.
  let seen = 0;
  /** @type {Set<string>} */
  const renamedIds = new Set();
  /** @type {Set<Element>} */
  const renamedElements = new Set();
  /** @type {Set<string>} */
  const unheard = new Set();
  /** @type {Set<(placed: Placed) => void>} */
  const hearers = new Set();
  /** @param {string} id @param {ResolvedTarget | null | undefined} placement @param {boolean} on */
  const note = (id, placement, on) => {
    if (placement?.kind !== "passage") return;
    for (const { node } of placement.segments) {
      const ids = inNode.get(node) ?? new Set();
      if (on) ids.add(id);
      else ids.delete(id);
      if (ids.size) inNode.set(node, ids);
      else inNode.delete(node);
    }
  };
  /** @param {Map<string, Set<string>>} map @param {string} key @param {string} id */
  const file = (map, key, id) => map.set(key, (map.get(key) ?? new Set()).add(id));
  // Any change to the page's words may have moved a quote's words, put a second copy of
  // them anywhere, or put back words a quote lost, and a change to the page's ids may
  // have moved a section, so placement is stale until it settles, which every read of
  // it does first (`placedAt`, `pendingAt`, the hit test, a presentation). Changes then
  // cost one comparison of the readings however many come first, as a counter redrawn
  // each frame does. A change that wrote or took out the text a placed passage stands in
  // is settled after its script too, since no reader draws the page's marks: the
  // browser paints their live ranges, which the DOM has moved, so the marks no longer
  // show where the passage is until it is placed again.
  hearPageWords(({ written, ids, renamed }) => {
    for (const id of ids) renamedIds.add(id);
    for (const element of renamed) renamedElements.add(element);
    stale ||= byQuote.size > 0 || bySection.size > 0;
    if ([...written].some((node) => inNode.has(node))) afterScript(settle);
  });

  // A thread's placement, as its anchor resolves now: in the message holding the element
  // it names where the page doesn't hold it, and over its passage the ranges `was` had
  // where they still stand; a pointed row (`placePoints`) is a presentation's to give.
  /** @param {Thread & {anchor: Anchor}} thread @param {Placement | undefined} was
   * @param {boolean} [keepsPoint] @returns {Placement | undefined} */
  function place(thread, was, keepsPoint = false) {
    const found = resolveAnchor(thread.anchor);
    const held =
      found && !inChrome(found.place) ? null : heldIn(thread.anchor, threads);
    const resolved = !held
      ? found
      : found
        ? Object.assign(found, { message: held.message })
        : resolvedInMessage(held);
    if (!resolved) return undefined;
    if (resolved.kind === "passage")
      resolved.ranges = liveRanges(was, resolved.segments);
    return Object.assign(resolved, {
      messageTarget: held,
      point: (keepsPoint && was?.point) || null,
      pointRow: (keepsPoint && was?.pointRow) || null,
      pointWords: (keepsPoint && was?.pointWords) || null,
    });
  }

  /** @param {{threads: readonly Thread[], draft: ThreadDraft, actionAnchor: Anchor | null}} options */
  function read({ threads: all, draft, actionAnchor }) {
    if (!anchoringIsReady()) return null;
    catchUpWords();
    const before = new Map(placed);
    placed.clear();
    // Names for the threads this read placed, so `placedAt` answers from the same
    // reading as `placed` until the next read, not from a later publication.
    names = threadNames(all);
    threads = all;
    byId = new Map(all.map((thread) => [thread.id, thread]));
    byQuote = new Map();
    bySection = new Map();
    pendingAnchor = draft.open ? draft.anchor : null;
    /** @type {Set<string>} */
    const inWhole = new Set();
    for (const { id, anchor } of [...all, { id: DRAFT, anchor: pendingAnchor }]) {
      if (anchor?.quote) file(byQuote, anchor.quote, id);
      if (anchor?.quote && !anchor.datum && !anchor.visual) inWhole.add(anchor.quote);
      if (anchor?.section) file(bySection, anchor.section, id);
    }
    trackQuotes(inWhole);
    inNode.clear();
    const readings = [];
    const pointable = [];
    for (const thread of all) {
      if (!thread.anchor) continue;
      const placement = place(
        /** @type {Thread & {anchor: Anchor}} */ (thread),
        before.get(thread.id),
      );
      if (!placement) continue;
      const target = targetElement(placement) ?? placement.place;
      placed.set(thread.id, placement);
      note(thread.id, placement, true);
      readings.push({ thread, placement });
      if (!thread.resolved && !thread.anchor.quote && !thread.anchor.visual && target)
        pointable.push({ id: thread.id, key: threadKey(thread), target, placement });
    }
    const pointed = placePoints(pointable, new Set(all.map(threadKey)));
    for (const { placement, key } of pointable) {
      const point = pointed.get(key);
      if (point)
        Object.assign(placement, {
          point: point.element,
          pointRow: point.row,
          pointWords: point.words,
        });
    }
    const resolvedDraft = pendingAnchor ? resolveAnchor(pendingAnchor) : null;
    pendingPlaced = resolvedDraft;
    note(DRAFT, resolvedDraft, true);
    const active = draft.open ? null : actionAnchor;
    const action = active && !active.quote ? resolveAnchor(active) : null;
    // This reading placed every anchor, those changes touched before it included.
    seen = quotesChanged(seen).version;
    renamedIds.clear();
    renamedElements.clear();
    stale = false;
    if (
      before.size !== placed.size ||
      [...placed].some(([id, placement]) => !samePlacement(before.get(id), placement))
    )
      tick(version);
    return { readings, draft: { ...draft, resolved: resolvedDraft }, action };
  }
  // Bring placement to the page as it is now, the changes the watcher hasn't delivered
  // yet included (passages.js, `catchUpWords`), placing again the threads they touched:
  // those whose quote's copies, or the words beside them its resolution read, changed
  // (passages.js, `quotesChanged`), placed or not, and those whose section's id came or
  // went, or that stand under an element whose own id changed. Each is placed again,
  // kept where it stands as it stood, or no longer placed, and the draft is resolved
  // again. Those who hear hear which threads changed: at once, where the reader is the
  // hit test, which reads the marks they paint next; after the script, where the reader
  // is a view reading placement as it draws (`placedAt`), so a draw changes nothing
  // another draw has read.
  /** @param {boolean} [heardNow] */
  function settle(heardNow = true) {
    catchUpWords();
    if (stale && anchoringIsReady()) {
      stale = false;
      /** @type {Set<string>} */
      const ids = new Set();
      const changed = quotesChanged(seen);
      seen = changed.version;
      for (const quote of changed.quotes)
        for (const id of byQuote.get(quote) ?? []) ids.add(id);
      for (const name of renamedIds)
        for (const id of bySection.get(name) ?? []) ids.add(id);
      for (const element of renamedElements)
        for (const [node, at] of inNode)
          if (under(node, element)) for (const id of at) ids.add(id);
      renamedIds.clear();
      renamedElements.clear();
      for (const id of ids) {
        if (id === DRAFT) {
          const was = pendingPlaced;
          note(DRAFT, was, false);
          pendingPlaced = pendingAnchor ? resolveAnchor(pendingAnchor) : null;
          note(DRAFT, pendingPlaced, true);
          if (!samePlacement(was ?? undefined, pendingPlaced ?? undefined))
            unheard.add(DRAFT);
          continue;
        }
        const thread = byId.get(id);
        if (!thread?.anchor) continue;
        const was = placed.get(id);
        note(id, was, false);
        const placement = place(
          /** @type {Thread & {anchor: Anchor}} */ (thread),
          was,
          !thread.anchor.quote,
        );
        if (placement) placed.set(id, placement);
        else placed.delete(id);
        note(id, placement, true);
        if (!samePlacement(was, placement)) unheard.add(id);
      }
      if (unheard.size && !heardNow) afterScript(tell);
    }
    if (heardNow) tell();
  }
  function tell() {
    if (!unheard.size) return;
    const pending = unheard.delete(DRAFT);
    const change = { threads: [...unheard], pending };
    unheard.clear();
    tick(version);
    for (const hear of hearers) hear(change);
  }
  return Object.freeze({
    read,
    settle,
    /** @param {(placed: Placed) => void} hear */
    hearPlaced: (hear) => {
      hearers.add(hear);
      return () => void hearers.delete(hear);
    },
    placedAt: (/** @type {string | null | undefined} */ id) => {
      settle(false);
      version.value;
      return id == null ? undefined : placed.get(names.get(id)?.id ?? id);
    },
    pendingAt: () => {
      settle(false);
      return pendingPlaced;
    },
  });
}
