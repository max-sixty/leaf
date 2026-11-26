/* lf-board: the one widget the user edits directly, with every move sharing one send
 * path and one gesture gate. Dragging is wired via the vendored SortableJS
 * (pointer-driven `forceFallback` mode, so the follower is stylable — native HTML5 DnD
 * is not used). A short label follows the pointer; native state stays in the real
 * card. Phones show each card's other columns as direct move buttons instead: the
 * board stacks its columns there (board.css), so another column is a long press-hold
 * drag through autoscroll away, and the buttons name every destination where the card is.
 * The grip is a press (`offer`), so the keyboard path needs no pointer: Enter grabs,
 * arrows restate the card's placement (announced through the live region), Enter drops,
 * and Escape or focus loss restores the origin. Left and Right change column, named for
 * the column rather than a direction, since on a stacked board the next column stands
 * below; there Down past a column's last card continues into the column below and Up
 * past its first into the one above, the next slot the user sees (#step). Escape also
 * cancels a pointer drag.
 * For the whole gesture the board says the user holds a card (`lf-hold`), so no new
 * revision or undo replaces the cards under the hand, and defers its own drawing
 * (`defer`), so no foreign move replays mid-gesture; a completed move
 * reports through #send as one ranked `move` action, indistinguishable on
 * the wire. Its render receives every column's final ordered card ids. One render
 * preserves native nodes, syncs a second tab, and no-ops on the sender. Presentation is theme CSS; authored content
 * is never replaced, so there is no failSoft.
 *
 * A card with `shows` is the board's view of another widget's answer (`shownAnswer`),
 * such as a proposal's pick in its own section, and the answer stays that widget's. The
 * board draws the card in the column whose `value` the answer names, read from the
 * widget's state in this render, so a pick there, an undo, a refusal and a revision's
 * retraction move the card with no state of the board's own. Dropping it in another
 * column sends the widget's own answer for that column's value, the same command the
 * section's control sends. Where the answer picks members, a column with a `value`
 * takes a drop, and offers a button, only when exactly one member carries that value:
 * with none there is no answer to send, and with several a drop wouldn't say which. A
 * card that no other column takes has its grip disabled. A card with `shows` keeps its
 * authored order, and the arrows only change its column: an order of the board's own
 * would be a second fact placed among columns the answer decides.
 *
 * Only this module holds a card to the answer it shows. The registry declares `shows`
 * as an attribute naming an element (`refers`), so `page check` and message admission
 * require only that the element exists, and the append door admits a board move of
 * such a card. The board therefore never sends its own move for one (#movable, #send)
 * and draws it by its answer whatever the board's move state holds. A card whose
 * `shows` names no answer the board can show stands where the markup puts it and takes
 * no move, and the board reports it to the author as the page's error, as it reports a
 * card naming a widget none of whose members carries a `value` (#reportUnshown).
 * Nothing draws a message before the user opens its thread, so there the user meets
 * such a card before the author hears of it.
 *
 * The user chose this over keeping the same rules in `page check` and the append door:
 * a fact is declared only where Leaf must act on it without the module and the module
 * can't keep the rule itself (`browser/AGENTS.md`, "The widget vocabulary stays open").
 * A change that wants the static refusal back can give `shows` a typed `refers`
 * contract, which `page check` and message admission already hold, at the cost of a
 * registry map listing each widget a card may show. Two other designs fail: an Answer
 * record, or a value on the question's group, moves the answer off the widget that owns
 * its words, options and obligation; and a field on the event naming the view that
 * sent it is bookkeeping no reader needs, since the widget's own declaration admits or
 * refuses the value alone.
 *
 * An answer names a value when it is one string: a `value` record's attribute, or the
 * members an `attribute` record picks when every one of them carries the same `value`
 * attribute, as an `lf-option`'s does. An empty pick, a member without one (an option
 * the user wrote in) or members naming different values name none, and the card then
 * stands in the first column without a `value`, as it does when no column holds the
 * value named.
 *
 * The board also says what it is non-visually: columns are labeled lists and
 * cards their items (#structure), and each grip is named for the column its
 * card now sits in (#names). Both are attributes on authored elements — the
 * light DOM stays verbatim, which is what the anchor pass and the version diff
 * walk. The column's heading is the module's span, aria-hidden, so the label
 * reaches the tree once, as the list's name, rather than twice.
 *
 * A column's heading is the one title the default widgets draw from a `label`, where
 * option cards, board cards and samples show only what their author writes
 * (lf-options.js). The column is a list the board builds, and its heading is that
 * list's name beside its card count. An authored heading would be a child the column's
 * `members` content refuses, and a non-item inside a list a screen reader reads as one
 * of its items. */
import Sortable from "/vendor/sortable.esm.js";
import { nothing } from "/vendor/lit.js";
import {
  elementById,
  move,
  motion,
  scrollerFor,
  focusDestination,
  scrollIntoView,
  whileConnected,
  layerFact,
  widgetController,
} from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { offer, offerAction } from "/runtime/lib/controls.js";
import { PRESS, rowArrows } from "/runtime/lib/keys.js";
import { keeps, keepsText } from "/runtime/lib/keeps.js";
import { byRank, rankAt } from "/runtime/lib/rank.js";

// The attribute naming an answer: on a column, the answer the column holds, and on a
// member a widget's answer picks, the answer that pick gives.
const VALUE = "value";

// The value `answer` names, given the reading of the members it picks.
/** @param {unknown} answer @param {((id: string) => string | null) | null} valueOf */
const namedValue = (answer, valueOf) => {
  if (!valueOf) return typeof answer === "string" && answer ? answer : null;
  /** @type {unknown[]} */
  const members = Array.isArray(answer) ? answer : [];
  const values = new Set(
    members.map((member) => {
      if (typeof member !== "string")
        throw new Error("A picked answer must name its members by id");
      return valueOf(member);
    }),
  );
  const [only, other] = values;
  return only !== undefined && other === undefined ? only : null;
};

// The id a card's `shows` names, or null for a card that shows no answer: one without
// the attribute, or with it empty.
/** @param {Element} card */
const showsId = (card) => card.getAttribute("shows") || null;

/** The widget whose answer a card shows, with the verb that writes the answer and
 * that verb's record; `{fault}`, telling the author what to write instead, where the
 * card's `shows` names no answer a board can show; or null for a card that shows none.
 * A board can show the answer of a widget whose `awaits.value` verb records a value or
 * members, in the card's own message first, then on the page. */
/** @param {Element} card */
function shownWidget(card) {
  const id = showsId(card);
  if (id === null) return null;
  const owner = elementById(id, card);
  if (!owner)
    return {
      fault:
        `shows="${id}" names no element beside the card; a card shows a widget on` +
        " the page, or in the message that holds it",
    };
  const declaration = layerFact(owner.localName);
  const verb = declaration?.awaits?.value;
  const record = verb ? declaration?.verbs?.[verb]?.record : undefined;
  if (!verb || (record?.kind !== "value" && record?.kind !== "attribute"))
    return {
      fault:
        `shows="${id}" names <${owner.localName}>, which has no answer a board can` +
        " show; name the widget the user answers, such as a question's <lf-options>",
    };
  return { owner, verb, record };
}

/** What to tell the author of a card showing a widget whose answer picks members when
 * none of them carries a `value`, so no pick can put the card in a column; null
 * otherwise, and while the widget's state has not loaded. */
/** @param {Element} card @param {Exclude<ReturnType<typeof shownWidget>, null | {fault: string}>} shown */
function valuelessFault(card, { owner, record }) {
  if (record.kind !== "attribute") return null;
  const members = widgetController(owner).read().memberships[record.attr];
  if (!members?.length) return null;
  return members.some((member) => elementById(member, owner)?.hasAttribute(VALUE))
    ? null
    : `shows="${showsId(card)}" names <${owner.localName}>, none of whose members ` +
        `carries a \`${VALUE}\`, so no pick puts the card in a column; give each ` +
        `member the \`${VALUE}\` of the column its pick belongs in`;
}

/** The answer a card shows, or null where it shows none: no `shows`, one naming no
 * answer a board can show (`shownWidget`), or a widget whose state has not loaded.
 * Reading it reads that widget's own published state, and changing it sends the
 * widget's own command through its controller, the same command its own control sends.
 * `render()` follows that reading, so the board draws again when the answer changes.
 * The widget's own `state` property holds the same answer, but nothing tells the
 * board when Leaf sets it.
 * `value` is the value the answer names now (null for none), `available` whether the
 * user can change it, `takes(value)` whether the widget can answer `value` (null
 * clears a pick), and `answer(value, says)` sends the widget's command, returning
 * what `dispatch` returns, or null where the widget can't take `value`. */
/** @param {Element} card */
function shownAnswer(card) {
  const shown = shownWidget(card);
  if (!shown || "fault" in shown) return null;
  const { owner, verb, record } = shown;
  const controller = widgetController(owner);
  const reading = controller.read();
  const state = reading.state[verb];
  if (!state) return null;
  const valueOf =
    record.kind === "attribute"
      ? (/** @type {string} */ member) =>
          elementById(member, owner)?.getAttribute(VALUE) ?? null
      : null;
  const detailFor = (/** @type {string | null} */ value) => {
    if (!valueOf) return value === null ? null : { value };
    if (value === null) return { value: [] };
    // The one member carrying `value` is the answer. Where several carry it, as two
    // options that land a card in one column do, `value` doesn't say which of them the
    // user picks, so the widget takes no answer for it and the user picks among them
    // in the widget itself. Answering with the first, or with all of them, would
    // record a pick the user never made.
    const members = (reading.memberships[record.attr] ?? []).filter(
      (member) => valueOf(member) === value,
    );
    return members.length === 1 ? { value: members } : null;
  };
  return Object.freeze({
    value: namedValue(state.value, valueOf),
    available: Boolean(reading.actions[verb]?.available),
    takes: (/** @type {string | null} */ value) => detailFor(value) !== null,
    /** @param {string | null} value @param {string} [says] */
    answer(value, says) {
      const detail = detailFor(value);
      return detail
        ? controller.dispatch({ kind: "action", verb, detail, ...(says && { says }) })
        : null;
    },
  });
}

customElements.define(
  "lf-board",
  class extends LeafElement {
    /** @typedef {Element & {parentElement: HTMLElement}} BoardCard */
    /** @typedef {{card: BoardCard, grip: HTMLElement, from: HTMLElement, index: number}} Grab */
    /** @type {Grab | null} */
    #grabbed = null; // {card, grip, from, index} — the origin, for cancel and no-op drops
    /** @type {Grab | null} */
    #superseded = null; // a grab folded into a pointer drag of the same card (see onStart)
    /** @type {MutationObserver | null} */
    #namesObserver = null;
    /** @type {Set<Sortable>} */
    #sortables = new Set();
    /** @type {(() => void) | null} */
    #resumeProjection = null;
    // The user's hold through the gesture, settled as the card is put down.
    /** @type {PromiseWithResolvers<void> | null} */
    #held = null;
    // The fault last reported for each card, so the author hears of it once rather
    // than at every draw.
    /** @type {WeakMap<Element, string>} */
    #reported = new WeakMap();

    setup() {
      this.toggleAttribute("data-lf-scroll", true);
      this.#structure();
      // A quoted board is an exhibit: no grips, no sortable, no grip keys in
      // the command reference dialog — it stays the static board the theme renders anyway.
      if (this.matches("[data-lf-exhibit] *")) return;
      // Own cards only (:scope-deep would double-wire a nested board's cards).
      for (const card of this.#allCards()) {
        this.#grip(card);
        this.#destinations(card);
      }
      this.#names();
      // Grip names come from where their cards sit, so column child-list mutations
      // restate them — not the four paths that move a card (arrow step, drag, cancel,
      // replay), any of which would eventually forget. #names writes an aria-label on
      // the grip, which is not a child-list mutation and cannot feed this pass back
      // into itself.
      whileConnected(this, () => {
        for (const col of this.#columns()) this.#sortable(col);
        this.#observeNames();
        const stopMotion = this.#observeMotion();
        return () => {
          this.#namesObserver?.disconnect();
          this.#namesObserver = null;
          stopMotion?.();
          for (const sortable of this.#sortables) sortable.destroy();
          this.#sortables.clear();
        };
      });
    }

    // What a board is, said in roles: each column a labeled list, each card an
    // item in it. What says so visually is three boxes side by side — geometry,
    // which the accessibility tree doesn't carry — so without this a board is
    // one flat run of cards and Move buttons, and which column a card is in,
    // the one fact about it not in its own text, is never announced. Roles
    // describe rather than afford, so this holds for a quoted board too: an
    // exhibit is read like anything else, it just takes no input.
    //
    // The heading is written here too, because it is two things at once: the words a
    // user selects to comment on the column, and the list's accessible name, so the
    // tree hears them once, as the name. It is the page speaking (`data-lf-said`) and
    // generated, so the diff looks away, and it isn't .lf-ui, so the anchor pass
    // doesn't.
    #structure() {
      for (const col of this.#columns()) {
        col.setAttribute("role", "list");
        keeps(col, "aria-label", col.getAttribute("label"));
        for (const card of this.#cards(col)) card.setAttribute("role", "listitem");
        if (col.querySelector(":scope > .lf-column-name")) continue;
        const heading = document.createElement("span");
        heading.className = "lf-column-name";
        keeps(heading, "data-lf-gen", "1");
        heading.toggleAttribute("data-lf-said", true);
        // The column already carries these words as its name, so the heading is
        // the visible half only: the tree hears them once, the user can still
        // select them, and the theme's generated copy is left to the no-script case.
        heading.setAttribute("aria-hidden", "true");
        heading.textContent = col.getAttribute("label");
        // How many cards stand in the column, beside its heading rather than in it, so
        // the heading's words stay the column's name. Generated like the heading, and
        // quotable like it: a figure the user can see is one they can point at. The
        // list already tells a screen reader its length, so it is the visible half only.
        const count = document.createElement("span");
        count.className = "lf-column-count";
        keeps(count, "data-lf-gen", "1");
        count.setAttribute("aria-hidden", "true");
        col.prepend(heading);
        heading.after(count);
      }
      this.#counts();
    }

    #counts() {
      for (const col of this.#columns()) {
        const count = col.querySelector(":scope > .lf-column-count");
        keepsText(count, this.#cards(col).length);
      }
    }

    // Every grip's name, in the idiom the live region already announces moves in
    // ("card — column"): the user who lands on a grip by Tab hears where the
    // card is without having read the list it sits in. State provenance is the runtime's
    // one shared reading on the card rather than another suffix in this control's name.
    #names() {
      this.#counts();
      const columns = [...this.#columns()];
      const byId = new Map(columns.map((col) => [col.id, col]));
      for (const col of columns) {
        const where = col.getAttribute("label");
        for (const card of this.#cards(col)) {
          const name = `Move: ${this.#title(card)} — ${where}`;
          const grip = card.querySelector(":scope > .lf-grip");
          keeps(grip, "aria-label", name);
          /** @type {NodeListOf<HTMLButtonElement>} */
          const destinations = card.querySelectorAll(
            ":scope > .lf-board-destinations > .lf-board-destination",
          );
          for (const button of destinations)
            button.toggleAttribute(
              "hidden",
              button.getAttribute("data-lf-board-target") === col.id ||
                !this.#takes(
                  card,
                  byId.get(button.getAttribute("data-lf-board-target") ?? "") ?? null,
                ),
            );
          // With no button to show, the group's "Move to" would name no destination.
          card.querySelector(":scope > .lf-board-destinations")?.toggleAttribute(
            "hidden",
            [...destinations].every((button) => button.hidden),
          );
        }
      }
    }

    // A board inside a Claude reply detaches when its thread's node is rebuilt —
    // resolving is the occasion the reconciled panel leaves, its cached body
    // re-adopted into the new node — and no blur fires for a detached grip, so
    // drop a live grab here or it holds the page's drag for good — freezing action
    // replay and version-follow.
    disconnectedCallback() {
      super.disconnectedCallback();
      if (this.#grabbed) this.#cancel(this.#grabbed);
      this.#superseded = null;
      this.#finishGesture();
    }

    #observeMotion() {
      if (!this.#sortables.size) return;
      const reduced = matchMedia("(prefers-reduced-motion: reduce)");
      const animate = () => {
        for (const sortable of this.#sortables)
          sortable.option("animation", reduced.matches ? 0 : 150);
      };
      animate();
      reduced.addEventListener("change", animate);
      return () => reduced.removeEventListener("change", animate);
    }

    #paintAvailability = () => {
      const cards = [...this.#allCards()];
      const movable = new Map(cards.map((card) => [card, this.#movable(card)]));
      const any = [...movable.values()].some(Boolean);
      for (const sortable of this.#sortables) sortable.option("disabled", !any);
      for (const [card, available] of movable) {
        const grip = card.querySelector(":scope > .lf-grip");
        if (grip) {
          keeps(grip, "aria-disabled", !available);
          keeps(grip, "tabindex", available ? 0 : -1);
        }
        for (const button of card.querySelectorAll(
          ":scope > .lf-board-destinations button",
        ))
          button.toggleAttribute("disabled", !available);
      }
    };

    #available() {
      return Boolean(this.state?.move?.available);
    }

    // A card with `shows` moves when the answer it shows can change and a column other
    // than its own takes it, so never where it shows none, and every other card when
    // the board's own move can. A card no column takes would offer a grip that grabs
    // and then moves nowhere.
    /** @param {Element} card */
    #movable(card) {
      if (!showsId(card)) return this.#available();
      const shown = shownAnswer(card);
      return Boolean(
        shown?.available &&
        [...this.#columns()].some(
          (column) => column !== card.parentElement && shown.takes(this.#holds(column)),
        ),
      );
    }

    // The value a column holds for a card showing an answer, null for none.
    /** @param {Element} column */
    #holds(column) {
      return column.getAttribute(VALUE) || null;
    }

    // Where a card showing an answer stands: the first column holding the value the
    // answer names, else the first holding none.
    /** @param {unknown} value */
    #columnFor(value) {
      const columns = [...this.#columns()];
      return (
        columns.find((column) => this.#holds(column) === value) ??
        columns.find((column) => this.#holds(column) === null) ??
        null
      );
    }

    #observeNames() {
      if (
        this.#namesObserver ||
        !this.querySelector(":scope > lf-column > lf-card > .lf-grip")
      )
        return;
      this.#namesObserver = new MutationObserver(() => this.#names());
      for (const col of this.#columns())
        this.#namesObserver.observe(col, { childList: true });
    }

    /** @param {Element} card */
    #title(card) {
      return card.getAttribute("label")?.trim() || card.id;
    }
    /** @returns {NodeListOf<HTMLElement>} */
    #columns() {
      return this.querySelectorAll(":scope > lf-column");
    }

    /** @returns {NodeListOf<BoardCard>} */
    #allCards() {
      return this.querySelectorAll(":scope > lf-column > lf-card");
    }

    /** @param {Element} col @returns {BoardCard[]} */
    #cards(col) {
      /** @type {NodeListOf<BoardCard>} */
      const cards = col.querySelectorAll(":scope > lf-card");
      return [...cards];
    }

    // The grip's two states, declared once. Each row carries its own liveness, so the
    // state moves by the board's own field rather than by re-declaring the keys at every
    // site that changes it — three sites did, and a fourth that forgot would have left the
    // line promising the wrong press.
    //
    // The page's own keys still work mid-grab, and that is not an oversight: any of them
    // that takes focus off the grip (c into the composer, d to the next Decision) blurs it, and
    // the blur below cancels the grab and puts the card back where it was. A held card
    // therefore cannot be stranded by a press that moves the user elsewhere, which is
    // what suspending the page would have been for.
    /** @param {BoardCard} card @param {HTMLElement} grip */
    #keys(card, grip) {
      const held = () => this.#grabbed?.grip === grip;
      // Whether the card is authored to show an answer, read off its markup since the
      // answer's own state may not have loaded yet.
      const shows = Boolean(showsId(card));
      // Columns run the way the page's words do, so left is the previous column only
      // in left-to-right text; the title names the column, which holds whichever way
      // the board lays them out.
      const [back] = rowArrows(this);
      /** @param {string} binding */
      const column = (binding) =>
        `Move it to the ${binding === back ? "previous" : "next"} column`;
      // A card showing an answer only changes column, so it has no up or down.
      const routes = [
        { id: "board.move-up", binding: "ArrowUp", title: "Move it up" },
        { id: "board.move-down", binding: "ArrowDown", title: "Move it down" },
        { id: "board.move-left", binding: "ArrowLeft", title: column("ArrowLeft") },
        { id: "board.move-right", binding: "ArrowRight", title: column("ArrowRight") },
      ].slice(shows ? 2 : 0);
      const grab = {
        id: "board.grab",
        keys: PRESS,
        title: "grab the card",

        // One gesture at a time: a grab, or a pointer drag under way, holds the board.
        when: () => this.#movable(card) && !this.#resumeProjection,
        run: () => this.#grab(card, grip, rows),
      };
      // The grip says the drag, as its description and under its name in its preview;
      // the keys that grab it are the row's own, its activation, which a control's
      // preview leaves out, so the grip names them as key chips beside its name, which a
      // finger never sees, and its `aria-keyshortcuts` names them for a screen reader.
      const drag = "Drag to move";
      grip.setAttribute("aria-description", drag);
      // Grabbed, the card is moving, so the grip says nothing over it until it drops.
      grip.lfPreview = () =>
        !held() && { keys: grab.keys.map((binding) => [binding]), detail: [drag] };
      /** @type {import("/runtime/dom/keyboard/bindings.js").Command[]} */
      const rows = [
        grab,
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
          runKey: (binding) => {
            const [back, ahead] = rowArrows(this);
            this.#step(
              card,
              grip,
              binding === back ? -1 : binding === ahead ? 1 : 0,
              binding === "ArrowUp" ? -1 : binding === "ArrowDown" ? 1 : 0,
            );
          },
        },
        {
          id: "board.drop",
          keys: PRESS,
          title: "drop",
          when: held,
          run: () => {
            if (this.#grabbed) this.#drop(this.#grabbed);
          },
        },
        {
          id: "board.cancel",
          keys: ["Escape"],
          title: "cancel the move",
          travels: true,
          when: () => held() || Boolean(this.#activeDrag()),
          run: () => {
            const drag = this.#activeDrag();
            if (drag)
              drag.handleEvent(new CustomEvent("dragend", { detail: "cancel" }));
            else if (this.#grabbed) this.#cancel(this.#grabbed, true);
          },
        },
      ];
      grip.lfCommands = { title: "On a card grip", rows };
      return rows;
    }
    /** @param {BoardCard} card */
    #grip(card) {
      const grip = offerAction("symbol", "lf-grip", undefined, { action: "move" });
      // A revision that rewrites any card replaces the board, and a user on this grip
      // is on the same card's grip in the replacement (records/carry.js).
      grip.setAttribute("data-lf-carry", "grip");
      this.#keys(card, grip);
      // Leaving the grip drops the grab: restore the origin. Native moves retain
      // focus, so only a real departure still lacks focus when this settles. The window
      // losing system focus blurs the grip but leaves it its tree's active element, so
      // that is no departure.
      grip.addEventListener("blur", () => {
        if (this.#grabbed?.grip !== grip) return;
        setTimeout(() => {
          const root = /** @type {Document | ShadowRoot} */ (grip.getRootNode());
          if (this.#grabbed?.grip === grip && root.activeElement !== grip)
            this.#cancel(this.#grabbed);
        });
      });
      card.append(grip);
      grip.dispatchEvent(
        new CustomEvent("lf-commands", { bubbles: true, composed: true }),
      );
    }

    /** @param {BoardCard} card */
    #destinations(card) {
      const columns = [...this.#columns()];
      if (columns.length < 2) return;
      const group = offer("div", "lf-board-destinations");
      group.setAttribute("role", "group");
      group.setAttribute("aria-label", `Move ${this.#title(card)} to`);
      const label = document.createElement("span");
      label.className = "lf-board-destinations-label";
      keeps(label, "data-lf-gen", "1");
      label.textContent = "Move to";
      group.append(label);
      for (const column of columns) {
        const button = offerAction(
          "word",
          "lf-board-destination",
          column.getAttribute("label") ?? undefined,
        );
        button.dataset.lfBoardTarget = column.id;
        button.setAttribute(
          "aria-label",
          `Move ${this.#title(card)} to ${column.getAttribute("label")}`,
        );
        button.addEventListener("click", () => {
          if (!this.#movable(card)) return;
          const from = card.parentElement;
          if (from === column) return;
          this.#beginGesture();
          this.#place(
            card,
            column,
            this.#cards(column).length,
            card.querySelector(":scope > .lf-grip"),
          );
          this.#send(card, from, column);
        });
        group.append(button);
      }
      card.append(group);
    }

    /** @param {BoardCard} card @param {HTMLElement} grip @param {readonly import("/runtime/dom/keyboard/bindings.js").Command[]} rows */
    #grab(card, grip, rows) {
      if (!this.#movable(card)) return;
      const from = card.parentElement;
      const cards = this.#cards(from);
      const index = cards.indexOf(card);
      this.#grabbed = { card, grip, from, index };
      this.#beginGesture();
      card.classList.add("lf-lift");
      grip.dispatchEvent(
        new CustomEvent("lf-preview", { bubbles: true, composed: true }),
      );
      // Where the card starts, in the idiom every arrow step announces — a user about to
      // move it needs the position the moves count from.
      const grabbed = `${this.#title(card)} grabbed — ${from.getAttribute("label")}, position ${
        index + 1
      } of ${cards.length}`;
      window.dispatchEvent(
        new CustomEvent("lf-announce", { detail: { words: grabbed, rows } }),
      );
    }

    /** @param {BoardCard} card @param {HTMLElement} grip @param {number} dCol @param {number} dRow */
    #step(card, grip, dCol, dRow) {
      const col = card.parentElement;
      let target;
      let index;
      if (dRow) {
        const cards = this.#cards(col);
        const to = cards.indexOf(card) + dRow;
        if (to >= 0 && to < cards.length) {
          target = col;
          index = to;
        } else {
          // Past the column's end. Where the board stacks its columns the next column
          // stands on that side, so the step continues into it at the slot nearest
          // this one; side by side, nothing stands there and the card stays.
          const cols = [...this.#columns()];
          const beside = cols[cols.indexOf(col) + dRow];
          if (!beside) return;
          const here = col.getBoundingClientRect();
          const there = beside.getBoundingClientRect();
          if (dRow > 0 ? there.top < here.bottom - 1 : there.bottom > here.top + 1)
            return;
          target = beside;
          index = dRow > 0 ? 0 : this.#cards(beside).length;
        }
      } else {
        // Past any column the card's answer cannot name.
        const cols = [...this.#columns()].filter(
          (column) => column === col || this.#takes(card, column),
        );
        target = cols[cols.indexOf(col) + dCol];
        if (!target) return;
        // Same visual index; #place clamps to the target's end.
        index = this.#cards(col).indexOf(card);
      }
      this.#place(card, target, index, grip);
      const now = card.parentElement;
      const cards = this.#cards(now);
      window.dispatchEvent(
        new CustomEvent("lf-announce", {
          detail: `${this.#title(card)} — ${now.getAttribute("label")}, position ${
            cards.indexOf(card) + 1
          } of ${cards.length}`,
        }),
      );
    }

    /** @param {Grab} grab */
    #drop(grab) {
      const { card, from, index } = grab;
      this.#release(grab);
      const to = card.parentElement;
      if (
        to === from &&
        this.#cards(to).findIndex((candidate) => candidate === card) === index
      ) {
        this.#finishGesture();
        return;
      }
      this.#send(card, from, to);
    }

    /** @param {Grab} grab @param {boolean} [refocus] */
    #cancel(grab, refocus = false) {
      const { card, grip, from, index } = grab;
      this.#release(grab);
      // Escape keeps focus and returns the view to the origin. Blur restores the card
      // without taking the viewport from the control the user deliberately entered.
      this.#place(card, from, index, refocus ? grip : null);
      this.#finishGesture();
      window.dispatchEvent(
        new CustomEvent("lf-announce", {
          detail: `${this.#title(card)} — move cancelled`,
        }),
      );
    }

    #beginGesture() {
      if (this.#resumeProjection) return;
      this.#resumeProjection = this.defer();
      this.#held = Promise.withResolvers();
      this.dispatchEvent(
        Object.assign(new Event("lf-hold", { bubbles: true, composed: true }), {
          complete: this.#held.promise,
        }),
      );
    }

    #finishGesture() {
      this.#held?.resolve();
      this.#held = null;
      this.#resumeProjection?.();
      this.#resumeProjection = null;
    }

    // The one writer of "no card is held", so the grip's rows change back here and nowhere
    // else: a drop, a cancel, and any later way out of a grab all end through it.
    /** @param {Grab} grab */
    #release(grab) {
      grab.card.classList.remove("lf-lift");
      this.#grabbed = null;
      // The grip's rows read the grab, and a drag that takes a grab over keeps the
      // user's hold, whose start and end are what paint them otherwise.
      grab.grip.dispatchEvent(
        new CustomEvent("lf-commands", { bubbles: true, composed: true }),
      );
      grab.grip.dispatchEvent(
        new CustomEvent("lf-preview", { bubbles: true, composed: true }),
      );
    }

    // Arrow steps and a cancelled grab place through one writer. Start from the
    // current paint before cancelling a superseded FLIP, so a reversal continues
    // where the user sees the card. Keyboard placement refocuses and reveals the final
    // box before FLIP puts its paint back at the old box; the reveal's glide and the
    // card's motion then run together.
    /** @param {Element} card @param {Element} col @param {number} index @param {HTMLElement | null} [grip] */
    #place(card, col, index, grip = null) {
      const first = card.getBoundingClientRect();
      for (const a of card.getAnimations()) a.cancel();
      const rest = this.#cards(col).filter((c) => c !== card);
      move(col, card, rest[index] ?? null);
      if (grip) {
        focusDestination(grip, "return");
        scrollIntoView(card, { behavior: "smooth", block: "nearest" });
      }
      const last = card.getBoundingClientRect();
      const dx = first.left - last.left;
      const dy = first.top - last.top;
      if (dx || dy)
        motion(
          card,
          [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }],
          150,
        );
    }

    // One completed move, drag or keyboard: the card's rank among the destination's
    // other cards, sent once, so the move stays put whichever other moves stand. The
    // gesture's name follows the branch the user can see — a card kept in its column
    // was reordered, not moved to where it already was. A refusal is restored by the
    // layer from the declared record plus its outbox, never from this gesture's DOM
    // snapshot: that snapshot may be another queued move the server also refused.
    /** @param {Element} card @param {Element} from @param {Element} to */
    #send(card, from, to) {
      if (showsId(card)) {
        // The answer moves the card, through its widget's own command; a move within
        // its column changes nothing, and the release below puts it back. So does a
        // card showing no answer by the time it drops, since the board's own move
        // would record its place as a fact of the board's.
        if (to !== from)
          shownAnswer(card)?.answer(
            this.#holds(to),
            `Moved “${this.#title(card)}” to ${to.getAttribute("label")}`,
          );
        this.#finishGesture();
        return;
      }
      this.record(
        "move",
        {
          unit: card.id,
          value: to.id,
          // Among the cards as the board shows them, those standing by an answer
          // included.
          rank: rankAt(
            { ...this.#position, value: this.#placement() },
            to.id,
            this.#cards(to).findIndex((candidate) => candidate === card),
            card.id,
          ),
        },
        {
          says: `${to === from ? "Reordered in" : "Moved to"} ${to.getAttribute("label")}`,
        },
      );
      // A gesture can outlive the state that enabled it. If admission has already
      // closed by commit time, releasing the hold repaints the moved native node from
      // the current state immediately.
      this.#finishGesture();
    }

    // Sortable owns drag teardown; the grip's Cancel command ends it through
    // the dependency's drag-end handler, and onEnd restores rather than records.
    #activeDrag() {
      const active = Sortable.active;
      return active && this.#sortables.has(active) ? active : null;
    }

    /** @param {HTMLElement} col */
    #sortable(col) {
      const scroller = scrollerFor(this);
      const group = `board-${this.id}`;
      const sortable = new Sortable(col, {
        disabled: !this.#available(),
        // Named per board, so two boards on a page don't cross-drag. A column opens a
        // slot only for a card it takes (#takes), as the arrows and the destination
        // buttons offer it. Sortable asks this of every column but the one the drag
        // began in, which always takes its card back. A column that takes the card
        // answers with the groups it takes from, which Sortable matches against the
        // board the drag began in; `true` would take a card from any board.
        group: {
          name: group,
          put: (to, _from, card) => (this.#takes(card, to.el) ? [group] : false),
        },
        draggable: "lf-card",
        handle: ".lf-grip",
        // Movability is the card's own where it shows an answer (#movable). Sortable
        // passes null for a press on no card, such as a column's heading, which
        // starts no drag.
        filter: (_event, card) => !card || !this.#movable(card),
        preventOnFilter: false,
        // Named because a board an agent sent in a reply is scrolled by the panel's list,
        // while one in the page is scrolled by the browser root. Sortable cannot infer
        // that product boundary from the board alone.
        scroll: scroller instanceof HTMLElement ? scroller : false,
        forceFallback: true, // pointer-driven label preview, including touch
        // The image under the pointer carries the card's label, never a second live
        // widget tree: no copied form groups, widget lifetimes or iframes.
        cloneElement: (card) => {
          const preview = offer("div", "lf-motion-preview", this.#title(card));
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
          // A pointer drag supersedes a live keyboard grab: Sortable's mid-drag
          // reparents fire no blur, so a stale grab would survive the drag and
          // its Escape would silently revert the recorded move. Dragging the
          // grabbed card folds the grab's origin into the drag — unsent arrow
          // steps become part of the one recorded move; dragging another card
          // cancels the grab exactly as focus loss would.
          if (this.#grabbed) {
            if (this.#grabbed.card === evt.item) {
              this.#superseded = this.#grabbed;
              this.#release(this.#grabbed);
            } else this.#cancel(this.#grabbed);
          }
          this.#beginGesture();
          // The held card owns the keyboard too, through its existing grip scope.
          const grip = evt.item.querySelector(":scope > .lf-grip");
          if (grip) focusDestination(grip, "return");
        },
        onEnd: (evt) => {
          // Ahead of the branches below, because the one that returns early sends
          // nothing: a card dropped where it was picked up puts the hand down with
          // nothing following it to say so.
          const sup = this.#superseded;
          this.#superseded = null;
          // The *draggable* indexes, which count cards; Sortable's plain
          // oldIndex/newIndex count every element child, and a column's first
          // child is the heading #structure prepends. Mixing the two units is
          // silent both ways: a superseded grab compares its own card index
          // against a child index, so a card dragged one place up from where it
          // was grabbed reads as unmoved and the move is never sent, and a
          // cancelled move restores through #place, which counts cards, one slot
          // late.
          const { item: card, to, newDraggableIndex: newIndex } = evt;
          const from = sup ? sup.from : evt.from;
          const oldIndex = sup ? sup.index : evt.oldDraggableIndex;
          const event = evt.originalEvent;
          if (
            event?.type === "pointercancel" ||
            event?.type === "touchcancel" ||
            (event instanceof CustomEvent && event.detail === "cancel")
          ) {
            this.#place(card, from, oldIndex, card.querySelector(":scope > .lf-grip"));
            this.#finishGesture();
            window.dispatchEvent(
              new CustomEvent("lf-announce", {
                detail: `${this.#title(card)} — move cancelled`,
              }),
            );
            return;
          }
          if (from === to && oldIndex === newIndex) {
            this.#finishGesture();
            return;
          }
          this.#send(card, from, to);
        },
      });
      this.#sortables.add(sortable);
    }

    // The complete column composition names every card in its final order. Measure
    // once around that placement so FLIP animates the resulting layout together.
    render() {
      // A quoted board is an exhibit with no reading: the theme draws it as authored.
      if (!this.state) return nothing;
      this.#reportUnshown();
      this.#arrange(this.#placement());
      this.#paintAvailability();
      return nothing;
    }

    // Tell the author of each card whose `shows` names no answer the board can show,
    // or a widget whose picks can name no column. Neither card can follow an answer,
    // and neither `page check` nor the page says why.
    #reportUnshown() {
      for (const card of this.#allCards()) {
        const shown = shownWidget(card);
        const fault = !shown
          ? null
          : "fault" in shown
            ? shown.fault
            : valuelessFault(card, shown);
        if (fault === null) this.#reported.delete(card);
        else if (this.#reported.get(card) !== fault) {
          this.#reported.set(card, fault);
          card.dispatchEvent(
            new ErrorEvent("error", {
              error: new Error(fault),
              bubbles: true,
              composed: true,
            }),
          );
        }
      }
    }

    get #position() {
      const state = this.state?.move;
      if (!state || !("ranks" in state))
        throw new Error("Board requires positional move state");
      return state;
    }

    // Every column's cards in order: the board's own move state, with each card that
    // shows an answer moved to the column that answer names. Reading the answer here
    // follows its widget's state, so a pick in its section, an undo, a refusal and a
    // revision's retraction all redraw the board. Each column lists its cards by rank,
    // a shown card keeping its authored one.
    #placement() {
      const { value, ranks } = this.#position;
      const columns = Object.fromEntries(
        Object.entries(value).map(([id, cards]) => [id, [...cards]]),
      );
      for (const card of this.#allCards()) {
        const shown = shownAnswer(card);
        const target = shown && this.#columnFor(shown.value);
        if (!target) continue;
        const destination = columns[target.id];
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

    // Whether the card can stand in `column`: any column for a card the board places,
    // one holding a value its answer can take for a card showing an answer.
    /** @param {Element} card @param {Element | null} column */
    #takes(card, column) {
      const shown = shownAnswer(card);
      return !shown || (column && shown.takes(this.#holds(column)));
    }

    /** @param {Readonly<Record<string, readonly string[]>>} columns */
    #arrange(columns) {
      const cards = [...this.#allCards()];
      if (
        Object.entries(columns).every(([id, order]) => {
          const column = document.getElementById(id);
          const current = column && this.#cards(column);
          return (
            current?.length === order.length &&
            current.every((card, index) => card.id === order[index])
          );
        })
      )
        return;
      const first = new Map(
        cards.map((card) => {
          const painted = card.getBoundingClientRect();
          for (const animation of card.getAnimations()) animation.cancel();
          return [card, painted];
        }),
      );
      for (const [id, order] of Object.entries(columns)) {
        const column = document.getElementById(id);
        if (!column || column.closest("lf-board") !== this) continue;
        order.forEach((id, index) => {
          const card = cards.find((candidate) => candidate.id === id);
          if (card && this.#cards(column)[index] !== card)
            move(column, card, this.#cards(column)[index] ?? null);
        });
      }
      const movements = [];
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
      this.dispatchEvent(
        new CustomEvent("lf-layout", { bubbles: true, composed: true }),
      );
      if (movements.length)
        void Promise.allSettled(movements).then(() =>
          this.dispatchEvent(
            new CustomEvent("lf-layout", { bubbles: true, composed: true }),
          ),
        );
    }
  },
);
