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
 * A card with `shows` is the board's view of another widget's pick, such as a
 * proposal's answer in its own section, and the pick stays that widget's. The card binds
 * the widget's `choice` output (lf-card.js), so the board draws the card in the column
 * whose `value` the pick names, or in the first column without a `value` where the
 * pick names none or no column holds it. A pick there, an undo, a refusal and a
 * revision's retraction move the card with no state of the board's own. Dropping the
 * card in another column asks its owner, the widget whose choice it shows, to pick
 * that column's value with the invoker command `--choose`, from a button whose words
 * name the move, so Undo names it. The owner records the pick as its own or refuses
 * it, and either way the board then draws the card where the owner's choice puts it. A
 * column without a `value` asks for the empty pick. A column with one takes the card
 * only where one option carries that value, since a value two options carry doesn't
 * say which the user picks. A card no other column takes has its grip disabled. The
 * arrows only change a shown card's column: an order of the board's own would be a
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
 * a card with `shows`, so the board never sends its own move for one (#movable, #send)
 * and, once the choice has arrived, draws it by its choice whatever the board's move
 * state holds.
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
  move,
  motion,
  scrollerFor,
  focusDestination,
  scrollIntoView,
  whileConnected,
} from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { offer, offerAction } from "/runtime/lib/controls.js";
import { PRESS, rowArrows } from "/runtime/lib/keys.js";
import { keeps, keepsText } from "/runtime/lib/keeps.js";
import { byRank, rankAt } from "/runtime/lib/rank.js";

// The attribute naming the value a column holds for a card that shows a choice.
const VALUE = "value";

/** A `choice` value, as the registry's `$data.contracts` declares it.
 * @typedef {{value: string, options: {value: string, label: string}[], disabled: boolean}} Choice */

// The id a card's `shows` names, or null for a card that shows no choice: one without
// the attribute, or with it empty.
/** @param {Element} card */
const showsId = (card) => card.getAttribute("shows") || null;

// The choice a card shows, or null where it shows none or the widget it names holds
// none yet.
/** @param {Element} card @returns {Choice | null} */
const choiceOf = (card) =>
  (showsId(card) && /** @type {{choice?: Choice | null}} */ (card).choice) || null;

// Whether `--choose` takes `value`: the empty pick, or the one option carrying it.
/** @param {Choice} choice @param {string} value */
const takes = (choice, value) =>
  !value || choice.options.filter((option) => option.value === value).length === 1;

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

    // A card with `shows` moves when the user can change the choice it shows and a
    // column other than its own takes it, so never where it shows none, and every other
    // card when the board's own move can. A card no column takes would offer a grip that
    // grabs and then moves nowhere.
    /** @param {Element} card */
    #movable(card) {
      if (!showsId(card)) return this.#available();
      const choice = choiceOf(card);
      return Boolean(
        choice &&
        !choice.disabled &&
        [...this.#columns()].some(
          (column) =>
            column !== card.parentElement && takes(choice, this.#holds(column)),
        ),
      );
    }

    // The value a column holds for a card showing a choice, the empty string for none.
    /** @param {Element} column */
    #holds(column) {
      return column.getAttribute(VALUE) || "";
    }

    // Where a card showing a choice stands: the first column holding the value the
    // choice names, else the first holding none.
    /** @param {string} value */
    #columnFor(value) {
      const columns = [...this.#columns()];
      return (
        columns.find((column) => this.#holds(column) === value) ??
        columns.find((column) => this.#holds(column) === "") ??
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
      // Whether the card is authored to show a choice, read off its markup since the
      // choice may not have arrived yet.
      const shows = Boolean(showsId(card));
      // Columns run the way the page's words do, so left is the previous column only
      // in left-to-right text; the title names the column, which holds whichever way
      // the board lays them out.
      const [back] = rowArrows(this);
      /** @param {string} binding */
      const column = (binding) =>
        `Move it to the ${binding === back ? "previous" : "next"} column`;
      // A card showing a choice only changes column, so it has no up or down.
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
        // Past any column the card's choice cannot take.
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
        // The choice moves the card, through its widget's `--choose`; a move within its
        // column asks for nothing. Either way the release below draws the card where
        // the choice the widget then holds puts it, so a refused or unchanged choice
        // puts the card back, as does a request that throws.
        try {
          if (to !== from)
            this.#ask(
              card,
              this.#holds(to),
              `Moved “${this.#title(card)}” to ${to.getAttribute("label")}`,
            );
        } finally {
          this.#finishGesture();
        }
        return;
      }
      this.record(
        "move",
        {
          unit: card.id,
          value: to.id,
          // Among the cards as the board shows them, those standing by a choice
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

    // Ask the card's owner to pick `value`, from a button the board makes and keeps out
    // of the page, whose words name the move (`package-data.md`, "Asking another widget
    // to act").
    /** @param {Element} card @param {string} value @param {string} says */
    #ask(card, value, says) {
      /** @type {{owner?: Element | null}} */ (card).owner?.dispatchEvent(
        new CommandEvent("command", {
          command: "--choose",
          source: Object.assign(document.createElement("button"), {
            value,
            textContent: says,
          }),
          cancelable: true,
        }),
      );
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
        // Movability is the card's own where it shows a choice (#movable). Sortable
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
      this.#arrange(this.#placement());
      // The columns a card showing a choice offers follow the choice, which may arrive
      // after the board has set up and move no card.
      this.#names();
      this.#paintAvailability();
      return nothing;
    }

    get #position() {
      const state = this.state?.move;
      if (!state || !("ranks" in state))
        throw new Error("Board requires positional move state");
      return state;
    }

    // Every column's cards in order: the board's own move state, with each card that
    // shows a choice moved to the column that choice names. Leaf sets each card's
    // choice as the widget's moves, and the card draws the board again, so a pick in
    // its section, an undo, a refusal and a revision's retraction all redraw the board.
    // Each column lists its cards by rank, which the authored order and the board's own
    // moves set.
    #placement() {
      const { value, ranks } = this.#position;
      const columns = Object.fromEntries(
        Object.entries(value).map(([id, cards]) => [id, [...cards]]),
      );
      for (const card of this.#allCards()) {
        const choice = choiceOf(card);
        const target = choice && this.#columnFor(choice.value);
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
    // and for a card showing a choice one holding a value its `--choose` takes.
    /** @param {Element} card @param {Element | null} column */
    #takes(card, column) {
      if (!showsId(card)) return true;
      const choice = choiceOf(card);
      return Boolean(choice && column && takes(choice, this.#holds(column)));
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
