/* The accessible comment note for each authored block carrying comments.
 *
 * A painted range builds no accessibility node, so a block cannot say by itself that it
 * carries comments. Anchor controls supplies each commented block with its thread ids, and
 * this projection keeps one native button per block saying how many, which enters the
 * block's first thread. The button stands on the details shelf, and the block names it as
 * its details (details-shelf.js).
 *
 * The notes stand together, so each is named for the block it counts as a thread's quote
 * names it, cut to a spoken name's length ("2 comments on § paragraph · The first…"),
 * while it shows only the count, which the name begins with.
 *
 * A keyboard reaches a block's threads from the block itself (`c`, `t`) and through its
 * margin row. The note is a proxy for its block (control-faces.js, `proxy`): focus on it
 * rings the block and brings it into view (details-shelf.js).
 */
import { aimTargetAt } from "./anchor-resolution.js";
import { shelve, unshelve } from "./details-shelf.js";
import { spokenSubject } from "./contribution-model.js";
import { offerAction } from "./widget-elements.js";
import { keeps, keepsText } from "./keeps.js";

/** @param {number} count */
const label = (count) => `${count} comment${count === 1 ? "" : "s"}`;

/** @typedef {readonly [string, ...string[]]} CommentThreads */
/** @param {{openThread: ReturnType<typeof import("./thread/destination.js").createThreadDestinations>["openPageThread"],
 * labelAnchor: typeof import("./thread/messages.js").anchorLabel}} options */
export function createAnchorNoteProjection({ openThread, labelAnchor }) {
  // holder -> { note, firstThreadId }
  /** @type {Map<Element, ReturnType<typeof claim>>} */
  const claims = new Map();

  /** @param {string} firstThreadId */
  function claim(firstThreadId) {
    const note = offerAction("proxy", "lf-mark-note");
    note.tabIndex = -1;
    const record = { note, firstThreadId };
    note.addEventListener(
      "click",
      () => void openThread(record.firstThreadId, { part: "thread" }),
    );
    return record;
  }

  /** @param {Element} holder @param {ReturnType<typeof claim>} record */
  function release(holder, record) {
    unshelve(holder, record.note);
    claims.delete(holder);
  }

  /** @param {ReadonlyMap<Element, CommentThreads>} notes */
  function present(notes) {
    // A block the page drew anew keeps its note, found by the thread it enters, so a
    // user on the note stays on it (details-shelf.js, `shelve`).
    /** @type {Map<string, [Element, ReturnType<typeof claim>]>} */
    const left = new Map();
    for (const [holder, record] of claims)
      if (!notes.has(holder) || !holder.isConnected) {
        claims.delete(holder);
        left.set(record.firstThreadId, [holder, record]);
      }
    for (const [holder, threadIds] of notes) {
      let record = claims.get(holder);
      if (!record) {
        record = left.get(threadIds[0])?.[1] ?? claim(threadIds[0]);
        left.delete(threadIds[0]);
        claims.set(holder, record);
      }
      shelve(holder, record.note);
      record.firstThreadId = threadIds[0];
      const count = label(threadIds.length);
      const anchor = aimTargetAt(holder)?.anchor;
      keepsText(record.note, count);
      keeps(
        record.note,
        "aria-label",
        anchor ? `${count} on ${spokenSubject(labelAnchor(anchor))}` : count,
      );
    }
    for (const [holder, record] of left.values()) release(holder, record);
  }

  function destroy() {
    for (const [holder, record] of claims) release(holder, record);
  }

  return { present, destroy };
}
