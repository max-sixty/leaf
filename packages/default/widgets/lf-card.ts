/* lf-card: one card on a board, and the controls Leaf draws inside it. The card's words
   are the author's and stay where the author wrote them; the card draws its grip and,
   where a phone shows them, the buttons that move it to another column after those
   words, as its own children, since both stand inside the card's box. The board tells
   each card its face (the `face` property) as a host sets `state`, and does every move;
   a card draws what it is told and records nothing itself. board.css places the grip
   in the card's corner and shows the buttons on a phone.

   Why it is a `LeafElement` and not an Effect UI component (browser/AGENTS.md,
   "Renderers"): Effect UI's mount needs a box of its own, and a view returns one root,
   so the controls would stand in two `display: contents` wrappers (`defineWidget`'s
   box and the view's root) inside every card. Leaf's walkers, margin layout, passages
   and arrivals among them, pay for each element they meet, and a page of 256 cards
   loaded about a third slower with them than with the controls as the card's own
   children (`leaf-dev bench cards`). A card holds no logic of its own to test as a
   Story: the board's component decides every face (lf-board.js).

   The grip is a symbol (controls.js) whose keys the board declares: the face carries
   the grip's rows (`keys`), which read the board as it stands when a key is pressed,
   and the card seats them on the grip, the one node they belong to (lf-board.js,
   "Keys"). A destination button names its column (`data-lf-board-target`), and the
   board hears its press.

   A card whose `shows` names another widget is a view of the pick that widget holds as
   its `choice`, which the card binds as an input, so Leaf sets it on `choice` as the
   pick moves. The card says `change` on itself each time it does, as a form control
   says its value moved, so its board reads its cards again and stands the card in the
   column the pick names (lf-board.js). The card's owner is the widget its binding
   reads: the one `shows` named when Leaf first set `choice`, the moment Leaf captured
   the binding (host/data.js), so a drop asks the widget whose choice the card shows
   even after a script rewrites `shows` (`ownerOf`). A card whose binding finds no
   widget shows no choice and can't be moved. */
import { html, nothing } from "/vendor/lit.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { offered, offeredAction } from "/runtime/lib/controls.js";
import { PRESS } from "/runtime/lib/keys.js";

/** What a card shows of its board: the grip's name and keys, whether the card can
 *  move now and is held, and the columns its phone buttons offer. */
export type CardFace = {
  readonly title: string;
  readonly name: string;
  readonly movable: boolean;
  readonly held: boolean;
  readonly keys: unknown;
  readonly destinations: readonly { readonly column: string; readonly label: string }[];
};

// The id each card's `shows` held as Leaf first set its `choice` (the header).
const owners = new WeakMap<Element, string | null>();

/** The id of the widget whose `choice` `card` shows, or null. */
export const ownerOf = (card: Element) =>
  owners.has(card) ? (owners.get(card) ?? null) : card.getAttribute("shows") || null;

/** The grip `card` draws, or null. */
export const gripOf = (card: Element) =>
  card.querySelector<HTMLElement>(":scope > .lf-grip");

// The grip says the drag, as its description and under its name in its preview; the
// keys that grab it are its rows' own, its activation, which a control's preview leaves
// out, so the grip names them as key chips beside its name. Grabbed, the card is
// moving, so the grip says nothing over it until it drops.
const DRAG = "Drag to move";

customElements.define(
  "lf-card",
  class extends LeafElement {
    #face: CardFace | undefined;
    #choice: unknown;

    constructor() {
      super();
      // A board or Leaf that set these before the class was defined set own
      // properties, which would hide the accessors below.
      const own = this as unknown as Record<string, unknown>;
      for (const name of ["face", "choice"])
        if (Object.hasOwn(this, name)) {
          const value = own[name];
          delete own[name];
          queueMicrotask(() => (own[name] = value));
        }
    }

    // The board moves its cards with `moveBefore` (dom-move.js), and a moved card is
    // the same card: it connects again only where the browser lacks the API, so a
    // move doesn't say `lf-connect` and have Leaf set the board's `state` again.
    connectedMoveCallback() {}

    get face() {
      return this.#face;
    }
    set face(face: CardFace | undefined) {
      const old = this.#face;
      this.#face = face;
      this.requestUpdate("face", old);
    }

    get choice() {
      return this.#choice;
    }
    set choice(choice: unknown) {
      this.#choice = choice;
      if (choice === undefined) return;
      if (!owners.has(this)) owners.set(this, this.getAttribute("shows") || null);
      this.dispatchEvent(new Event("change"));
    }

    render() {
      const face = this.#face;
      if (!face) return nothing;
      const { title, movable } = face;
      // A revision that rewrites any card replaces the board, and a user on the grip is
      // on the same card's grip in the replacement (records/carry.js).
      return html`<button
          ${offeredAction("symbol", "lf-grip", face.name, { action: "move" })}
          data-lf-carry="grip"
          aria-description=${DRAG}
          aria-disabled=${String(!movable)}
          tabindex=${movable ? "0" : "-1"}
        ></button
        >${
          face.destinations.length
            ? html`<div
                ${offered("lf-board-destinations")}
                role="group"
                aria-label=${`Move ${title} to`}
              >
                <span class="lf-board-destinations-label" data-lf-gen="1">Move to</span
                >${face.destinations.map(
                  ({ column, label }) =>
                    html`<button
                      ${offeredAction("word", "lf-board-destination")}
                      data-lf-board-target=${column}
                      aria-label=${`Move ${title} to ${label}`}
                      ?disabled=${!movable}
                    >
                      ${label}
                    </button>`,
                )}
              </div>`
            : nothing
        }`;
    }

    // The grip carries the rows its face gives it, and previews the drag while the
    // card is not held.
    updated() {
      const face = this.#face;
      const grip = face && gripOf(this);
      if (!face || !grip) return;
      const held = face.held;
      grip.lfPreview = () =>
        !held && { keys: PRESS.map((binding) => [binding]), detail: [DRAG] };
      grip.dispatchEvent(
        new CustomEvent("lf-preview", { bubbles: true, composed: true }),
      );
      if (grip.lfCommands?.rows === face.keys) return;
      grip.lfCommands = {
        title: "On a card grip",
        rows: face.keys as NonNullable<HTMLElement["lfCommands"]>["rows"],
      };
      grip.dispatchEvent(
        new CustomEvent("lf-commands", { bubbles: true, composed: true }),
      );
    }
  },
);
