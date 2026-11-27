/* lf-card: one card on a board, and the controls Leaf draws inside it. It is a
   decorating widget's member (lf-options.js, "How it is drawn"): the card's words are
   the author's and show through its root's `<slot>`, and its root holds the grip and,
   where a phone shows them, the buttons that move the card to another column, since
   both stand inside the card's box. The board tells each card its face (the `face`
   property) as a host sets `state`, and does every move; a card draws what it is told
   and records nothing itself. The theme dresses the controls through shadow parts:
   `grip`, and `destinations` with its `destinations-label` and each `destination`.

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
import { Component, Effect, Html, Mount, Schema, Stream } from "/vendor/effect-ui.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";
import {
  offerActionElement,
  offerAttributes,
  pressAttributes,
} from "/runtime/lib/controls.js";
import { PRESS } from "/runtime/lib/keys.js";

/** What a card shows of its board: the grip's name and keys, whether the card can
 *  move now and is held, and the columns its phone buttons offer. */
export const CardFace = Schema.Struct({
  title: Schema.String,
  name: Schema.String,
  movable: Schema.Boolean,
  held: Schema.Boolean,
  keys: Schema.Any,
  destinations: Schema.Array(
    Schema.Struct({ column: Schema.String, label: Schema.String }),
  ),
});
export type CardFace = typeof CardFace.Type;

// The id each card's `shows` held as Leaf first set its `choice` (the header).
const owners = new WeakMap<Element, string | null>();

/** The id of the widget whose `choice` `card` shows, or null. */
export const ownerOf = (card: Element) =>
  owners.has(card) ? (owners.get(card) ?? null) : card.getAttribute("shows") || null;

// The grip says the drag, as its description and under its name in its preview; the
// keys that grab it are its rows' own, its activation, which a control's preview leaves
// out, so the grip names them as key chips beside its name. Grabbed, the card is
// moving, so the grip says nothing over it until it drops.
const DRAG = "Drag to move";

// The grip wears the symbol role's face, which a view's attributes can't draw
// (controls.js, `pressAttributes`), and carries the rows its face gives it.
const OfferGrip = Mount.make(
  "OfferGrip",
  { args: { name: Schema.String, held: Schema.Boolean, keys: Schema.Any } },
  (grip: HTMLButtonElement, _args, changes) =>
    Stream.runForEach(changes, ({ name, held, keys }) =>
      Effect.sync(() => {
        const was = grip.lfCommands;
        offerActionElement(grip, "symbol", "lf-grip", name, { action: "move" });
        grip.lfPreview = () =>
          !held && { keys: PRESS.map((binding) => [binding]), detail: [DRAG] };
        grip.dispatchEvent(
          new CustomEvent("lf-preview", { bubbles: true, composed: true }),
        );
        if (was?.rows === keys) return;
        grip.lfCommands = { title: "On a card grip", rows: keys };
        grip.dispatchEvent(
          new CustomEvent("lf-commands", { bubbles: true, composed: true }),
        );
      }),
    ).pipe(Effect.as(Component.noop)),
);

// Says `change` on the card each time Leaf sets its `choice`, keeping the id its
// binding read.
const SaysChoice = Mount.make(
  "SaysChoice",
  { args: { choice: Schema.Unknown } },
  (node: Element, _args, changes) => {
    const card = (node.getRootNode() as ShadowRoot).host;
    return Stream.runForEach(changes, ({ choice }) =>
      Effect.sync(() => {
        if (choice === undefined) return;
        if (!owners.has(card)) owners.set(card, card.getAttribute("shows") || null);
        card.dispatchEvent(new Event("change"));
      }),
    ).pipe(Effect.as(Component.noop));
  },
);

export const Card = Html.component({
  name: "Card",
  props: Schema.Struct({
    ...widgetProps,
    face: Schema.optional(CardFace),
    choice: Schema.optional(Schema.Unknown),
  }),
  model: Schema.Struct({}),
  message: Schema.Never,
}).make({
  init: () => ({}),
  update: {},
  view: (h) => {
    const { face, choice } = h.props;
    return h.span
      .style({ display: "contents" })
      .onMount(SaysChoice({ choice }))
      .children(
        h.slot.key("slot"),
        face
          ? h.button
              .key("grip")
              .attr("part", "grip")
              // A revision that rewrites any card replaces the board, and a user on
              // this grip is on the same card's grip in the replacement
              // (records/carry.js).
              .attr("data-lf-carry", "grip")
              .attr("aria-description", DRAG)
              .attr("aria-disabled", String(!face.movable))
              .attr("tabindex", face.movable ? "0" : "-1")
              .onMount(OfferGrip({ name: face.name, held: face.held, keys: face.keys }))
          : null,
        face?.destinations.length
          ? h.div
              .key("destinations")
              .attrs(offerAttributes("div", "lf-board-destinations"))
              .attr("part", "destinations")
              .attr("role", "group")
              .attr("aria-label", `Move ${face.title} to`)
              .children(
                h.span
                  .class("lf-board-destinations-label")
                  .attr("part", "destinations-label")
                  .attr("data-lf-gen", "1")
                  .children("Move to"),
                ...face.destinations.map(({ column, label }) =>
                  h.button
                    .key(column)
                    .attrs(pressAttributes("word", "lf-board-destination"))
                    .attr("part", "destination")
                    .attr("data-lf-board-target", column)
                    .attr("aria-label", `Move ${face.title} to ${label}`)
                    .attr("disabled", face.movable ? undefined : "")
                    .children(label),
                ),
              )
          : null,
      );
  },
});

defineWidget("lf-card", Card, { shadow: true, properties: ["face", "choice"] });
