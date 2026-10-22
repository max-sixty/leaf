/* lf-tally: how many of a region's obligations are still open, whose turn each is, and the
 * way to the next one waiting on the user.
 *
 * The region is the element `for` names, and which obligations it holds is `obligationsIn`
 * (runtime/obligations/place.js), the rule a side list's rows read too, so the total
 * counts the obligations whose marks the queue shows. An obligation stays open until the
 * page adopts the reading that admits its answer, never on a guess. The count splits the
 * open ones by the server's next actor. Those waiting on the user, which Next on me walks
 * (`readObligations().user`), are "to answer". Those whose next actor is the agent, such
 * as one the user commented on and whose reply the agent owes (`obligations.discussed`),
 * are counted under the agent's name, as its On list names it (`agentName`):
 * "7 of 8 to answer", "2 of 8 to answer · 1 on Claude", "1 of 8 on Claude". So the words
 * say something is the user's to answer exactly when Next on me is enabled. A frozen
 * obligation in a resolved thread is open with no next actor, so it counts on neither
 * side, and a region holding only such ones reads "1 of 1 open". An earlier
 * tally counted every open obligation as to answer and read "1 of 8 to answer" beside a
 * disabled Next on me once the last one went to the agent. Until the page's first reading
 * is in, the tally says nothing rather than a count of an inventory it has not seen.
 *
 * With `next`, a Next on me control steps to the next obligation waiting on the user inside
 * the region (`obligationActions.next`), from where the user stands, so a press keeps
 * them standing there rather than taking focus onto the control, as the On
 * panel's Next on me does. It is a native button: Tab and Enter reach it, and a
 * finger taps it. Pressed by keyboard, focus is on the control outside the region, so
 * the walk counts from the obligation the user last went to there, else the first in sight,
 * else the region's start (queue-walk.js says how). With none waiting it is disabled.
 *
 * The structure is the registry's `x-prepaint`, which delivery writes for the first
 * paint and this module fills in. Its room holds the widest words, both sides two digits
 * wide and the agent called "the agent", so the words change without moving the control
 * beside them or what follows. A longer count or agent name widens the room once. */
import {
  agentName,
  obligationsIn,
  declarationFor,
  elementById,
  keeps,
  LeafElement,
  nothing,
  offer,
  obligationActions,
  readObligations,
  relabel,
  render,
} from "/runtime/widget-api.js";

// The count's words: how many of the region's obligations wait on the user and how many
// on the agent, of all it holds; how many are open where neither is next, as in a
// resolved thread; or that none is open.
function words({ onUser, onAgent, open, total }, agent) {
  if (!total) return "Nothing to answer";
  if (onUser && onAgent)
    return `${onUser} of ${total} to answer · ${onAgent} on ${agent}`;
  if (onUser) return `${onUser} of ${total} to answer`;
  if (onAgent) return `${onAgent} of ${total} on ${agent}`;
  if (open) return `${open} of ${total} open`;
  return total === 1 ? "Answered" : `All ${total} answered`;
}

customElements.define(
  "lf-tally",
  class extends LeafElement {
    #rooms = [];
    #words = null;
    #next = null;

    setup() {
      const drawing = document.createElement("template");
      drawing.innerHTML = declarationFor(this, "x-prepaint");
      const face = /** @type {HTMLElement} */ (drawing.content.firstElementChild);
      face.dataset.lfGen = "1";
      this.#rooms = [...face.querySelectorAll(".lf-tally-room")];
      for (const room of this.#rooms) room.replaceChildren();
      this.#words = face.querySelector(".lf-tally-words");
      const seat = face.querySelector(".lf-tally-next");
      if (this.hasAttribute("next")) {
        this.#next = offer("button", "lf-btn lf-tally-next");
        seat.replaceWith(this.#next);
        relabel(this.#next, "Next on me", { says: false });
        this.#next.title = "Next on me here";
        this.#next.setAttribute("aria-controls", this.getAttribute("for"));
        this.#next.addEventListener("mousedown", (event) => event.preventDefault());
        this.#next.addEventListener("click", () => {
          const region = this.#region();
          if (region) obligationActions.next({ within: region });
        });
      } else seat.remove();
      this.querySelector(":scope > [data-lf-prepaint]")?.remove();
      this.append(face);
    }

    #region() {
      return elementById(this.getAttribute("for"));
    }

    render() {
      const items = readObligations();
      const region = this.#region();
      const ready = items.phase === "ready" && Boolean(region);
      const held = ready ? obligationsIn(region, items.all) : [];
      const open = held.filter((item) => item.status === "open");
      const count = {
        onUser: open.filter((item) => item.next_actor === "user").length,
        onAgent: open.filter((item) => item.next_actor === "agent").length,
        open: open.length,
        total: held.length,
      };
      keeps(this, "data-lf-ready", ready ? "" : null);
      keeps(this, "data-lf-done", held.length && !open.length ? "" : null);
      // The drawing's two rooms hold the widest words, one calling the agent "the
      // agent" and one by its name; a longer count widens them once.
      const digits = "0".repeat(Math.max(2, String(held.length).length));
      const widest = { onUser: digits, onAgent: digits, open: digits, total: digits };
      const [generic, named] = this.#rooms;
      render(words(widest, "the agent"), generic);
      render(words(widest, agentName()), named);
      render(ready ? words(count, agentName()) : "", this.#words);
      if (this.#next) keeps(this.#next, "disabled", count.onUser ? null : "");
      return nothing;
    }
  },
);
