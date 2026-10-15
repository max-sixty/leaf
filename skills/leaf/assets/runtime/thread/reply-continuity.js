/* Natural thread layout with explicit space retained for passive presentation.

   Transcript, quote and response size themselves through CSS. A semantic presentation
   preserves the visible reply's position by converting removed content into a spacer;
   later content consumes that spacer. Local disclosures and native edits never take
   an allocation snapshot, so returning to a collapsed shape is ordinary layout.
   Message rewrites identify their changing boxes at the presentation boundary, so their
   own height change does not become passive space. The reply editor alone retains its
   room across mirrored draft replacement; native input returns it to intrinsic size.
   A departed or closed response releases both mechanical allocations. */
import { growthIsSeen, whenNone } from "../geometry.js";
import { atLayoutPrecision, layoutPx } from "../keeps.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { nextRender, sizeObserver } from "../rendering.js";
import { placeKeeper } from "../user-place.js";
import { scrollerFor } from "../reading-regions.js";

export class ReplyContinuity {
  #owner;
  #row = null;
  #departure = null;
  #space = 0;
  // The writing areas a presentation changes, each with its height before it.
  #presenting = [];
  #writing = null;
  #measure = null;
  #sizes = sizeObserver((entries) => {
    const writing = this.#writing;
    if (
      !writing ||
      !entries.some(
        ({ target, borderBoxSize }) =>
          target === writing.input &&
          atLayoutPrecision(borderBoxSize[0].inlineSize) !== writing.width,
      ) ||
      this.#measure != null
    )
      return;
    // A new inline measure changes wrapping, independently of the draft's value.
    // Reallocate through the rendering pass, outside ResizeObserver delivery.
    this.#measure = nextRender(() => {
      this.#measure = null;
      if (this.#writing !== writing) return;
      if (!this.#visible()) return this.release();
      writing.width = atLayoutPrecision(
        parseFloat(getComputedStyle(writing.input).inlineSize),
      );
      this.#allocateWriting(writing.input, layoutPx(writing.input.naturalBlockSize));
    });
  });
  gap = document.createElement("div");
  constructor(owner) {
    this.#owner = owner;
    owner.classList.add("lf-reply-continuity");
    this.gap.className = "lf-reply-space";
    this.gap.setAttribute("aria-hidden", "true");
    owner.addEventListener("toggle", () => {
      if (!this.#visible()) this.release();
    });
    // Only native reply edits resize the editor; restored draft values fire no input.
    owner.addEventListener(
      "input",
      (event) => {
        if (!this.#row?.contains(event.target)) return;
        const input = this.#row.querySelector(TEXT_FIELD);
        if (input.value) this.#allocateWriting(input, layoutPx(input.naturalBlockSize));
        else this.#releaseWriting();
      },
      { capture: true },
    );
  }

  #visible() {
    return (
      this.#owner.isConnected &&
      (this.#owner.localName !== "details" || this.#owner.open) &&
      this.#row?.isConnected &&
      growthIsSeen(this.#row)
    );
  }
  // `writing` are the boxes the presentation opens, closes or changes the words of, as
  // rewrites do, whose own height changes the extent follows.
  before(writing = []) {
    this.#row = this.#owner.querySelector(":scope > .lf-thread-reply");
    this.#presenting = [];
    if (!this.#visible()) return null;
    this.#presenting = writing
      .filter((node) => node.isConnected)
      .map((node) => ({ node, height: node.getBoundingClientRect().height }));
    const body =
      this.#owner.localName === "details"
        ? getComputedStyle(this.#owner, "::details-content")
        : getComputedStyle(this.#owner);
    const extent = parseFloat(body.blockSize);
    // Natural measurement can briefly clamp a surrounding scroller before the gap
    // settles. Use the shared synchronous place keeper to pay for that reflow only.
    const place = placeKeeper(scrollerFor(this.#owner), {
      items: ".lf-reply-continuity",
      identity: (node) => node.dataset.id,
      preferred: () => this.#owner,
    });
    return { extent, place, held: place.take({ spans: false }) };
  }
  after(reading) {
    this.#row = this.#owner.querySelector(":scope > .lf-thread-reply");
    const presenting = this.#presenting;
    this.#presenting = [];
    if (
      !this.#row?.isConnected ||
      (this.#owner.localName === "details" && !this.#owner.open)
    )
      return this.release();
    if (!this.#visible()) {
      reading?.place.finish(reading.held);
      return this.release();
    }
    if (reading != null) {
      const { extent, place, held } = reading;
      const body =
        this.#owner.localName === "details"
          ? getComputedStyle(this.#owner, "::details-content")
          : getComputedStyle(this.#owner);
      const written = presenting
        .filter(({ node }) => node.isConnected)
        .reduce(
          (sum, { node, height }) => sum + node.getBoundingClientRect().height - height,
          0,
        );
      this.#keep(
        Math.max(0, this.#space + extent - parseFloat(body.blockSize) + written),
      );
      place.finish(held);
    }
    if (!this.#visible()) return this.release();
    this.#retainWriting();
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
  #retainWriting() {
    const input = this.#row?.querySelector(TEXT_FIELD);
    if (!input?.value) return this.#releaseWriting();
    if (this.#writing?.input === input) return;
    this.#allocateWriting(input, getComputedStyle(input).blockSize);
  }
  #allocateWriting(input, room) {
    if (this.#writing?.input !== input) {
      this.#releaseWriting();
      this.#writing = {
        input,
        width: atLayoutPrecision(parseFloat(getComputedStyle(input).inlineSize)),
        room: null,
      };
      this.#sizes.observe(input, { box: "border-box" });
    }
    if (this.#writing.room === room) return;
    this.#writing.room = room;
    input.style.setProperty("--lf-reply-writing-room", room);
  }
  #releaseWriting() {
    if (!this.#writing) return;
    const { input } = this.#writing;
    input.style.removeProperty("--lf-reply-writing-room");
    this.#sizes.unobserve(input);
    this.#writing = null;
  }
  release() {
    this.#departure?.();
    this.#departure = null;
    this.#space = 0;
    this.#releaseWriting();
    if (this.gap.style.getPropertyValue("--lf-reply-space"))
      this.gap.style.removeProperty("--lf-reply-space");
  }
}
