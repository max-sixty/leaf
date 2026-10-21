/* lf-tally: how many of a region's obligations are still to answer, and the way to the next.
 *
 * The region is the element `for` names, and which obligations it holds is `obligationsIn`
 * (runtime/obligations/place.js), the rule a side list's rows read too, so "7 of 8 to
 * answer" counts the obligations whose open marks the queue shows. An obligation counts as to answer
 * until the log admits its answer, including one the user discussed and left with the
 * agent; it leaves the count when the page adopts the answering reading, never on a
 * guess. Until the page's first reading is in, the tally says nothing rather than a
 * count of an inventory it has not seen.
 *
 * With `next`, a Next on me control steps to the next obligation waiting on the user inside
 * the region (`obligationActions.next`), from where the user stands, so a press keeps
 * them standing there rather than taking focus onto the control, as the On
 * panel's Next on me does. It is a native button: Tab and Enter reach it, and a
 * finger taps it. Pressed by keyboard, focus is on the control outside the region, so
 * the walk counts from the obligation the user last went to there, else the first in sight,
 * else the region's start (queue-walk.js says how). With none waiting it is disabled.
 *
 * The drawing matches the registry's `x-prepaint`, which delivery writes for the first
 * paint. Its room holds the widest count two digits wide, so
 * the words change without moving the control beside them or what follows. */
import {
  obligationsIn,
  elementById,
  html,
  keeps,
  LeafElement,
  nothing,
  offered,
  obligationActions,
  readObligations,
} from "/runtime/widget-api.js";

// The count's words: what remains of the whole, or that nothing does.
function words(open, total) {
  if (!total) return "Nothing to answer";
  if (open) return `${open} of ${total} to answer`;
  return total === 1 ? "Answered" : `All ${total} answered`;
}

customElements.define(
  "lf-tally",
  class extends LeafElement {
    setup() {
      this.querySelector(":scope > [data-lf-prepaint]")?.remove();
    }

    #region() {
      return elementById(this.getAttribute("for"));
    }

    #next() {
      const region = this.#region();
      if (region) obligationActions.next({ within: region });
    }

    render() {
      const items = readObligations();
      const region = this.#region();
      const ready = items.phase === "ready" && Boolean(region);
      const held = ready ? obligationsIn(region, items.all) : [];
      const open = held.filter((item) => item.status === "open").length;
      keeps(this, "data-lf-ready", ready ? "" : null);
      keeps(this, "data-lf-done", held.length && !open ? "" : null);
      // Two digits are in the drawing; a longer count widens its room once.
      const digits = "0".repeat(Math.max(2, String(held.length).length));
      return html`<span class="lf-tally-face" data-lf-gen="1"
        ><span class="lf-tally-count"
          ><span class="lf-tally-room">${words(digits, digits)}</span
          ><span class="lf-tally-room">Nothing to answer</span
          ><span class="lf-tally-words"
            >${ready ? words(open, held.length) : ""}</span
          ></span
        >${
          this.hasAttribute("next")
            ? html`<button
                ${offered("lf-btn lf-tally-next")}
                title="Next on me here"
                aria-controls=${this.getAttribute("for")}
                ?disabled=${!ready || obligationsIn(region, items.user).length === 0}
                @mousedown=${(event) => event.preventDefault()}
                @click=${this.#next}
              >
                Next on me
              </button>`
            : nothing
        }</span
      >`;
    }
  },
);
