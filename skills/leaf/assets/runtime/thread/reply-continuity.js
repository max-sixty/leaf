/* Mechanical continuity of a thread's live response region on every surface.

   Semantic presentation always draws only current messages. A visible response region
   keeps the body extent it occupied before that presentation, with flexible free space
   immediately before the reply row. Removed content becomes space; new content
   consumes it, with the response foot held by layout rather than a later resize
   correction. A region is visible while a change of size at its reply row would move
   what the user sees (geometry.js, `growthIsSeen`), and departs once one would not.
   The editor retains its allocated room across passive draft replacement, so
   surviving words and Send stay put; longer replacement text scrolls inside it.
   A change of inline measure starts a fresh allocation. Native edits resize that
   room to their intrinsic content. What the user writes is theirs to see grow and
   shrink: the retained body extent follows the boxes the user resizes, through native
   editing, a rewrite (`before(writing)`) or a disclosure's click. Disclosures declare
   their content through native details or aria-controls, so rich replies and Leaf's
   own controls follow the same resize path. Space held for news stays held.
   A departed or closed region releases that mechanical extent. A floating card
   bounds that extent by its already allocated body room.
   No message or delivery state is retained; a short panel card starts at its
   natural extent, while a long card pins its reply within the list. */
import { growthIsSeen, whenNone } from "../geometry.js";
import { atLayoutPrecision, layoutPx } from "../keeps.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { cancelRender, nextRender, sizeObserver } from "../rendering.js";
import { DISCLOSURE_SELECTOR, disclosed } from "../keyboard/disclosure.js";

// The smallest box containing a disclosure and all the content it controls. Native
// details declares that box itself; ARIA disclosures name their content by id.
function disclosureLayout(control) {
  if (control.matches("details > summary"))
    return {
      region: control.parentElement,
      state: control.parentElement,
      attribute: "open",
    };
  const root = control.getRootNode();
  const controlled = (control.getAttribute("aria-controls") ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .map((id) => root.getElementById(id));
  if (!controlled.length || controlled.some((node) => !node)) return null;
  let region = control;
  while (region && !controlled.every((node) => region.contains(node)))
    region = region.parentElement;
  return region ? { region, state: control, attribute: "aria-expanded" } : null;
}

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
  #disclosure = null;
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
    owner.addEventListener("click", (event) => this.#disclosed(event), {
      capture: true,
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
  // Pointer and keyboard activation both click the disclosure. Capture before its
  // handler or native default changes the box, then reconcile at its state checkpoint.
  // Waiting for a frame would include passive changes arriving after that gesture.
  // The composed path reaches disclosures in a message widget's shadow root too.
  #disclosed(event) {
    this.#disclosure?.finish();
    const control = event
      .composedPath()
      .find((node) => node instanceof Element && node.matches(DISCLOSURE_SELECTOR));
    if (!control) return;
    const layout = disclosureLayout(control);
    if (!layout || layout.region === this.#owner || !this.#visible()) return;
    const { region, state, attribute } = layout;
    const open = disclosed(control);
    const height = region.getBoundingClientRect().height;
    const extent = this.before();
    const reading = { region, frame: null, observer: null, finish: null };
    const finish = () => {
      cancelRender(reading.frame);
      reading.observer.disconnect();
      if (this.#disclosure !== reading) return;
      this.#disclosure = null;
      if (
        !control.isConnected ||
        !region.isConnected ||
        disclosed(control) === open ||
        !this.#visible()
      )
        return;
      this.after(
        Math.max(
          0,
          (this.#extent ?? extent) + region.getBoundingClientRect().height - height,
        ),
      );
    };
    reading.finish = finish;
    this.#disclosure = reading;
    // Watch the state node itself: toggle neither bubbles nor leaves a shadow root.
    reading.observer = new MutationObserver(() => {
      if (disclosed(control) !== open) finish();
    });
    reading.observer.observe(state, { attributes: true, attributeFilter: [attribute] });
    // A canceled activation changes no state; it still ends this observation.
    reading.frame = nextRender(finish);
  }
  #visible() {
    return (
      this.#owner.isConnected &&
      (this.#owner.localName !== "details" || this.#owner.open) &&
      this.#row?.isConnected &&
      growthIsSeen(this.#row)
    );
  }
  // A disclosure's region already includes the editors inside it. Count each change
  // once, while still following an independent rewrite elsewhere in the card.
  before(writing = []) {
    this.#row = this.#owner.querySelector(":scope > .lf-thread-reply");
    this.#presenting = [];
    if (!this.#visible()) return null;
    this.#presenting = writing
      .filter((node) => node.isConnected && !this.#disclosure?.region.contains(node))
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
    this.#departure = whenNone([this.#row], growthIsSeen, () => this.release());
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
    if (this.#disclosure) {
      cancelRender(this.#disclosure.frame);
      this.#disclosure.observer.disconnect();
    }
    this.#disclosure = null;
    this.#departure?.();
    this.#departure = null;
    this.#extent = null;
    this.#releaseWriting();
    this.#owner.style.removeProperty("--lf-thread-body-extent");
  }
}
