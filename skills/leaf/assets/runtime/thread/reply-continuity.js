/* Natural thread layout with explicit space retained for passive presentation.

   Transcript, quote and response size themselves through CSS. A semantic presentation
   preserves the visible reply's position by converting removed content into a spacer;
   later content consumes that spacer. Local disclosures and native edits never take
   an allocation snapshot, so returning to a collapsed shape is ordinary layout.
   Message rewrites identify their changing boxes at the presentation boundary, so their
   own height change does not become passive space. The reply editor retains its room
   across mirrored draft replacement and while it is scrolled out of sight; native
   input returns it to intrinsic size. A departed or closed response releases both
   mechanical allocations. */
import { growthIsSeen, whenNone } from "../geometry.js";
import { atLayoutPrecision, layoutPx } from "../keeps.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { sizeObserver } from "../rendering.js";
import { placeKeeper } from "../user-place.js";
import { scrollerFor } from "../reading-regions.js";
import { offFlowSurfaceOf } from "../off-flow.js";
import { draftHasContent } from "../drafts.js";
import { replyDraftContext } from "./replies.js";

export class ReplyContinuity {
  #owner;
  #row = null;
  #departure = null;
  #space = 0;
  // Growth already deducted from passive space while a refused draft returns.
  #returningWriting = 0;
  // The writing areas a presentation changes, each with its height before it.
  #presenting = [];
  #writing = null;
  #sizes = sizeObserver((entries) => {
    const writing = this.#writing;
    if (
      !writing ||
      !entries.some(
        ({ target, borderBoxSize }) =>
          target === writing.input &&
          atLayoutPrecision(borderBoxSize[0].inlineSize) !== writing.width,
      )
    )
      return;
    // A new inline measure changes wrapping, independently of the draft's value.
    // Retain its new intrinsic room before this layout paints; a later frame
    // would temporarily turn the newly wrapped words into overflowing content.
    if (!this.#visible()) return this.#releaseSpace();
    writing.width = atLayoutPrecision(
      parseFloat(getComputedStyle(writing.input).inlineSize),
    );
    this.#allocateWriting(writing.input, layoutPx(writing.input.naturalBlockSize));
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
    return this.#owner.isConnected && this.#row?.isConnected && growthIsSeen(this.#row);
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
      return this.#releaseSpace();
    }
    this.#retainWriting();
    if (reading != null) {
      const { extent, place, held } = reading;
      const body = getComputedStyle(this.#owner);
      const written = presenting
        .filter(({ node }) => node.isConnected)
        .reduce(
          (sum, { node, height }) => sum + node.getBoundingClientRect().height - height,
          0,
        );
      // A refusal lifts the draft mask after this thread presentation. Its words
      // will grow the still-empty field back to the writing room we retained from
      // before Send. Account for that growth while replacing the departed turn
      // with passive space, rather than adding both the space and the words.
      const input = this.#row.querySelector(TEXT_FIELD);
      const context = input && replyDraftContext(input);
      const returning =
        this.#writing?.input === input &&
        context &&
        draftHasContent(context) &&
        !this.#owner.querySelector(".lf-msg.user[data-attempt]")
          ? Math.max(
              0,
              parseFloat(this.#writing.room) - input.getBoundingClientRect().height,
            )
          : 0;
      this.#keep(
        Math.max(
          0,
          this.#space +
            extent -
            parseFloat(body.blockSize) +
            written +
            this.#returningWriting -
            returning,
        ),
      );
      this.#returningWriting = returning;
      place?.finish(held);
    }
    if (!this.#visible()) return this.#releaseSpace();
    this.#departure?.();
    this.#departure = whenNone([this.#row], growthIsSeen, () => {
      if (!this.#owner.isConnected) this.release();
      else this.#releaseSpace();
    });
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
    if (!input?.value) {
      const context = input && replyDraftContext(input);
      if (context && draftHasContent(context) && this.#writing?.context === context) {
        if (this.#writing.input === input) return;
        const width = atLayoutPrecision(parseFloat(getComputedStyle(input).inlineSize));
        if (width === this.#writing.width)
          return this.#allocateWriting(input, this.#writing.room);
      }
      return this.#releaseWriting();
    }
    if (this.#writing?.input === input) return;
    this.#allocateWriting(input, getComputedStyle(input).blockSize);
  }
  #allocateWriting(input, room) {
    if (this.#writing?.input !== input) {
      this.#releaseWriting();
      this.#writing = {
        input,
        context: replyDraftContext(input),
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
    this.#returningWriting = 0;
    const { input } = this.#writing;
    input.style.removeProperty("--lf-reply-writing-room");
    this.#sizes.unobserve(input);
    this.#writing = null;
  }
  #releaseSpace() {
    this.#departure?.();
    this.#departure = null;
    this.#space = 0;
    this.#returningWriting = 0;
    if (this.gap.style.getPropertyValue("--lf-reply-space"))
      this.gap.style.removeProperty("--lf-reply-space");
  }
  release() {
    this.#releaseSpace();
    this.#releaseWriting();
  }
}
