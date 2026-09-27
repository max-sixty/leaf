/* The accessible comment note for each authored block carrying comments.
 *
 * A painted range builds no accessibility node, so a block cannot say by itself that it
 * carries comments. Anchor paint supplies each commented block with its thread ids, and
 * this projection keeps one native button per block saying how many, which enters the
 * block's first thread.
 *
 * The button stands in the chrome, never inside the block. An element added to authored
 * content changes which of the block's children is first, last, and only, so the page's
 * own structural rules would restyle and move it for as long as a comment stood
 * (assets/AGENTS.md, "Space and scrolling"). The block names its note as its details
 * instead, ARIA's relation for an annotation, which the browser exposes on the block's
 * accessibility node for a screen reader to announce and follow. That attribute is the
 * only trace on the block. It is written through element reflection,
 * which reaches a note in the document from a block inside a widget's shadow tree, where
 * an id reference cannot; `aria-owns`, which would seat the note in the block's reading
 * order, has no reflection in Chrome and so cannot. An authored `aria-details` keeps its
 * elements ahead of the note and is restored when the note goes.
 *
 * The note is no Tab stop: from the chrome it would come after the whole page, away from
 * the block it counts. A keyboard reaches a block's threads from the block itself (`c`,
 * `t`) and through its margin row. Focus on the note stands at its block
 * (standing-target.js), and shows it in the skip link's face (chrome.css).
 */
import { chromeRoot } from "./chrome.js";
import { declareSide } from "./standing-target.js";
import { keepsText, offer } from "./widget-elements.js";

const label = (count) => `${count} comment${count === 1 ? "" : "s"}`;

export function createAnchorNoteProjection({ openThread }) {
  // holder -> { note, firstThreadId, authored }; the note's holder, read the other way.
  const claims = new Map();
  const holders = new WeakMap();
  let shelf = null;

  declareSide((node) => holders.get(node.closest?.(".lf-mark-note")) ?? null);

  function claim(holder) {
    const note = offer("button", "lf-skip lf-mark-note");
    note.tabIndex = -1;
    const record = {
      note,
      firstThreadId: null,
      authored: holder.getAttribute("aria-details"),
    };
    note.addEventListener("click", () =>
      openThread(record.firstThreadId, { focus: "thread" }),
    );
    if (!shelf) shelf = offer("div", "lf-mark-notes");
    if (!shelf.isConnected) chromeRoot.append(shelf);
    shelf.append(note);
    holder.ariaDetailsElements = [...(holder.ariaDetailsElements ?? []), note];
    holders.set(note, holder);
    claims.set(holder, record);
    return record;
  }

  function release(holder, record) {
    if (record.authored === null) holder.removeAttribute("aria-details");
    else holder.setAttribute("aria-details", record.authored);
    record.note.remove();
    claims.delete(holder);
  }

  function present(notes) {
    for (const [holder, record] of claims)
      if (!notes.has(holder) || !holder.isConnected) release(holder, record);
    for (const [holder, threadIds] of notes) {
      const record = claims.get(holder) ?? claim(holder);
      record.firstThreadId = threadIds[0];
      keepsText(record.note, label(threadIds.length));
    }
  }

  function destroy() {
    for (const [holder, record] of claims) release(holder, record);
    shelf?.remove();
  }

  return { present, destroy };
}
