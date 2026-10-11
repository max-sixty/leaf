/* Mechanical continuity of a thread's live response region on every surface.

   Semantic presentation always draws only current messages. A visible response region
   keeps the body extent it occupied before that presentation, with flexible free space
   immediately before the reply row. Removed content becomes space; new content
   consumes it, with the response foot held by layout rather than a later resize
   correction. The editor retains its allocated room across passive draft replacement,
   so surviving words and Send stay put; longer replacement text scrolls inside it.
   A change of inline measure starts a fresh allocation. Native edits resize that
   room to their intrinsic content. What the user writes is theirs to see grow and
   shrink: the retained body extent changes by the height change of the box they write
   in, the reply row or a message they are rewriting (`message-edit.js`), on each native
   edit and on each presentation that opens, closes or saves a rewrite
   (`before(writing)`), so the transcript's space never retains deleted lines, and
   space held for news stays held.
   A departed or closed region releases that mechanical extent. A floating card
   bounds that extent by its already allocated body room.
   No message or delivery state is retained; a short panel card starts at its
   natural extent, while a long card pins its reply within the list. */
import { seenRect, whenOffScreen } from "../geometry.js";
import { atLayoutPrecision, layoutPx } from "../keeps.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { nextRender, sizeObserver } from "../rendering.js";

// The box an edit is written in: the thread's reply row, or the message whose rewrite
// holds the target.
const writingArea = (row, target) =>
  row?.contains(target)
    ? row
    : (target.closest?.(".lf-msg-editor")?.closest(".lf-msg") ?? null);

export class ReplyContinuity {
  #owner;
  #row = null;
  #departure = null;
  #extent = null;
  // The writing area read at an edit's boundary, and its height then.
  #read = null;
  #readHeight = 0;
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
      this.#readArea(this.#row);
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
    owner.addEventListener("lf-before-edit", (event) =>
      this.#readArea(writingArea(this.#row, event.target)),
    );
    // Input names a native edit; writing a restored or mirrored draft fires none.
    // Rebase before the draft's listeners can repaint and retain its former height.
    owner.addEventListener(
      "input",
      (event) => this.#edited(writingArea(this.#row, event.target)),
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
    return parseFloat(body.blockSize);
  }
  after(extent) {
    this.#row = this.#owner.querySelector(":scope > .lf-thread-reply");
    const presenting = this.#presenting;
    this.#presenting = [];
    if (
      extent == null ||
      !this.#row?.isConnected ||
      (this.#owner.localName === "details" && !this.#owner.open)
    ) {
      this.release();
      if (this.#visible()) this.#retainWriting();
      return;
    }
    // Keep the prior extent before asking layout to read the changed body: scroll
    // anchoring need not pay a temporary collapse the live response never paints. An
    // extent already held does that itself, so the one write is the followed extent.
    if (this.#extent == null) this.#keep(extent);
    const grown = presenting
      .filter(({ node }) => node.isConnected)
      .reduce(
        (sum, { node, height }) => sum + node.getBoundingClientRect().height - height,
        0,
      );
    this.#keep(Math.max(0, extent + grown));
    this.#readArea(this.#row);
    this.#retainWriting();
    this.#departure?.();
    this.#departure = whenOffScreen([this.#row], () => this.release());
  }
  #keep(extent) {
    if (extent === this.#extent) return;
    this.#extent = extent;
    this.#owner.style.setProperty("--lf-thread-body-extent", layoutPx(extent));
  }
  #edited(area) {
    if (!area?.isConnected) return;
    if (area === this.#row) {
      const input = this.#row.querySelector(TEXT_FIELD);
      if (input.value) this.#allocateWriting(input, layoutPx(input.naturalBlockSize));
      else this.#releaseWriting();
    }
    const height = area.getBoundingClientRect().height;
    if (this.#extent != null && area === this.#read)
      this.#keep(Math.max(0, this.#extent + height - this.#readHeight));
    this.#read = area;
    this.#readHeight = height;
  }
  #readArea(area) {
    if (!area?.isConnected) return;
    this.#read = area;
    this.#readHeight = area.getBoundingClientRect().height;
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
    this.#extent = null;
    this.#releaseWriting();
    this.#owner.style.removeProperty("--lf-thread-body-extent");
  }
}
