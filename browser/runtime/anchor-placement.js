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
   words can change under a passage, by a revision, a widget or any script, and the
   page-words watcher says which text each change touched (passages.js,
   `hearPageWords`): placement reads again only the anchors whose segments stand in text
   it wrote or took away, or whose passage runs on past text put in after them, and
   places each again, keeps it, or finds it no longer stands (`settle`). Those who draw
   from it hear which threads it placed again (`hearPlaced`), as the anchor paint
   paints them and finds the pointer in them, so they read no change to the page
   themselves. A change elsewhere, as a counter a widget redraws each frame, reads no
   anchor again. */
import { anchoringIsReady, resolveAnchor } from "./anchor-resolution.js";
import { resolvedInMessage, targetElement } from "./resolved-target.js";
import { hearPageWords, inChrome, pageReadingVersion, rangeOf } from "./passages.js";
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
  // The threads the last reading placed, by id; for each text node a placed passage's
  // segment stands in, its threads, and the threads whose passage runs on past it; the
  // threads a change to the page's words touched, not yet placed again; and those who
  // hear which threads were.
  /** @type {Map<string, Thread>} */
  let byId = new Map();
  /** @type {Map<Node, Set<string>>} */
  const inNode = new Map();
  /** @type {Map<Node, Set<string>>} */
  const runsOn = new Map();
  /** @type {Set<string>} */
  const touched = new Set();
  /** @type {Set<(ids: readonly string[]) => void>} */
  const hearers = new Set();
  /** @param {Map<Node, Set<string>>} map @param {Node} node @param {string} id @param {boolean} on */
  const mark = (map, node, id, on) => {
    const ids = map.get(node) ?? new Set();
    if (on) ids.add(id);
    else ids.delete(id);
    if (ids.size) map.set(node, ids);
    else map.delete(node);
  };
  /** @param {string} id @param {Placement | undefined} placement @param {boolean} on */
  const note = (id, placement, on) => {
    if (placement?.kind !== "passage") return;
    placement.segments.forEach((segment, at) => {
      mark(inNode, segment.node, id, on);
      if (at < placement.segments.length - 1) mark(runsOn, segment.node, id, on);
    });
  };
  hearPageWords(({ written, added }) => {
    for (const node of written)
      for (const id of inNode.get(node) ?? []) touched.add(id);
    for (const node of added) {
      const walker = document.createTreeWalker(
        node.getRootNode(),
        NodeFilter.SHOW_TEXT,
      );
      walker.currentNode = node;
      const before = walker.previousNode();
      for (const id of (before && runsOn.get(before)) ?? []) touched.add(id);
    }
    if (touched.size) afterScript(settle);
  });

  /** @param {{threads: readonly Thread[], draft: ThreadDraft, actionAnchor: Anchor | null}} options */
  function read({ threads, draft, actionAnchor }) {
    if (!anchoringIsReady()) return null;
    const before = new Map(placed);
    placed.clear();
    // Names for the threads this read placed, so `placedAt` answers from the same
    // reading as `placed` until the next read, not from a later publication.
    names = threadNames(threads);
    byId = new Map(threads.map((thread) => [thread.id, thread]));
    inNode.clear();
    runsOn.clear();
    const readings = [];
    const pointable = [];
    for (const thread of threads) {
      if (!thread.anchor) continue;
      const found = resolveAnchor(thread.anchor);
      const held =
        found && !inChrome(found.place) ? null : heldIn(thread.anchor, threads);
      const resolved = !held
        ? found
        : found
          ? Object.assign(found, { message: held.message })
          : resolvedInMessage(held);
      if (!resolved) continue;
      if (resolved.kind === "passage")
        resolved.ranges = liveRanges(before.get(thread.id), resolved.segments);
      const target = targetElement(resolved) ?? resolved.place;
      const placement = Object.assign(resolved, {
        messageTarget: held,
        point: null,
        pointRow: null,
        pointWords: null,
      });
      placed.set(thread.id, placement);
      note(thread.id, placement, true);
      readings.push({ thread, placement });
      if (!thread.resolved && !thread.anchor.quote && !thread.anchor.visual && target)
        pointable.push({ id: thread.id, key: threadKey(thread), target, placement });
    }
    const pointed = placePoints(pointable, new Set(threads.map(threadKey)));
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
    touched.clear();
    if (
      before.size !== placed.size ||
      [...placed].some(([id, placement]) => !samePlacement(before.get(id), placement))
    )
      tick(version);
    return { readings, draft: { ...draft, resolved: resolvedDraft }, action };
  }
  // Read again the anchors changes to the page's words touched, after the script that
  // made them, or at once where something reads them first (the hit test): each placed
  // again, kept where it stands as it stood, or no longer placed where it no longer
  // resolves; those who hear hear which threads changed.
  function settle() {
    pageReadingVersion();
    if (!touched.size || !anchoringIsReady()) return;
    const ids = [...touched];
    touched.clear();
    /** @type {string[]} */
    const changed = [];
    for (const id of ids) {
      const was = placed.get(id);
      const thread = byId.get(id);
      if (!was || !thread?.anchor) continue;
      note(id, was, false);
      const found = resolveAnchor(thread.anchor);
      if (!found) {
        placed.delete(id);
        changed.push(id);
        continue;
      }
      if (found.kind === "passage") found.ranges = liveRanges(was, found.segments);
      const placement = Object.assign(found, {
        messageTarget: was.messageTarget,
        point: was.point,
        pointRow: was.pointRow,
        pointWords: was.pointWords,
      });
      placed.set(id, placement);
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
