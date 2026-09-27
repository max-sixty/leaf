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
 * accessibility node; screen readers differ in how they announce it and whether they
 * offer a move to its target, and the note is otherwise found in the chrome. That
 * attribute is the only trace on the block. It is written through element reflection,
 * which reaches a note in the document from a block inside a widget's shadow tree, where
 * an id reference cannot. `aria-owns` would seat the note in the block's reading order,
 * but Chrome has no reflection for it, so it could name notes only for blocks in the
 * document's own tree; one relation serves every block instead. An authored
 * `aria-details` keeps its elements ahead of the note and is restored when the note goes.
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
    const record = { note, firstThreadId: null, authored: null };
    note.addEventListener("click", () =>
      openThread(record.firstThreadId, { focus: "thread" }),
    );
    if (!shelf) shelf = offer("div", "lf-mark-notes");
    if (!shelf.isConnected) chromeRoot.append(shelf);
    shelf.append(note);
    holders.set(note, holder);
    claims.set(holder, record);
    return record;
  }

  // Name the note on its block, keeping whatever the block's own `aria-details` names
  // ahead of it. Asked on every pass rather than once, because a revision that keeps the
  // block patches its attributes to the new source and takes the name off with it; the
  // source's value is then the one to keep and to restore.
  function name(holder, record) {
    if (holder.ariaDetailsElements?.includes(record.note)) return;
    record.authored = holder.getAttribute("aria-details");
    holder.ariaDetailsElements = [...(holder.ariaDetailsElements ?? []), record.note];
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
      name(holder, record);
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
