/* lf-tally: how many of a region's asks are still to answer, and the way to the next.
 *
 * The region is the element `for` names, and which asks it holds is `asksIn`
 * (runtime/questions/place.js), the rule a side list's rows read too, so "7 of 8 to
 * answer" counts the asks whose open marks the queue shows. An ask counts as to answer
 * until the log admits its answer, including one the user discussed and left with the
 * agent; it leaves the count when the page adopts the answering reading, never on a
 * guess. Until the page's first reading is in, the tally says nothing rather than a
 * count of an inventory it has not seen.
 *
 * With `next`, a Next question control steps to the next ask waiting on the user inside
 * the region (`questionActions.next`), from where the user stands, so a press keeps
 * them standing there rather than taking focus onto the control, as the Questions
 * panel's Next question does. It is a native button: Tab and Enter reach it, and a
 * finger taps it. Pressed by keyboard, focus is on the control outside the region, so
 * the walk counts from the ask the user last went to there, else the first in sight,
 * else the region's start (queue-walk.js says how). With none waiting it is disabled.
 *
 * The structure is the registry's `x-prepaint`, which delivery writes for the first
 * paint and this module fills in. Its room holds the widest count two digits wide, so
 * the words change without moving the control beside them or what follows. */
import {
  asksIn,
  declarationFor,
  elementById,
  keeps,
  keepsText,
  offer,
  once,
  questionActions,
  relabel,
  watchQuestions,
} from "/runtime/widget-api.js";

// The count's words: what remains of the whole, or that nothing does.
function words(open, total) {
  if (!total) return "Nothing to answer";
  if (open) return `${open} of ${total} to answer`;
  return total === 1 ? "Answered" : `All ${total} answered`;
}

export default class extends HTMLElement {
  #room = null;
  #words = null;
  #next = null;

  connectedCallback() {
    if (!once(this)) return;
    const drawing = document.createElement("template");
    drawing.innerHTML = declarationFor(this, "x-prepaint");
    const face = drawing.content.firstElementChild;
    face.dataset.lfGen = "1";
    this.#room = face.querySelector(".lf-tally-room");
    this.#words = face.querySelector(".lf-tally-words");
    const seat = face.querySelector(".lf-tally-next");
    if (this.hasAttribute("next")) {
      this.#next = offer("button", "lf-btn lf-tally-next");
      seat.replaceWith(this.#next);
      relabel(this.#next, "Next question", { says: false });
      this.#next.title = "Go to the next question waiting on you here";
      this.#next.setAttribute("aria-controls", this.getAttribute("for"));
      this.#next.addEventListener("mousedown", (event) => event.preventDefault());
      this.#next.addEventListener("click", () => {
        const region = this.#region();
        if (region) questionActions.next({ within: region });
      });
    } else seat.remove();
    this.querySelector(":scope > [data-lf-prepaint]")?.remove();
    this.append(face);
    watchQuestions(this, (asks) => this.#paint(asks));
  }

  #region() {
    return elementById(this.getAttribute("for"));
  }

  #paint(asks) {
    const region = this.#region();
    const ready = asks.phase === "ready" && Boolean(region);
    keeps(this, "data-lf-ready", ready ? "" : null);
    if (!ready) {
      keepsText(this.#words, "");
      return;
    }
    const held = asksIn(region, asks.all);
    const open = held.filter((ask) => ask.status === "open").length;
    keeps(this, "data-lf-done", held.length && !open ? "" : null);
    keepsText(this.#words, words(open, held.length));
    // Two digits are in the drawing; a longer count widens its room once.
    const digits = "0".repeat(Math.max(2, String(held.length).length));
    keepsText(this.#room, words(1, 1).replace(/1 of 1/, `${digits} of ${digits}`));
    this.#next?.toggleAttribute("disabled", asksIn(region, asks.user).length === 0);
  }
}
