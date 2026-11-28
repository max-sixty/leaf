/* lf-board: the one widget the user edits directly, with every move sharing one send
 * path and one gesture gate. Dragging is wired via the vendored SortableJS
 * (pointer-driven `forceFallback` mode, so the follower is stylable — native HTML5 DnD
 * is not used). A short label follows the pointer; native state stays in the real
 * card. Phones show each card's other columns as direct move buttons instead: the
 * board stacks its columns there (board.css), so another column is a long press-hold
 * drag through autoscroll away, and the buttons name every destination where the card is.
 * The grip is a press, so the keyboard path needs no pointer: Enter grabs, arrows
 * restate the card's placement (announced through the live region), Enter drops, and
 * Escape or focus loss restores the origin. Left and Right change column, named for the
 * column rather than a direction, since on a stacked board the next column stands
 * below; there Down past a column's last card continues into the column below and Up
 * past its first into the one above, the next slot the user sees (`Stepped`). Escape
 * also cancels a pointer drag.
 *
 * For the whole gesture the board says the user holds a card (`lf-hold`), so no new
 * revision or undo replaces the cards under the hand, and holds its own drawing
 * (`lf-defer`), so no foreign move replays mid-gesture: it draws the placement it held
 * as the gesture began, with the user's steps on it (`held`). A completed move reports
 * as one ranked `move` action (`RecordAction`), indistinguishable on the wire, and
 * Leaf has set the state the move gives before the board draws again, so releasing the
 * hold draws the card where the user put it. A refusal is restored from the state Leaf
 * sets again, never from the gesture's placement. Presentation is theme CSS; authored
 * content is never replaced, so there is no failSoft.
 *
 * A card with `shows` is the board's view of another widget's pick, such as a
 * proposal's answer in its own section, and the pick stays that widget's. The card binds
 * the widget's `choice` output (lf-card.js), so the board draws the card in the column
 * whose `value` the pick names, or in the first column without a `value` where the
 * pick names none or no column holds it. A pick there, an undo, a refusal and a
 * revision's retraction move the card with no state of the board's own. Dropping the
 * card in another column asks its owner, the widget whose choice it shows, to pick
 * that column's value with the invoker command `--choose`, from a button whose words
 * name the move, so Undo names it (`AskOwner`). The owner records the pick as its own or
 * refuses it, and either way the board then draws the card where the owner's choice
 * puts it. A column without a `value` asks for the empty pick. A column with one takes
 * the card only where one option carries that value, since a value two options carry
 * doesn't say which the user picks. A card no other column takes has its grip disabled.
 * The arrows only change a shown card's column: an order of the board's own would be a
 * second fact placed among columns the choice decides.
 *
 * The user chose this over the board reading the widget's state and recording the
 * widget's own verb, which tied the board to each widget's verbs, record kinds and
 * members, and needed a package function that reads any widget's state. An Answer
 * record, or a value on the question's group, would move the answer off the widget
 * that owns its words, options and obligation.
 *
 * `page check` and message admission refuse a `shows` naming a widget that holds no
 * `choice`, through the card's input. The user chose that refusal over the board
 * reporting a bad `shows` as it draws, since a contract-bound input gives it without a
 * registry map of the widgets a card may show. The append door admits a board move of
 * a card with `shows`, so the board never sends its own move for one (`send`) and,
 * once the choice has arrived, draws it by its choice whatever the board's move state
 * holds (`placementOf`).
 *
 * The board also says what it is non-visually: columns are labeled lists and cards
 * their items (`structure`), and each grip is named for the column its card now sits
 * in (the card's face). The roles are attributes on authored elements, and the light
 * DOM otherwise stays verbatim, which is what the anchor pass and the version diff
 * walk. A column's heading is the one title the default widgets draw from a `label`,
 * where option cards, board cards and samples show only what their author writes
 * (lf-options.js). The column is a list the board builds, and its heading is that
 * list's name beside its card count. An authored heading would be a child the column's
 * `members` content refuses, and a non-item inside a list a screen reader reads as one
 * of its items. The heading is the module's span, aria-hidden, so the label reaches the
 * tree once, as the list's name, rather than twice; it is two things at once, the words
 * a user selects to comment on the column and the list's name, so it stands in the
 * light DOM as the page speaking (`data-lf-said`), where selection and page search
 * reach it, and generated (`data-lf-gen`), so the diff looks away.
 *
 * How it is drawn: a decorating widget, in light-DOM parts beside the author's children
 * (browser/AGENTS.md, "Renderers"), with no shadow root, since nothing it draws needs
 * one.
 *
 * - The authored children are the author's, and the page's record: each card stands in
 *   the column and at the rank the `move` record places it (the verb's record form), and
 *   the board adds only the roles and headings above.
 * - Each card is an element of its own, `lf-card` (lf-card.js), which draws its grip and
 *   its phone buttons as its own children after the card's words, since they stand
 *   inside the card's box; lf-card.js says why it is not an Effect UI component. The
 *   board's own root draws one hidden node.
 * - The board's component holds what the user is doing (the grab, the drag, the
 *   placement held under the hand) and its `update` turns gestures into Leaf's services
 *   (`RecordAction`, `Announce`). One Mount on that node (`ShowBoard`) does what only a
 *   host's own code can: it places the cards, says the headings and counts, gives each
 *   card its face (the `face` property the card declares, as a host sets
 *   `state`), owns the Sortable instances, holds the page while the user does, and
 *   hears the host's events (a press of a phone button, focus leaving a held grip, a
 *   drag's start and end) as messages.
 *
 * Keys. The grip's rows are the board's, since they read the gesture the board holds:
 * the Mount makes each card's rows once and the card seats them on its grip, where a
 * key scope of one control's own belongs. They read the Mount's latest arguments when a
 * key is pressed. Grabbing says where the card starts and which keys act on it now, so
 * that announcement is the row's own, which has those keys. The page's own keys still
 * work mid-grab, and that is not an oversight: any of them that takes focus off the
 * grip (c into the composer, d to the next Decision) moves the user's current location
 * off it, and that cancels the grab and puts the card back where it was. A held card therefore cannot be stranded by
 * a press that moves the user elsewhere, which is what suspending the page would have
 * been for. */
import Sortable from "/vendor/sortable.esm.js";
import {
  Command,
  Component,
  Effect,
  Html,
  Mount,
  Queue,
  Schema,
  Stream,
  UiSchema,
} from "/vendor/effect-ui.js";
import {
  elementById,
  focusDestination,
  motion,
  move,
  onCurrentLocation,
  scrollerFor,
  scrollIntoView,
  whileConnected,
} from "/runtime/widget-api.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";
import { Announce, RecordAction } from "/runtime/widget-services.js";
import { offer } from "/runtime/lib/controls.js";
import { keeps, keepsText } from "/runtime/lib/keeps.js";
import { PRESS, rowArrows } from "/runtime/lib/keys.js";
import { byRank, rankAt } from "/runtime/lib/rank.js";
import { ANNOUNCE, DeferEvent, HOLD } from "/runtime/lib/widget-events.js";
import { gripOf, ownerOf, type CardFace } from "./lf-card.js";

/** A `choice` value, as the registry's `$data.contracts` declares it. */
const Choice = Schema.Struct({
  value: Schema.String,
  options: Schema.Array(Schema.Struct({ value: Schema.String, label: Schema.String })),
  disabled: Schema.Boolean,
});
type Choice = typeof Choice.Type;

/** Every column's cards in order, by id. */
const Placement = Schema.Record(Schema.String, Schema.Array(Schema.String));
type Placement = Readonly<Record<string, readonly string[]>>;

const Column = Schema.Struct({
  id: Schema.String,
  label: Schema.String,
  value: Schema.String,
});
type Column = typeof Column.Type;

/** A card as the board's inputs read it: its name, the id its `shows` names, and the
 *  choice Leaf set on it. */
const CardInput = Schema.Struct({
  id: Schema.String,
  title: Schema.String,
  shows: Schema.NullOr(Schema.String),
  choice: Schema.NullOr(Choice),
});
type CardInput = typeof CardInput.Type;

const BoardProps = Schema.Struct({
  ...widgetProps,
  host: Schema.optional(Schema.instanceOf(HTMLElement)),
  exhibit: Schema.Boolean,
  columns: Schema.Array(Column),
  cards: Schema.Array(CardInput),
});
type Props = typeof BoardProps.Type;

/** Where a keyboard grab began, which a pointer drag of the same card keeps. */
const Grab = Schema.Struct({
  card: Schema.String,
  from: Schema.String,
  index: Schema.Number,
});

const BoardModel = Schema.Struct({
  // The placement drawn while the user holds a card, else null: the board's drawing
  // is held for the gesture.
  held: Schema.NullOr(Placement),
  grab: Schema.NullOr(Grab),
  // The card a pointer drag holds, which Sortable places itself.
  dragging: Schema.NullOr(Schema.String),
  // The card whose grip the next draw that places it keeps the user on, numbered so
  // each ask is spent once.
  reveal: Schema.NullOr(Schema.Struct({ card: Schema.String, ask: Schema.Number })),
  asks: Schema.Number,
  // The placement a recorded move leaves, with the placement it was recorded from,
  // until the record settles. A draw commits before its Commands run, so the draw that
  // ends the gesture still has the old `state`, and Leaf may set that `state` again
  // before the move's (a card's connecting asks it to); each such draw shows the
  // placement the move leaves, as the move's `state` will, rather than put the card
  // back for one draw. A `state` that places the cards otherwise places them itself,
  // and so does the server's, set again over a refused move.
  landed: Schema.NullOr(Schema.Struct({ placement: Placement, from: Placement })),
});
type Model = typeof BoardModel.Type;

export const BoardMessage = UiSchema.TaggedEnum({
  Grabbed: { card: Schema.String },
  // `crosses`: whether a row step past the column's end continues into the column the
  // step points at, which stands there only where the board stacks its columns.
  Stepped: { column: Schema.Number, row: Schema.Number, crosses: Schema.Boolean },
  Dropped: {},
  Cancelled: { refocus: Schema.Boolean },
  DragStarted: { card: Schema.String },
  DragEnded: { to: Schema.String, index: Schema.Number },
  DragCancelled: {},
  MovedTo: { card: Schema.String, column: Schema.String },
  // The move's record settled, admitted, refused or unrecorded (`landed`).
  Settled: {},
});

/** Ask the widget whose choice `card` shows to pick `value`, from a button the board
 *  makes and keeps out of the page, whose words name the move (`package-data.md`,
 *  "Asking another widget to act"). */
export const AskOwner = Command.make(
  "AskOwner",
  {
    args: {
      host: Schema.instanceOf(HTMLElement),
      card: Schema.String,
      value: Schema.String,
      says: Schema.String,
    },
  },
  ({ host, card, value, says }) =>
    Effect.sync(() => {
      const shown = cardsOf(host).find((candidate) => candidate.id === card);
      const id = shown && ownerOf(shown);
      const owner = shown && id ? elementById(id, shown) : null;
      owner?.dispatchEvent(
        new CommandEvent("command", {
          command: "--choose",
          source: Object.assign(document.createElement("button"), {
            value,
            textContent: says,
          }),
          cancelable: true,
        }),
      );
      return Component.noop;
    }),
);

const columnsOf = (host: Element) => [
  ...host.querySelectorAll<HTMLElement>(":scope > lf-column"),
];
// Own cards only (`:scope` keeps a nested board's cards out).
const cardsOf = (host: Element) => [
  ...host.querySelectorAll<HTMLElement>(":scope > lf-column > lf-card"),
];
const cardsIn = (column: Element) => [
  ...column.querySelectorAll<HTMLElement>(":scope > lf-card"),
];

// Whether `--choose` takes `value`: the empty pick, or the one option carrying it.
const takes = (choice: Choice, value: string) =>
  !value || choice.options.filter((option) => option.value === value).length === 1;

const available = (props: Props) =>
  Boolean(
    (props.state as { move?: { available?: boolean } } | undefined)?.move?.available,
  );

// The board's own move state, which positions every card it places.
const position = (props: Props) => {
  const state = (
    props.state as { move?: { value: Placement; ranks?: Record<string, string> } }
  ).move;
  if (!state || !state.ranks) throw new Error("Board requires positional move state");
  return { value: state.value, ranks: state.ranks };
};

// Where a card showing a choice stands: the first column holding the value the choice
// names, else the first holding none.
const columnFor = (columns: readonly Column[], value: string) =>
  columns.find((column) => column.value === value) ??
  columns.find((column) => column.value === "") ??
  null;

/** Every column's cards in order: the board's own move state, with each card that shows
 *  a choice moved to the column that choice names, or null where Leaf has given the
 *  board no reading, as for a quoted board. Each column lists its cards by rank, which
 *  the authored order and the board's own moves set. */
export function placementOf(props: Props): Placement | null {
  if (props.state === undefined) return null;
  const { value, ranks } = position(props);
  const columns: Record<string, string[]> = Object.fromEntries(
    Object.entries(value).map(([id, cards]) => [id, [...cards]]),
  );
  for (const card of props.cards) {
    const target =
      card.shows && card.choice && columnFor(props.columns, card.choice.value);
    const destination = target && columns[target.id];
    if (!destination) continue;
    for (const cards of Object.values(columns)) {
      const index = cards.indexOf(card.id);
      if (index >= 0) cards.splice(index, 1);
    }
    destination.push(card.id);
  }
  for (const cards of Object.values(columns)) cards.sort(byRank(ranks));
  return columns;
}

const columnOf = (placement: Placement, card: string) =>
  Object.keys(placement).find((id) => placement[id]?.includes(card)) ?? null;

// `placement` with `card` at `index` in `column`, past the column's end where it
// holds fewer.
const samePlacement = (a: Placement, b: Placement) =>
  Object.keys(a).length === Object.keys(b).length &&
  Object.entries(a).every(
    ([column, cards]) =>
      b[column]?.length === cards.length &&
      cards.every((card, index) => b[column]![index] === card),
  );

const withCard = (
  placement: Placement,
  card: string,
  column: string,
  index: number,
) => {
  const next = Object.fromEntries(
    Object.entries(placement).map(([id, cards]) => [
      id,
      cards.filter((c) => c !== card),
    ]),
  );
  next[column]?.splice(index, 0, card);
  return next;
};

// Whether the card can stand in `column`: any column for a card the board places,
// and for a card showing a choice one holding a value its `--choose` takes.
const takesCard = (card: CardInput, column: Column) =>
  !card.shows || Boolean(card.choice && takes(card.choice, column.value));

// A card with `shows` moves when the user can change the choice it shows and a column
// other than its own takes it, so never where it shows none, and every other card when
// the board's own move can. A card no column takes would offer a grip that grabs and
// then moves nowhere.
const movable = (props: Props, card: CardInput, at: string | null) =>
  card.shows
    ? Boolean(
        card.choice &&
        !card.choice.disabled &&
        props.columns.some((column) => column.id !== at && takesCard(card, column)),
      )
    : available(props);

const cardOf = (props: Props, id: string) => props.cards.find((card) => card.id === id);
const labelOf = (props: Props, id: string) =>
  props.columns.find((column) => column.id === id)?.label ?? id;
const titleOf = (props: Props, id: string) => cardOf(props, id)?.title ?? id;

// Where a card stands, in the idiom every arrow step announces.
const where = (props: Props, placement: Placement, card: string) => {
  const column = columnOf(placement, card) ?? "";
  const cards = placement[column] ?? [];
  return `${labelOf(props, column)}, position ${cards.indexOf(card) + 1} of ${cards.length}`;
};

const announce = (words: string) => Announce.make({ words }).pipe(Command.asNoop);

const released = { held: null, grab: null, dragging: null };

// One completed move, drag or keyboard: the card's rank among the destination's
// other cards as the board shows them now, sent once, so the move stays put whichever
// other moves stand. The gesture's name follows the branch the user can see — a card
// kept in its column was reordered, not moved to where it already was. A card showing
// a choice asks its owner instead, and a move within its column asks for nothing.
function send(
  $: { props: Props; evolve: (m: Partial<Model>) => any; model: Model },
  next: Partial<Model>,
  card: string,
  from: string,
  to: string,
  index: number,
) {
  const props = $.props;
  const step = $.evolve(next);
  const shown = cardOf(props, card);
  const label = labelOf(props, to);
  if (shown?.shows) {
    if (to === from || !props.host) return step;
    return step.run(
      AskOwner.make({
        host: props.host,
        card,
        value: props.columns.find((column) => column.id === to)?.value ?? "",
        says: `Moved “${titleOf(props, card)}” to ${label}`,
      }),
    );
  }
  const current = placementOf(props);
  if (!current) return $.evolve(next);
  const placement = Object.fromEntries(
    Object.entries(current).map(([column, cards]) => {
      const rest = cards.filter((id) => id !== card);
      return [column, column === to ? rest.toSpliced(index, 0, card) : rest];
    }),
  );
  return $.evolve({ ...next, landed: { placement, from: current } }).run(
    RecordAction.make({
      verb: "move",
      detail: {
        unit: card,
        value: to,
        // Among the cards as the board shows them, those standing by a choice included.
        rank: rankAt({ ...position(props), value: current }, to, index, card),
      },
      says: `${to === from ? "Reordered in" : "Moved to"} ${label}`,
    }).pipe(Command.as(BoardMessage.Settled())),
  );
}

const revealing = (model: Model, card: string) => ({
  reveal: { card, ask: model.asks + 1 },
  asks: model.asks + 1,
});

export const Board = Html.component({
  name: "Board",
  props: BoardProps,
  model: BoardModel,
  message: BoardMessage,
}).make({
  init: () => ({
    held: null,
    grab: null,
    dragging: null,
    reveal: null,
    asks: 0,
    landed: null,
  }),
  update: {
    // One gesture at a time: a grab, or a pointer drag under way, holds the board.
    Grabbed: ($, { card }) => {
      const props = $.props;
      const placement = placementOf(props);
      const shown = cardOf(props, card);
      const from = placement && columnOf(placement, card);
      if ($.model.held || !placement || !from || !shown) return $.model;
      if (!movable(props, shown, from)) return $.model;
      const index = placement[from]?.indexOf(card) ?? 0;
      return $.evolve({ held: placement, grab: { card, from, index }, reveal: null });
    },
    // Up and Down move the card within its column, and past its end into the column
    // the step points at where that stands there. Left and Right move it to the
    // previous or next column that takes it, at the same index, past the target's end
    // where it holds fewer.
    Stepped: ($, { column: dCol, row: dRow, crosses }) => {
      const { held, grab } = $.model;
      const props = $.props;
      const shown = grab && cardOf(props, grab.card);
      const col = held && grab && columnOf(held, grab.card);
      if (!held || !grab || !shown || !col) return $.model;
      const cards = held[col] ?? [];
      const at = cards.indexOf(grab.card);
      let target: string | undefined;
      let index: number;
      if (dRow) {
        if (at + dRow >= 0 && at + dRow < cards.length) {
          target = col;
          index = at + dRow;
        } else {
          const ids = props.columns.map((column) => column.id);
          target = crosses ? ids[ids.indexOf(col) + dRow] : undefined;
          index =
            dRow > 0
              ? 0
              : (held[target ?? ""] ?? []).filter((c) => c !== grab.card).length;
        }
      } else {
        const ids = props.columns
          .filter((column) => column.id === col || takesCard(shown, column))
          .map((column) => column.id);
        target = ids[ids.indexOf(col) + dCol];
        index = at;
      }
      if (!target) return $.model;
      const next = withCard(held, grab.card, target, index);
      return $.evolve({ held: next, ...revealing($.model, grab.card) }).run(
        announce(`${shown.title} — ${where(props, next, grab.card)}`),
      );
    },
    Dropped: ($) => {
      const { held, grab } = $.model;
      const to = held && grab && columnOf(held, grab.card);
      if (!held || !grab || !to) return $.model;
      const index = held[to]?.indexOf(grab.card) ?? 0;
      if (to === grab.from && index === grab.index) return $.evolve(released);
      return send($, released, grab.card, grab.from, to, index);
    },
    // Escape keeps focus and returns the view to the origin. Focus leaving restores the
    // card without taking the viewport from the control the user deliberately entered.
    Cancelled: ($, { refocus }) => {
      const { grab } = $.model;
      if (!grab) return $.model;
      return $.evolve({
        ...released,
        ...(refocus ? revealing($.model, grab.card) : { reveal: null }),
      }).run(announce(`${titleOf($.props, grab.card)} — move cancelled`));
    },
    // A pointer drag supersedes a live keyboard grab. Dragging the grabbed card folds the
    // grab's origin into the drag, so unsent arrow steps become part of the one recorded
    // move; dragging another card lets the grab go, and its card returns as the drag
    // ends.
    DragStarted: ($, { card }) => {
      const placement = $.model.held ?? placementOf($.props);
      if (!placement) return $.model;
      const grab = $.model.grab?.card === card ? $.model.grab : null;
      return $.evolve({ held: placement, grab, dragging: card, reveal: null });
    },
    DragEnded: ($, { to, index }) => {
      const { held, dragging, grab } = $.model;
      if (!held || !dragging) return $.evolve(released);
      const from = grab?.from ?? columnOf(held, dragging);
      const was = grab?.index ?? held[from ?? ""]?.indexOf(dragging);
      if (!from || (from === to && was === index)) return $.evolve(released);
      return send($, released, dragging, from, to, index);
    },
    DragCancelled: ($) => {
      const { dragging } = $.model;
      if (!dragging) return $.model;
      return $.evolve({ ...released, ...revealing($.model, dragging) }).run(
        announce(`${titleOf($.props, dragging)} — move cancelled`),
      );
    },
    // A phone's button moves the card to the end of the column it names, and the view
    // and the user with it.
    MovedTo: ($, { card, column }) => {
      const props = $.props;
      const placement = placementOf(props);
      const shown = cardOf(props, card);
      const from = placement && columnOf(placement, card);
      const target = props.columns.find((c) => c.id === column);
      if ($.model.held || !placement || !from || !shown || !target || from === column)
        return $.model;
      if (!movable(props, shown, from) || !takesCard(shown, target)) return $.model;
      const index = (placement[column] ?? []).filter((c) => c !== card).length;
      return send($, revealing($.model, card), card, from, column, index);
    },
    Settled: ($) => ($.model.landed ? $.evolve({ landed: null }) : $.model),
  },
  view: (h, model) => {
    const props = h.props;
    const recorded = placementOf(props);
    const placement =
      model.held ??
      (model.landed && recorded && samePlacement(recorded, model.landed.from)
        ? model.landed.placement
        : recorded);
    const faces: Record<string, Omit<CardFace, "keys">> = {};
    if (!props.exhibit)
      for (const card of props.cards) {
        const at = placement ? columnOf(placement, card.id) : null;
        const can = movable(props, card, at);
        faces[card.id] = {
          title: card.title,
          name: `Move: ${card.title} — ${at ? labelOf(props, at) : ""}`,
          movable: can,
          held: model.grab?.card === card.id,
          destinations:
            props.columns.length < 2
              ? []
              : props.columns
                  .filter((column) => column.id !== at && takesCard(card, column))
                  .map((column) => ({ column: column.id, label: column.label })),
        };
      }
    return h.span.attr("hidden", "").onMount(
      ShowBoard({
        show: {
          exhibit: props.exhibit,
          placement,
          faces,
          grab: model.grab,
          dragging: model.dragging,
          holding: model.held !== null,
          reveal: model.reveal,
          shows: Object.fromEntries(
            props.cards.map((card) => [card.id, Boolean(card.shows)]),
          ),
          titles: Object.fromEntries(props.cards.map((card) => [card.id, card.title])),
          labels: Object.fromEntries(
            props.columns.map((column) => [column.id, column.label]),
          ),
        },
      }),
    );
  },
});

type Show = {
  exhibit: boolean;
  placement: Placement | null;
  faces: Record<string, Omit<CardFace, "keys">>;
  grab: typeof Grab.Type | null;
  dragging: string | null;
  holding: boolean;
  reveal: { card: string; ask: number } | null;
  shows: Record<string, boolean>;
  titles: Record<string, string>;
  labels: Record<string, string>;
};
type Send = (message: typeof BoardMessage.Type) => void;

// What a board is, said in roles: each column a labeled list, each card an item in it.
// What says so visually is boxes side by side — geometry, which the accessibility tree
// doesn't carry — so without this a board is one flat run of cards and Move buttons,
// and which column a card is in, the one fact about it not in its own text, is never
// announced. Roles describe rather than afford, so this holds for a quoted board too:
// an exhibit is read like anything else, it just takes no input.
function structure(host: HTMLElement) {
  for (const column of columnsOf(host)) {
    keeps(column, "role", "list");
    keeps(column, "aria-label", column.getAttribute("label"));
    for (const card of cardsIn(column)) keeps(card, "role", "listitem");
    if (column.querySelector(":scope > .lf-column-name")) continue;
    const heading = document.createElement("span");
    heading.className = "lf-column-name";
    keeps(heading, "data-lf-gen", "1");
    heading.toggleAttribute("data-lf-said", true);
    // The column already carries these words as its name, so the heading is the
    // visible half only: the tree hears them once, the user can still select them, and
    // the theme's generated copy is left to the no-script case.
    heading.setAttribute("aria-hidden", "true");
    heading.textContent = column.getAttribute("label");
    // How many cards stand in the column, beside its heading rather than in it, so the
    // heading's words stay the column's name. Generated like the heading, and quotable
    // like it: a figure the user can see is one they can point at. The list already
    // tells a screen reader its length, so it is the visible half only.
    const count = document.createElement("span");
    count.className = "lf-column-count";
    keeps(count, "data-lf-gen", "1");
    count.setAttribute("aria-hidden", "true");
    column.prepend(heading);
    heading.after(count);
  }
}

// Place every card where `placement` says, measuring once around the placement so
// FLIP animates the resulting layout together, from where each card paints now, so a
// reversal continues where the user sees the card. The card the user is moved with is
// revealed before FLIP puts its paint back at the old box; the reveal's glide and the
// card's motion then run together. Returns whether `reveal` moved.
function arrange(host: HTMLElement, placement: Placement, reveal: string | null) {
  const columns = new Map(columnsOf(host).map((column) => [column.id, column]));
  const cards = new Map(cardsOf(host).map((card) => [card.id, card]));
  // The columns whose cards stand otherwise than the placement says. Only their cards
  // move, so only theirs are measured and carried (FLIP).
  const changed = [...columns].filter(([id, column]) => {
    const order = placement[id] ?? [];
    const current = cardsIn(column);
    return (
      current.length !== order.length || current.some((card, i) => card.id !== order[i])
    );
  });
  if (!changed.length) return false;
  const shown = reveal ? cards.get(reveal) : undefined;
  const origin = shown && [
    shown.parentElement,
    cardsIn(shown.parentElement!).indexOf(shown),
  ];
  const first = new Map(
    changed.flatMap(([id]) =>
      (placement[id] ?? []).flatMap((cardId) => {
        const card = cards.get(cardId);
        if (!card) return [];
        const painted = card.getBoundingClientRect();
        for (const animation of card.getAnimations()) animation.cancel();
        return [[card, painted] as const];
      }),
    ),
  );
  for (const [id, column] of changed) {
    // Each card goes before the one standing where the next belongs, read once from
    // the column's children rather than again for every card.
    const order = (placement[id] ?? []).flatMap((cardId) => cards.get(cardId) ?? []);
    let next: Element | null = column.querySelector(":scope > lf-card");
    for (const card of order) {
      if (card !== next) move(column, card, next);
      else next = card.nextElementSibling;
      while (next && next.localName !== "lf-card") next = next.nextElementSibling;
    }
  }
  const moved =
    shown &&
    origin &&
    (origin[0] !== shown.parentElement ||
      origin[1] !== cardsIn(shown.parentElement!).indexOf(shown));
  if (shown && moved) {
    const grip = gripOf(shown);
    if (grip) focusDestination(grip, "return");
    scrollIntoView(shown, { behavior: "smooth", block: "nearest" });
  }
  const movements: Promise<unknown>[] = [];
  for (const [card, before] of first) {
    const last = card.getBoundingClientRect();
    const dx = before.left - last.left;
    const dy = before.top - last.top;
    if (dx || dy) {
      const played = motion(
        card,
        [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }],
        150,
      );
      if (played) movements.push(played.finished);
    }
  }
  const layout = () =>
    host.dispatchEvent(new CustomEvent("lf-layout", { bubbles: true, composed: true }));
  layout();
  if (movements.length) void Promise.allSettled(movements).then(layout);
  return Boolean(moved);
}

// The grip's rows for one card, made once and reading the board as it stands when a
// key is pressed.
function rowsFor(host: HTMLElement, card: HTMLElement, latest: () => Show, send: Send) {
  const id = card.id;
  const held = () => latest().grab?.card === id;
  const face = () => latest().faces[id];
  // Columns run the way the page's words do, so left is the previous column only in
  // left-to-right text; the title names the column, which holds whichever way the board
  // lays them out.
  const [back] = rowArrows(host);
  const column = (binding: string) =>
    `Move it to the ${binding === back ? "previous" : "next"} column`;
  // A card showing a choice only changes column, so it has no up or down.
  const routes = [
    { id: "board.move-up", binding: "ArrowUp", title: "Move it up" },
    { id: "board.move-down", binding: "ArrowDown", title: "Move it down" },
    { id: "board.move-left", binding: "ArrowLeft", title: column("ArrowLeft") },
    { id: "board.move-right", binding: "ArrowRight", title: column("ArrowRight") },
  ].slice(latest().shows[id] ? 2 : 0);
  const rows: NonNullable<HTMLElement["lfCommands"]>["rows"] = [
    {
      id: "board.grab",
      keys: PRESS,
      title: "grab the card",
      when: () => Boolean(face()?.movable) && !latest().holding,
      run: () => {
        // Where the card starts, in the idiom every arrow step announces — a user about
        // to move it needs the position the moves count from — and the keys that act
        // on it now.
        const { placement, titles } = latest();
        if (!placement) return;
        const from = columnOf(placement, id) ?? "";
        const cards = placement[from] ?? [];
        window.dispatchEvent(
          new CustomEvent(ANNOUNCE, {
            detail: {
              words: `${titles[id]} grabbed — ${latest().labels[from]}, position ${
                cards.indexOf(id) + 1
              } of ${cards.length}`,
              rows,
            },
          }),
        );
        send(BoardMessage.Grabbed({ card: id }));
      },
    },
    {
      id: "board.move",
      keys: routes.map((route) => route.binding),
      routes,
      label: "arrows",
      title: "move",
      when: held,
      repeat: true,
      // The card goes where it is moved, and the view and the user with it.
      travels: true,
      runKey: (binding: string) => {
        const [back, ahead] = rowArrows(host);
        const row = binding === "ArrowUp" ? -1 : binding === "ArrowDown" ? 1 : 0;
        send(
          BoardMessage.Stepped({
            column: binding === back ? -1 : binding === ahead ? 1 : 0,
            row,
            crosses: Boolean(row) && stacked(card, row),
          }),
        );
      },
    },
    {
      id: "board.drop",
      keys: PRESS,
      title: "drop",
      when: held,
      run: () => send(BoardMessage.Dropped()),
    },
    {
      id: "board.cancel",
      keys: ["Escape"],
      title: "cancel the move",
      travels: true,
      when: () => held() || latest().dragging === id,
      run: () => {
        // Sortable owns drag teardown; the cancel ends it through the dependency's
        // drag-end handler, and `onEnd` restores rather than records.
        const drag = Sortable.active;
        if (drag && drag.el.closest("lf-board") === host && latest().dragging === id)
          drag.handleEvent(new CustomEvent("dragend", { detail: "cancel" }) as never);
        else send(BoardMessage.Cancelled({ refocus: true }));
      },
    },
  ];
  return rows;
}

// Whether the column a row step past the end of `card`'s column points at stands on
// that side of it, as it does where the board stacks its columns; side by side,
// nothing stands there and the card stays.
function stacked(card: HTMLElement, row: number) {
  const column = card.parentElement;
  const columns = column?.parentElement ? columnsOf(column.parentElement) : [];
  const beside = column && columns[columns.indexOf(column) + row];
  if (!column || !beside) return false;
  const here = column.getBoundingClientRect();
  const there = beside.getBoundingClientRect();
  return row > 0 ? there.top >= here.bottom - 1 : there.bottom <= here.top + 1;
}

/** What the board states on the author's elements, kept by its root's one mount. */
class BoardLight {
  #latest: Show | null = null;
  #sortables = new Set<Sortable>();
  #rows = new WeakMap<HTMLElement, ReturnType<typeof rowsFor>>();
  #faces = new WeakMap<HTMLElement, string>();
  #lifted: HTMLElement | null = null;
  #revealed = 0;
  #hold: PromiseWithResolvers<void> | null = null;
  #stopMotion: (() => void) | null = null;
  #stopLocation: () => void;

  readonly host: HTMLElement;
  readonly send: Send;

  constructor(host: HTMLElement, send: Send) {
    this.host = host;
    this.send = send;
    host.toggleAttribute("data-lf-scroll", true);
    host.addEventListener("click", this.#click);
    this.#stopLocation = onCurrentLocation(this.#left);
  }

  close() {
    this.host.removeEventListener("click", this.#click);
    this.#stopLocation();
    this.#stopMotion?.();
    for (const sortable of this.#sortables) sortable.destroy();
    this.#sortables.clear();
    this.#holding(false);
  }

  show(show: Show) {
    const first = !this.#latest;
    this.#latest = show;
    const { host } = this;
    structure(host);
    if (show.exhibit) return;
    if (first) this.#sortable();
    if (show.placement && !show.dragging) {
      const reveal =
        show.reveal && show.reveal.ask !== this.#revealed ? show.reveal : null;
      if (arrange(host, show.placement, reveal?.card ?? null) && reveal)
        this.#revealed = reveal.ask;
    }
    for (const column of columnsOf(host))
      keepsText(
        column.querySelector(":scope > .lf-column-count"),
        cardsIn(column).length,
      );
    const cards = cardsOf(host);
    for (const card of cards) {
      const face = show.faces[card.id];
      if (!face) continue;
      const keys =
        this.#rows.get(card) ?? rowsFor(host, card, () => this.#latest!, this.send);
      this.#rows.set(card, keys);
      const said = JSON.stringify(face);
      if (this.#faces.get(card) === said) continue;
      this.#faces.set(card, said);
      (card as HTMLElement & { face?: CardFace }).face = { ...face, keys };
    }
    const lifted = show.grab
      ? (cards.find((card) => card.id === show.grab?.card) ?? null)
      : null;
    if (lifted !== this.#lifted) {
      this.#lifted?.classList.remove("lf-lift");
      lifted?.classList.add("lf-lift");
      this.#lifted = lifted;
    }
    const any = cards.some((card) => show.faces[card.id]?.movable);
    for (const sortable of this.#sortables) sortable.option("disabled", !any);
    this.#holding(show.holding);
  }

  // The user's hold through the gesture, settled as the card is put down: `lf-hold`
  // keeps revisions and undo off the cards under the hand, and `lf-defer` says the board
  // holds its drawing, so Leaf counts what it set meanwhile as drawn once the hold ends.
  #holding(on: boolean) {
    if (on && !this.#hold) {
      const hold = (this.#hold = Promise.withResolvers<void>());
      this.host.dispatchEvent(new DeferEvent(hold.promise));
      this.host.dispatchEvent(
        Object.assign(new Event(HOLD, { bubbles: true, composed: true }), {
          complete: hold.promise,
        }),
      );
    } else if (!on && this.#hold) {
      this.#hold.resolve();
      this.#hold = null;
    }
  }

  // A press of a phone button asks for its column.
  #click = (event: MouseEvent) => {
    const [target] = event.composedPath();
    const button =
      target instanceof Element
        ? target.closest<HTMLElement>(".lf-board-destination")
        : null;
    const card = button?.closest("lf-card");
    const column = button?.dataset.lfBoardTarget;
    if (!card || !column || card.closest("lf-board") !== this.host) return;
    this.send(BoardMessage.MovedTo({ card: card.id, column }));
  };

  // Leaving the grip drops the grab: restore the origin. A move that keeps focus on the
  // grip, and the window losing focus, tell no new location; a drop, focus falling to
  // the body as a change takes its node away, leaves the user where they were
  // (dom/focus.js, `onCurrentLocation`).
  #left = (node: Element | null, cause: string, left: Element | null) => {
    const grabbed = this.#latest?.grab?.card;
    if (!grabbed || cause === "drop" || node === left || !left?.matches(".lf-grip"))
      return;
    const card = left.closest<HTMLElement>("lf-card");
    if (
      card &&
      card.id === grabbed &&
      gripOf(card) === left &&
      cardsOf(this.host).includes(card)
    )
      this.send(BoardMessage.Cancelled({ refocus: false }));
  };

  #sortable() {
    const { host } = this;
    const scroller = scrollerFor(host);
    const group = `board-${host.id}`;
    for (const column of columnsOf(host))
      this.#sortables.add(
        new Sortable(column, {
          disabled: true,
          // Named per board, so two boards on a page don't cross-drag. A column opens a
          // slot only for a card it takes, as the arrows and the phone buttons offer it.
          // Sortable asks this of every column but the one the drag began in, which
          // always takes its card back. A column that takes the card answers with the
          // groups it takes from, which Sortable matches against the board the drag
          // began in; `true` would take a card from any board.
          group: {
            name: group,
            put: (to, _from, card) =>
              this.#latest?.faces[card.id]?.destinations.some(
                (d) => d.column === to.el.id,
              )
                ? [group]
                : false,
          },
          draggable: "lf-card",
          handle: ".lf-grip",
          // Sortable passes null for a press on no card, such as a column's heading,
          // which starts no drag.
          filter: (_event, card) => !card || !this.#latest?.faces[card.id]?.movable,
          preventOnFilter: false,
          // Named because a board an agent sent in a reply is scrolled by the panel's
          // list, while one in the page is scrolled by the browser root. Sortable cannot
          // infer that product boundary from the board alone.
          scroll: scroller instanceof HTMLElement ? scroller : false,
          forceFallback: true, // pointer-driven label preview, including touch
          // The image under the pointer carries the card's label, never a second live
          // widget tree: no copied form groups, widget lifetimes or iframes.
          cloneElement: (card: HTMLElement) => {
            const preview = offer(
              "div",
              "lf-motion-preview",
              this.#latest?.titles[card.id],
            );
            preview.inert = true;
            preview.setAttribute("aria-hidden", "true");
            return preview;
          },
          fallbackTolerance: 4, // a click on the grip stays a click
          delay: 120,
          delayOnTouchOnly: true, // touch arms by press-hold so scrolling stays free
          direction: "vertical",
          swapThreshold: 0.65, // hysteresis: boundaries don't flip-flop under a still pointer
          emptyInsertThreshold: 12,
          ghostClass: "lf-ghost", // the in-flow slot the drop would fill
          chosenClass: "lf-lift", // the pressed card
          dragClass: "lf-inhand", // the follower under the pointer
          onStart: (evt) => {
            this.send(BoardMessage.DragStarted({ card: evt.item.id }));
            // The held card owns the keyboard too, through its grip's scope.
            const grip = gripOf(evt.item);
            if (grip) focusDestination(grip, "return");
          },
          // The *draggable* index counts cards; Sortable's plain newIndex counts every
          // element child, and a column's first children are its heading and count.
          onEnd: (evt) => {
            const event = evt.originalEvent;
            if (
              event?.type === "pointercancel" ||
              event?.type === "touchcancel" ||
              (event instanceof CustomEvent && event.detail === "cancel")
            )
              this.send(BoardMessage.DragCancelled());
            else
              this.send(
                BoardMessage.DragEnded({
                  to: evt.to.id,
                  index: evt.newDraggableIndex ?? 0,
                }),
              );
          },
        }),
      );
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    const animate = () => {
      for (const sortable of this.#sortables)
        sortable.option("animation", reduced.matches ? 0 : 150);
    };
    animate();
    reduced.addEventListener("change", animate);
    this.#stopMotion = () => reduced.removeEventListener("change", animate);
  }
}

const ShowBoard = Mount.makeStream(
  "ShowBoard",
  { args: { show: Schema.Unknown } },
  (node: HTMLElement, { show }, changes) =>
    Stream.callback<typeof BoardMessage.Type>((queue) =>
      Effect.gen(function* () {
        const host = node.closest("lf-board") as HTMLElement;
        const light = new BoardLight(host, (message) =>
          Queue.offerUnsafe(queue, message),
        );
        light.show(show as Show);
        yield* Effect.addFinalizer(() => Effect.sync(() => light.close()));
        yield* Effect.forkScoped(
          Stream.runForEach(changes, (next) =>
            Effect.sync(() => light.show(next.show as Show)),
          ),
        );
      }),
    ),
);

// The board reads its cards again as one says its choice moved (lf-card.js).
const hearing = new WeakSet<Element>();

defineWidget("lf-board", Board, {
  inputs: (board, reread) => {
    if (!hearing.has(board)) {
      hearing.add(board);
      whileConnected(board, (signal: AbortSignal) =>
        board.addEventListener("change", reread, { capture: true, signal }),
      );
    }
    return {
      host: board,
      // A quoted board is an exhibit: no grips, no sortable, no grip keys in the command
      // reference dialog — it stays the static board the theme renders anyway.
      exhibit: board.matches("[data-lf-exhibit] *"),
      columns: columnsOf(board).map((column) => ({
        id: column.id,
        label: column.getAttribute("label") ?? "",
        value: column.getAttribute("value") ?? "",
      })),
      cards: cardsOf(board).map((card) => {
        // The id a card's `shows` names, or null for a card that shows no choice: one
        // without the attribute, or with it empty.
        const shows = card.getAttribute("shows") || null;
        const choice = (card as HTMLElement & { choice?: Choice | null }).choice;
        return {
          id: card.id,
          title: card.getAttribute("label")?.trim() || card.id,
          shows,
          choice: (shows && choice) || null,
        };
      }),
    };
  },
});
