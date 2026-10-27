/* Natural thread layout, with the room a publication removes held for the reply.

   Transcript, quote, response and the reply editor size themselves through CSS. A
   semantic presentation preserves the visible reply's position by converting the room
   it removed into a spacer; later content consumes that spacer, and it goes once the
   reply leaves sight or the thread closes. Local disclosures and native edits take no
   snapshot, so returning to a collapsed shape is ordinary layout. The boxes a
   presentation changes itself are measured at its boundary, so their own height change
   does not become passive space: a message rewrite the user has open, and a message
   leaving the thread, as a reply the log refuses does, which gives its room back as it
   folds away (transcript.js).

   The editor holds no room of its own. Words a refused send hands back, and a draft
   typed in another tab, grow it as typing does, in a card as in the floating panel
   (skills/leaf/references/interface-principles.md, "Stability is owed to the common path"; the user's choice, 25
   October 2026), over holding the room for returned and synced words, where the
   editor kept its height from before Send and the spacer kept the refused turn's room
   through its fold, so the card held still while a gap stood above the box, and a
   mirrored draft stayed in the box of the last native edit, clipped mid-glyph. */
import { growthIsSeen, whenNone } from "../geometry.js";
import { layoutPx } from "../keeps.js";
import { placeKeeper } from "../user-place.js";
import { scrollerFor } from "../reading-regions.js";
import { offFlowSurfaceOf } from "../off-flow.js";

// The room a box takes in its flow, its margins included; none once it has gone.
const room = (node) => {
  if (!node.isConnected) return 0;
  const { marginBlockStart, marginBlockEnd } = getComputedStyle(node);
  return (
    node.getBoundingClientRect().height +
    parseFloat(marginBlockStart) +
    parseFloat(marginBlockEnd)
  );
};

export class ReplyContinuity {
  #owner;
  #row = null;
  #departure = null;
  #space = 0;
  // The boxes a presentation changes itself, each with its height before it.
  #presenting = [];
  gap = document.createElement("div");
  constructor(owner) {
    this.#owner = owner;
    owner.classList.add("lf-reply-continuity");
    this.gap.className = "lf-reply-space";
    this.gap.setAttribute("aria-hidden", "true");
    owner.addEventListener("toggle", () => {
      if (!this.#visible()) this.release();
    });
  }

  #visible() {
    return this.#owner.isConnected && this.#row?.isConnected && growthIsSeen(this.#row);
  }
  // `own` are the boxes the presentation opens, closes, changes the words of or removes,
  // whose own height change the extent follows.
  before(own = []) {
    this.#row = this.#owner.querySelector(":scope > .lf-thread-reply");
    this.#presenting = [];
    if (!this.#visible()) return null;
    this.#presenting = own
      .filter((node) => node.isConnected)
      .map((node) => ({ node, height: room(node) }));
    const extent = parseFloat(getComputedStyle(this.#owner).blockSize);
    // Natural measurement can briefly clamp a surrounding scroller before the gap
    // settles. Use the shared synchronous place keeper to pay for that reflow only.
    // A floating surface owns its position; correcting the page scroller for growth
    // inside it moves the authored page under the reader instead.
    const place = offFlowSurfaceOf(this.#owner)
      ? null
      : placeKeeper(scrollerFor(this.#owner), {
          items: ".lf-reply-continuity",
          identity: (node) => node.dataset.thread,
          preferred: () => this.#owner,
        });
    return { extent, place, held: place?.take({ spans: false }) };
  }
  after(reading) {
    this.#row = this.#owner.querySelector(":scope > .lf-thread-reply");
    const presenting = this.#presenting;
    this.#presenting = [];
    if (!this.#row?.isConnected) return this.release();
    if (!this.#visible()) {
      reading?.place?.finish(reading.held);
      return this.release();
    }
    if (reading != null) {
      const { extent, place, held } = reading;
      const own = presenting.reduce(
        (sum, { node, height }) => sum + room(node) - height,
        0,
      );
      const now = parseFloat(getComputedStyle(this.#owner).blockSize);
      this.#keep(Math.max(0, this.#space + extent - now + own));
      place?.finish(held);
    }
    if (!this.#visible()) return this.release();
    this.#departure?.();
    this.#departure = whenNone([this.#row], growthIsSeen, () => this.release());
  }
  #keep(space) {
    if (space === this.#space) return;
    this.#space = space;
    const value = layoutPx(space);
    if (this.gap.style.getPropertyValue("--lf-reply-space") !== value)
      this.gap.style.setProperty("--lf-reply-space", value);
  }
  release() {
    this.#departure?.();
    this.#departure = null;
    this.#space = 0;
    if (this.gap.style.getPropertyValue("--lf-reply-space"))
      this.gap.style.removeProperty("--lf-reply-space");
  }
}
