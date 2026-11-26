/* lf-card: one card on a board. A card whose `shows` names another widget is a view of
   the pick that widget holds as its `choice`, which the card binds as an input
   (`inputs`), so Leaf sets it on `choice` as the pick moves. Its board stands the card
   in the column the pick names and asks the widget for a move (lf-board.js), so the
   card only asks its board to draw again. The class exists so that Leaf drives the
   card, since Leaf sets nothing on an element whose class isn't defined; every card is
   driven, whether or not it has `shows`. */

customElements.define(
  "lf-card",
  class extends HTMLElement {
    /** @type {unknown} */
    #choice = null;

    get choice() {
      return this.#choice;
    }

    set choice(value) {
      this.#choice = value;
      // A board whose class isn't defined yet reads this value as it first draws.
      const board = /** @type {{requestUpdate?: () => void} | null} */ (
        this.closest("lf-board")
      );
      board?.requestUpdate?.();
    }
  },
);
