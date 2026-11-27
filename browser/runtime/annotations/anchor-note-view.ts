/* The accessible comment note for each authored block carrying comments.
 *
 * A painted range builds no accessibility node, so a block cannot say by itself that it
 * carries comments. Anchor controls supplies each commented block with its thread ids, and
 * this projection keeps one native button per block saying how many, which enters the
 * block's first thread. The button stands on the details shelf, and the block names it as
 * its details (features/details-shelf.js).
 *
 * The notes stand together, so each is named for the block it counts as a thread's quote
 * names it, cut to a spoken name's length ("2 comments on § paragraph · The first…"),
 * while it shows only the count, which the name begins with.
 *
 * A keyboard reaches a block's threads from the block itself (`c`, `t`) and through its
 * margin row. The note is a proxy for its block (control-faces.js, `proxy`): focus on it
 * rings the block and brings it into view (features/details-shelf.js).
 */
import { counted } from "../lib/words.js";
import { aimTargetAt } from "../readings/anchor-resolution.js";
import { shelve, unshelve } from "../features/details-shelf.js";
import { spokenSubject } from "../base/contribution-model.js";
import { offerAction } from "../lib/controls.js";
import { keeps, keepsText } from "../lib/keeps.js";
import type { createThreadDestinations } from "../records/thread/destination.js";
import type { anchorLabel } from "../records/thread/messages.js";

type CommentThreads = readonly [string, ...string[]];
export function createAnchorNoteProjection({
  openThread,
  labelAnchor,
}: {
  openThread: ReturnType<typeof createThreadDestinations>["openPageThread"];
  labelAnchor: typeof anchorLabel;
}) {
  // holder -> { note, firstThreadId }
  const claims = new Map<Element, ReturnType<typeof claim>>();

  function claim(firstThreadId: string) {
    const note = offerAction("proxy", "lf-mark-note");
    note.tabIndex = -1;
    const record = { note, firstThreadId };
    note.addEventListener(
      "click",
      () => void openThread(record.firstThreadId, { part: "thread" }),
    );
    return record;
  }

  function release(holder: Element, record: ReturnType<typeof claim>) {
    unshelve(holder, record.note);
    claims.delete(holder);
  }

  function present(notes: ReadonlyMap<Element, CommentThreads>) {
    // A block the page drew anew keeps its note, found by the thread it enters, so a
    // user on the note stays on it (features/details-shelf.js, `shelve`). One passage across
    // several blocks gives each a note entering the same thread, so the notes that
    // left wait in page order under that thread, and each new block takes the first.
    const left = new Map<string, [Element, ReturnType<typeof claim>][]>();
    for (const [holder, record] of claims)
      if (!notes.has(holder) || !holder.isConnected) {
        claims.delete(holder);
        const waiting = left.get(record.firstThreadId) ?? [];
        left.set(record.firstThreadId, [...waiting, [holder, record]]);
      }
    for (const [holder, threadIds] of notes) {
      let record = claims.get(holder);
      if (!record) {
        record = left.get(threadIds[0])?.shift()?.[1] ?? claim(threadIds[0]);
        claims.set(holder, record);
      }
      shelve(holder, record.note);
      record.firstThreadId = threadIds[0];
      const count = counted(threadIds.length, "comment");
      const anchor = aimTargetAt(holder)?.anchor;
      keepsText(record.note, count);
      keeps(
        record.note,
        "aria-label",
        anchor ? `${count} on ${spokenSubject(labelAnchor(anchor))}` : count,
      );
    }
    for (const [holder, record] of [...left.values()].flat()) release(holder, record);
  }

  function destroy() {
    for (const [holder, record] of claims) release(holder, record);
  }

  return { present, destroy };
}
