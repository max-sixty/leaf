/* The accessible comment note for each authored block carrying comments.
 *
 * A painted range builds no accessibility node, so a block cannot say by itself that it
 * carries comments. Anchor paint supplies each commented block with its thread ids, and
 * this projection keeps one native button per block saying how many, which enters the
 * block's first thread. The button stands on the details shelf, and the block names it as
 * its details (details-shelf.js).
 *
 * The notes stand together, so each is named for the block it counts as a thread's quote
 * names it, cut to a spoken name's length ("2 comments on § paragraph · The first…"),
 * while it shows only the count, which the name begins with.
 *
 * A keyboard reaches a block's threads from the block itself (`c`, `t`) and through its
 * margin row. Focus on the note shows it in the skip link's face (chrome.css).
 */
import { addressableAt } from "./anchor-resolution.js";
import { shelve, unshelve } from "./details-shelf.js";
import { spokenSubject } from "./contribution-model.js";
import { offer } from "./widget-elements.js";
import { keeps, keepsText } from "./keeps.js";

const label = (count) => `${count} comment${count === 1 ? "" : "s"}`;

export function createAnchorNoteProjection({ openThread, labelAnchor }) {
  // holder -> { note, firstThreadId }
  const claims = new Map();

  function claim() {
    const note = offer("button", "lf-skip lf-mark-note");
    note.tabIndex = -1;
    const record = { note, firstThreadId: null };
    note.addEventListener("click", () =>
      openThread(record.firstThreadId, { focus: "thread" }),
    );
    return record;
  }

  function release(holder, record) {
    unshelve(holder, record.note);
    claims.delete(holder);
  }

  function present(notes) {
    for (const [holder, record] of claims)
      if (!notes.has(holder) || !holder.isConnected) release(holder, record);
    for (const [holder, threadIds] of notes) {
      let record = claims.get(holder);
      if (!record) claims.set(holder, (record = claim()));
      shelve(holder, record.note);
      record.firstThreadId = threadIds[0];
      const count = label(threadIds.length);
      const on = addressableAt(holder)?.id;
      keepsText(record.note, count);
      keeps(
        record.note,
        "aria-label",
        on ? `${count} on ${spokenSubject(labelAnchor({ section: on }))}` : count,
      );
    }
  }

  function destroy() {
    for (const [holder, record] of claims) release(holder, record);
  }

  return { present, destroy };
}
