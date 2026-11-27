/* lf-card: one card on a board. A card whose `shows` names another widget is a view of
   the pick that widget holds as its `choice`, which the card binds as an input
   (`inputs`), so Leaf sets it on `choice` as the pick moves. Its board stands the card
   in the column the pick names and asks the widget for a pick (lf-board.js), so the
   card only asks its board to draw again. The class exists so that Leaf drives the
   card, since Leaf sets nothing on an element whose class isn't defined; every card is
   driven, whether or not it has `shows`.

   The card's `owner` is the widget its binding reads: the element `elementById` names
   from the card under the id `shows` held when Leaf first set the card's `choice`, the
   moment Leaf captured the binding, which is the producer Leaf reads the binding from
   whenever there is one (host/data.js). So a drop asks the
   widget whose `choice` the card shows, and a card whose binding finds no widget shows
   no choice and can't be moved. */
import { elementById } from "/runtime/widget-api.js";

customElements.define(
  "lf-card",
  class extends HTMLElement {
    /** @type {unknown} */
    #choice = null;
    // The id the binding reads, read as Leaf first sets `choice`.
    /** @type {string | null | undefined} */
    #shows;

    get owner() {
      return this.#shows ? elementById(this.#shows, this) : null;
    }

    get choice() {
      return this.#choice;
    }

    set choice(value) {
      if (this.#shows === undefined) this.#shows = this.getAttribute("shows") || null;
      this.#choice = value;
      // A board whose class isn't defined yet reads this value as it first draws.
      const board = /** @type {{requestUpdate?: () => void} | null} */ (
        this.closest("lf-board")
      );
      board?.requestUpdate?.();
    }
  },
);
