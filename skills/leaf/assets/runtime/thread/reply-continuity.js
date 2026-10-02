/* Mechanical continuity of a thread's live response region in flow or a floating card.

   Semantic presentation always draws only current messages. A visible response region
   keeps the body extent it occupied before that presentation, with flexible free space
   immediately before the reply row. Removed content becomes space; new content and
   native editor growth consume it, with the response foot held by layout rather than
   a later resize correction. A departed or closed region releases that mechanical
   extent. A floating card bounds that extent by its already allocated body room.
   No message or delivery state is retained. Panel and general footer keep their
   separate fixed/free layout. */
import { seenRect } from "../geometry.js";
import { layoutPx } from "../keeps.js";

export class ReplyContinuity {
  #owner;
  #row = null;
  #departure;
  gap = document.createElement("div");
  constructor(owner) {
    this.#owner = owner;
    owner.classList.add("lf-reply-continuity");
    this.gap.className = "lf-reply-space";
    this.gap.setAttribute("aria-hidden", "true");
    this.#departure = new IntersectionObserver(() => {
      if (!this.#visible()) this.release();
    });
    owner.addEventListener("toggle", () => {
      if (!this.#visible()) this.release();
    });
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
    this.#owner.style.setProperty("--lf-thread-body-extent", layoutPx(extent));
    this.#departure.observe(this.#row);
  }
  release() {
    this.#departure.disconnect();
    this.#owner.style.removeProperty("--lf-thread-body-extent");
  }
}
