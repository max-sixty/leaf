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

   Placement is the one record of where each passage stands. Between readings the page's
   words can change under a passage, by a revision, a widget or any script, and what a
   quote's resolution depends on is in the page's index of quotes (passages.js,
   `trackQuotes`): every copy of each quote the threads name, placed or not, and the
   words a resolution read beside them to tell copies apart. After each change to the
   page's words, the index reads what changed off the readings before and after it and
   searches only there, so placement places again only the threads whose quotes it
   says changed (`quotesChanged`): words moved, a copy gone, a second copy anywhere, or
   lost words put back. A thread is placed again too where a change wrote or took out
   the text its passage stands in, whose live ranges the DOM moved however the page then
   reads. Each is placed again, kept, or found no longer to stand (`settle`). Those who
   draw from it hear which threads it placed again (`hearPlaced`), as the anchor paint
   paints them and finds the pointer in them, so they read no change to the page
   themselves. A change elsewhere, as a counter a widget redraws each frame, places no
   thread again. */
import { anchoringIsReady, resolveAnchor } from "./anchor-resolution.js";
import { resolvedInMessage, targetElement } from "./resolved-target.js";
import {
  hearPageWords,
  inChrome,
  quotesChanged,
  rangeOf,
  trackQuotes,
} from "./passages.js";
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
/** @param {Placement | undefined} a @param {Placement | undefined} b */
const samePlacement = (a, b) =>
  a?.kind === b?.kind &&
  (a?.kind !== "passage" ||
    b?.kind !== "passage" ||
    (a.ranges === b.ranges && sameSegments(a.segments, b.segments))) &&
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

export function createAnchorPlacement() {
  /** @type {Map<string, Placement>} */
  const placed = new Map();
  const version = signal(0);
  /** @type {ReturnType<typeof resolveAnchor>} */
  let pendingPlaced = null;
  /** @type {Map<string, Thread>} */
  let names = new Map();
  // The threads the last reading placed: all of them, by id and by each quote their
  // anchors name; for each text node a placed passage's segment stands in, its threads;
  // the threads whose text nodes a change wrote or took out, not yet placed again; and
  // those who hear which threads were.
  /** @type {readonly Thread[]} */
  let threads = [];
  /** @type {Map<string, Thread>} */
  let byId = new Map();
  /** @type {Map<string, Set<string>>} */
  let byQuote = new Map();
  /** @type {Map<Node, Set<string>>} */
  const inNode = new Map();
  /** @type {Set<string>} */
  const rewritten = new Set();
  /** @type {Set<(ids: readonly string[]) => void>} */
  const hearers = new Set();
  /** @param {string} id @param {Placement | undefined} placement @param {boolean} on */
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
  // Any change to the page's words may have moved a quote's words, put a second copy of
  // them anywhere, or put back words a quote lost, so each is settled after the script
  // that made it, if anything is placed by quote.
  hearPageWords(({ written }) => {
    for (const node of written)
      for (const id of inNode.get(node) ?? []) rewritten.add(id);
    if (byQuote.size || rewritten.size) afterScript(settle);
  });

  // A thread's placement, as its anchor resolves now: in the message holding the element
  // it names where the page doesn't hold it, and over its passage the ranges `was` had
  // where they still stand.
  /** @param {Thread & {anchor: Anchor}} thread @param {Placement | undefined} was
   * @returns {Placement | undefined} */
  function place(thread, was) {
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
      point: null,
      pointRow: null,
      pointWords: null,
    });
  }

  /** @param {{threads: readonly Thread[], draft: ThreadDraft, actionAnchor: Anchor | null}} options */
  function read({ threads: all, draft, actionAnchor }) {
    if (!anchoringIsReady()) return null;
    const before = new Map(placed);
    placed.clear();
    // Names for the threads this read placed, so `placedAt` answers from the same
    // reading as `placed` until the next read, not from a later publication.
    names = threadNames(all);
    threads = all;
    byId = new Map(all.map((thread) => [thread.id, thread]));
    byQuote = new Map();
    for (const { id, anchor } of all)
      if (anchor?.quote) {
        const ids = byQuote.get(anchor.quote) ?? new Set();
        byQuote.set(anchor.quote, ids.add(id));
      }
    trackQuotes(byQuote.keys());
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
    const resolvedDraft =
      draft.open && draft.anchor ? resolveAnchor(draft.anchor) : null;
    pendingPlaced = resolvedDraft;
    const active = draft.open ? null : actionAnchor;
    const action = active && !active.quote ? resolveAnchor(active) : null;
    // This reading placed every anchor, those changes touched before it included.
    quotesChanged();
    rewritten.clear();
    if (
      before.size !== placed.size ||
      [...placed].some(([id, placement]) => !samePlacement(before.get(id), placement))
    )
      tick(version);
    return { readings, draft: { ...draft, resolved: resolvedDraft }, action };
  }
  // Place again the threads changes to the page's words touched, after the script that
  // made them, or at once where something reads them first (the hit test): those whose
  // quote's copies, or the words beside them its resolution read, changed (passages.js,
  // `quotesChanged`), placed or not, and those whose text nodes a change wrote or took
  // out. Each is placed again, kept where it stands as it stood, or no longer placed;
  // those who hear hear which threads changed.
  function settle() {
    if (!anchoringIsReady()) return;
    const ids = new Set(rewritten);
    rewritten.clear();
    for (const quote of quotesChanged())
      for (const id of byQuote.get(quote) ?? []) ids.add(id);
    /** @type {string[]} */
    const changed = [];
    for (const id of ids) {
      const thread = byId.get(id);
      if (!thread?.anchor) continue;
      const was = placed.get(id);
      note(id, was, false);
      const placement = place(/** @type {Thread & {anchor: Anchor}} */ (thread), was);
      if (placement) placed.set(id, placement);
      else placed.delete(id);
      note(id, placement, true);
      if (!samePlacement(was, placement)) changed.push(id);
    }
    if (!changed.length) return;
    tick(version);
    for (const hear of hearers) hear(changed);
  }
  return Object.freeze({
    read,
    settle,
    /** @param {(ids: readonly string[]) => void} hear */
    hearPlaced: (hear) => {
      hearers.add(hear);
      return () => void hearers.delete(hear);
    },
    placedAt: (/** @type {string | null | undefined} */ id) => {
      version.value;
      return id == null ? undefined : placed.get(names.get(id)?.id ?? id);
    },
    pendingAt: () => pendingPlaced,
  });
}
