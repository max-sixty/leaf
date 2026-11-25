import { render as tallyTemplate } from "./tally-view.js";
/* lf-tally: how many of a region's obligations are still open, whose turn each is, and the
 * way to the next one waiting on the user.
 *
 * The region is the element `for` names, and which obligations it holds is
 * `obligations.read(region)`, the rule a side list's rows read too, so the total
 * counts the obligations whose marks the queue shows. An obligation stays open until the
 * page adopts the reading that admits its answer, never on a guess. The count splits the
 * open ones by the server's next actor, in the words `tally` and `tallyWords`
 * (runtime/lib/obligation-tally.js) give, which say why they split as they do. Until
 * the page's first reading is in, the tally says nothing rather than a count of an
 * inventory it has not seen.
 *
 * With `next`, a Next On Me control steps to the next obligation waiting on the user inside
 * the region (`go({within})`), from where the user is, so a press keeps
 * them there rather than taking focus onto the control, as the On
 * panel's Next On Me does. It is a native button: Tab and Enter reach it, and a
 * finger taps it. Pressed by keyboard, focus is on the control outside the region, so
 * the walk counts from the obligation the user last went to there, else the first in sight,
 * else the region's start (queue-walk.js says how). With none waiting it is disabled.
 *
 * The agent is called what the On lists call it (`queues.read().agent`), "On Claude"
 * where the panel says so.
 *
 * One retained Lit drawing follows the server's
 * reading in the same nodes. Its room holds the widest words, both sides two digits
 * wide and the agent called "the agent", so the words change without moving the control
 * beside them or what follows. A longer count or agent name widens the room once. */
import { go, obligations, queues } from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { tally, tallyWords } from "/runtime/lib/obligation-tally.js";

customElements.define(
  "lf-tally",
  class extends LeafElement {
    static shadow = true;
    #next = () => {
      const region = this.#region();
      if (region) go({ within: region });
    };

    #region() {
      const id = this.getAttribute("for");
      return id
        ? /** @type {Document | ShadowRoot} */ (this.getRootNode()).getElementById(id)
        : null;
    }

    render() {
      const region = this.#region();
      // The page's reading is read with no region yet too, so the reading that brings
      // the region draws the tally again.
      const ready = obligations.read().phase === "ready" && Boolean(region);
      const held = ready && region ? obligations.read(region).all : [];
      const count = tally(held);
      // The drawing's two rooms hold the widest words, one calling the agent "the
      // agent" and one by its name; a longer count widens them once.
      const digits = "0".repeat(Math.max(2, String(held.length).length));
      const widest = { onUser: digits, onAgent: digits, open: digits, total: digits };
      const { agent } = queues.read();
      return tallyTemplate(
        this,
        {
          ready,
          done: Boolean(held.length && !count.open),
          generic: tallyWords(widest, "the agent"),
          named: tallyWords(widest, agent),
          words: ready ? tallyWords(count, agent) : "",
          onUser: count.onUser,
        },
        this.#next,
      );
    }
  },
);
