/* Mechanical continuity of a thread's live response region on every surface.

   Semantic presentation always draws only current messages. A visible response region
   keeps the body extent it occupied before that presentation, with flexible free space
   immediately before the reply row. Removed content becomes space; new content and
   semantic draft restoration consume it, with the response foot held by layout rather
   than a later resize correction. Native edits change that retained extent by the
   reply's own height change: the transcript's space never retains deleted draft lines.
   A departed or closed region releases that mechanical extent. A floating card
   bounds that extent by its already allocated body room.
   No message or delivery state is retained; a short panel card starts at its
   natural extent, while a long card pins its reply within the list. */
import { seenRect, whenOffScreen } from "../geometry.js";
import { layoutPx } from "../keeps.js";

export class ReplyContinuity {
  #owner;
  #row = null;
  #departure = null;
  #extent = null;
  #replyHeight = 0;
  gap = document.createElement("div");
  constructor(owner) {
    this.#owner = owner;
    owner.classList.add("lf-reply-continuity");
    this.gap.className = "lf-reply-space";
    this.gap.setAttribute("aria-hidden", "true");
    owner.addEventListener("toggle", () => {
      if (!this.#visible()) this.release();
    });
    // Input names a native edit; writing a restored or mirrored draft fires none.
    // Rebase before the draft's listeners can repaint and retain its former height.
    owner.addEventListener(
      "input",
      (event) => {
        if (this.#row?.contains(event.target)) this.#edited();
      },
      { capture: true },
    );
  }
  #visible() {
    return (
      this.#owner.isConnected &&
      (this.#owner.localName !== "details" || this.#owner.open) &&
      this.#row?.isConnected &&
      Boolean(seenRect(this.#row, new Map()))
    );
  }
  before() {
    this.#row = this.#owner.querySelector(":scope > .lf-thread-reply");
    if (!this.#visible()) return null;
    const body =
      this.#owner.localName === "details"
        ? getComputedStyle(this.#owner, "::details-content")
        : getComputedStyle(this.#owner);
    return parseFloat(body.blockSize);
  }
  after(extent) {
    this.#row = this.#owner.querySelector(":scope > .lf-thread-reply");
    if (
      extent == null ||
      !this.#row?.isConnected ||
      (this.#owner.localName === "details" && !this.#owner.open)
    )
      return this.release();
    // Keep the prior extent before asking layout to read the changed body: scroll
    // anchoring need not pay a temporary collapse the live response never paints.
    this.#keep(extent);
    this.changed();
    this.#departure?.();
    this.#departure = whenOffScreen([this.#row], () => this.release());
  }
  #keep(extent) {
    if (extent === this.#extent) return;
    this.#extent = extent;
    this.#owner.style.setProperty("--lf-thread-body-extent", layoutPx(extent));
  }
  #edited() {
    if (this.#extent == null || !this.#row?.isConnected) return;
    const height = this.#row.getBoundingClientRect().height;
    this.#keep(Math.max(0, this.#extent + height - this.#replyHeight));
    this.#replyHeight = height;
  }
  // Draft hydration changes the row without a native input or a semantic repaint.
  // Its size is the starting point for the next edit, while its retained foot stays.
  changed() {
    if (this.#extent != null && this.#row?.isConnected)
      this.#replyHeight = this.#row.getBoundingClientRect().height;
  }
  release() {
    this.#departure?.();
    this.#departure = null;
    this.#extent = null;
    this.#owner.style.removeProperty("--lf-thread-body-extent");
  }
}
