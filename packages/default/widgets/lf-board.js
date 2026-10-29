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
 * For the whole gesture the board holds
 * the page's drag (`dragging`), so no new revision or undo replaces the cards under it,
 * and defers its own drawing (`defer`), so no foreign move replays mid-gesture; a
 * completed move
 * reports through #send as one ranked `move` action, indistinguishable on
 * the wire. Its render receives every column's final ordered card ids. One render
 * preserves native nodes, syncs a second tab, and no-ops on the sender. Presentation is theme CSS; authored content
 * is never replaced, so there is no failSoft.
 *
 * A card with `shows` is the board's view of another widget's answer (x-shows,
 * `shownAnswer`), such as a proposal's pick in its own section. The board draws it in
 * the column whose `value` that answer names, read from the widget's state in this
 * render, so a pick there, an undo, a refusal and a revision's retraction move the card
 * with no state of the board's own. Dropping it in another column sends the widget's
 * own answer for that column's value, the same command the section's control sends;
 * a column the widget has no answer for takes no drop and offers no button. Such a
 * card keeps its authored order: an order of the board's own would be a second fact
 * placed among columns the answer decides (`shown_answers.py`), so the door refuses
 * a move of it and the arrows only change its column.
 *
 * The board also says what it is non-visually: columns are labeled lists and
 * cards their items (#structure), and each grip is named for the column its
 * card now sits in (#names). Both are attributes on authored elements — the
 * light DOM stays verbatim, which is what the anchor pass and the version diff
 * walk. The theme's column heading is CSS generated content with empty alt
 * text, so the label reaches the tree once, as the list's name, rather than
 * twice. */
import Sortable from "/vendor/sortable.esm.js";
import {
  setScroll,
  LeafElement,
  nothing,
  move,
  offer,
  offerAction,
  generatedElement,
  quoted,
  says,
  announce,
  labelOf,
  layoutChanged,
  saying,
  dragging,
  motion,
  motionPreview,
  scrollerFor,
  PRESS,
  rowArrows,
  onMotionPreferenceChange,
  rankAt,
  reducedMotion,
  scrollBehavior,
  keeps,
  keepsHidden,
  keepsText,
  focusDestination,
  scrollIntoView,
  whileConnected,
  focused,
  declarationFor,
  shownAnswer,
  commandsChanged,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-board",
  class extends LeafElement {
    #grabbed = null; // {card, grip, from, index} — the origin, for cancel and no-op drops
    #superseded = null; // a grab folded into a pointer drag of the same card (see onStart)
    #rows = new WeakMap(); // grip → its declared rows, for the grab announcement
    #namesObserver = null;
    #sortables = new Set();
    #resumeProjection = null;

    setup() {
      if (!this.classList.contains("scroll")) this.classList.add("scroll");
      this.#structure();
      // A quoted board is an exhibit: no grips, no sortable, no grip keys in
      // the command reference dialog — it stays the static board the theme renders anyway.
      if (quoted(this)) return;
      // Own cards only (:scope-deep would double-wire a nested board's cards).
      for (const card of this.querySelectorAll(":scope > lf-column > lf-card")) {
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
        for (const col of this.querySelectorAll(":scope > lf-column"))
          this.#sortable(col);
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
    // The heading is written here too, rather than declared x-says and left to
    // the runtime's pass, because it is two things at once: the words a user
    // selects to comment on the column, and the list's accessible name. The pass
    // renders one run of words at an edge and knows nothing about names, so it
    // would put these into the tree a second time under a list already carrying
    // them. Same marker (the theme styles [data-lf-said]) and same contract
    // (generated, so the diff looks away; not .lf-ui, so the anchor pass doesn't)
    // — a widget with a module of its own does the part only it can, which is
    // the line the layer's AGENTS.md draws and a widget's authored labels are the
    // other case of.
    #structure() {
      for (const col of this.querySelectorAll(":scope > lf-column")) {
        col.setAttribute("role", "list");
        col.setAttribute("aria-label", col.getAttribute("label"));
        for (const card of this.#cards(col)) card.setAttribute("role", "listitem");
        if (col.querySelector(':scope > [data-lf-said="label"]')) continue;
        const heading = document.createElement("span");
        heading.dataset.lfSaid = "label";
        generatedElement(heading, { says: true });
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
        generatedElement(count, { says: false });
        count.setAttribute("aria-hidden", "true");
        col.prepend(heading);
        heading.after(count);
      }
      this.#counts();
    }

    #counts() {
      for (const col of this.querySelectorAll(":scope > lf-column")) {
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
      for (const col of this.querySelectorAll(":scope > lf-column")) {
        const where = col.getAttribute("label");
        for (const card of this.#cards(col)) {
          const name = `Move: ${this.#title(card)} — ${where}`;
          const grip = card.querySelector(":scope > .lf-grip");
          keeps(grip, "aria-label", name);
          for (const button of card.querySelectorAll(
            ":scope > .lf-board-destinations > .lf-board-destination",
          ))
            keepsHidden(
              button,
              button.dataset.lfBoardTarget === col.id ||
                !this.#takes(
                  card,
                  document.getElementById(button.dataset.lfBoardTarget),
                ),
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
      if (this.#grabbed) this.#cancel();
      this.#superseded = null;
      this.#finishGesture();
    }

    #observeMotion() {
      if (!this.#sortables.size) return;
      for (const sortable of this.#sortables)
        sortable.option("animation", reducedMotion() ? 0 : 150);
      return onMotionPreferenceChange((reduced) => {
        for (const sortable of this.#sortables)
          sortable.option("animation", reduced ? 0 : 150);
      });
    }

    #paintAvailability = () => {
      const cards = [...this.querySelectorAll(":scope > lf-column > lf-card")];
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
      return Boolean(this.reading?.actions.move?.available);
    }

    // A card showing another widget's answer (x-shows) moves when that answer can
    // change, and every other card when the board's own move can.
    #movable(card) {
      const shown = shownAnswer(card);
      return shown ? shown.available : this.#available();
    }

    // The value a column holds for a card showing an answer, null for none: the
    // attribute the card's x-shows names.
    #holds(column, card) {
      return column.getAttribute(declarationFor(card, "x-shows").value) || null;
    }

    // Where a card showing an answer stands: the first column holding the value the
    // answer names, else the first holding none (shown_answers.py).
    #columnFor(card, value) {
      const columns = [...this.querySelectorAll(":scope > lf-column")];
      return (
        columns.find((column) => this.#holds(column, card) === value) ??
        columns.find((column) => this.#holds(column, card) === null) ??
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
      for (const col of this.querySelectorAll(":scope > lf-column"))
        this.#namesObserver.observe(col, { childList: true });
    }

    #title(card) {
      const strong = card.querySelector(":scope > strong");
      return (strong && says(strong)) || card.id;
    }
    #cards(col) {
      return [...col.querySelectorAll(":scope > lf-card")];
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
    #keys(card, grip) {
      const held = () => this.#grabbed?.grip === grip;
      // Whether the card is authored to show an answer, read off its markup since the
      // answer's own state may not have loaded yet.
      const shows = card.hasAttribute(declarationFor(card, "x-shows")?.attr ?? "");
      // Columns run the way the page's words do, so left is the previous column only
      // in left-to-right text; the title names the column, which holds whichever way
      // the board lays them out.
      const [back] = rowArrows(this);
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
        run: () => this.#grab(card, grip),
      };
      // The tooltip names the keys the row binds rather than a letter typed beside it: the
      // grip answers Space too, and said Enter on every surface for as long as the word and
      // the press were separate objects.
      grip.title = `Drag to move — or ${labelOf(grab)} to grab`;
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
          run: (binding) => {
            const [back, ahead] = rowArrows(this);
            this.#step(
              card,
              grip,
              { [back]: -1, [ahead]: 1 }[binding] ?? 0,
              { ArrowUp: -1, ArrowDown: 1 }[binding] ?? 0,
            );
          },
        },
        {
          id: "board.drop",
          keys: PRESS,
          title: "drop",
          when: held,
          run: () => this.#drop(),
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
            else this.#cancel(true);
          },
        },
      ];
      grip.lfCommands = { title: "On a card grip", rows };
      commandsChanged(grip);
      return rows;
    }
    #grip(card) {
      const grip = offerAction("symbol", "lf-grip", undefined, { action: "move" });
      this.#rows.set(grip, this.#keys(card, grip));
      // Leaving the grip drops the grab: restore the origin. Native moves retain
      // focus, so only a real departure still lacks focus when this settles.
      grip.addEventListener("blur", () => {
        if (this.#grabbed?.grip !== grip) return;
        setTimeout(() => {
          if (this.#grabbed?.grip === grip && focused() !== grip) this.#cancel();
        });
      });
      card.append(grip);
    }

    #destinations(card) {
      const columns = [...this.querySelectorAll(":scope > lf-column")];
      if (columns.length < 2) return;
      const group = offer("div", "lf-board-destinations");
      group.setAttribute("role", "group");
      group.setAttribute("aria-label", `Move ${this.#title(card)} to`);
      const label = document.createElement("span");
      label.className = "lf-board-destinations-label";
      generatedElement(label, { says: false });
      label.textContent = "Move to";
      group.append(label);
      for (const column of columns) {
        const button = offerAction(
          "word",
          "lf-board-destination",
          column.getAttribute("label"),
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

    #grab(card, grip) {
      if (!this.#movable(card)) return;
      const from = card.parentElement;
      const cards = this.#cards(from);
      const index = cards.indexOf(card);
      this.#grabbed = { card, grip, from, index };
      this.#beginGesture();
      card.classList.add("lf-lift");
      // Where the card starts, in the idiom every arrow step announces — a user about to
      // move it needs the position the moves count from.
      announce(
        `${this.#title(card)} grabbed — ${from.getAttribute("label")}, position ${
          index + 1
        } of ${cards.length} — ${saying(this.#rows.get(grip))}`,
      );
    }

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
          const cols = [...this.querySelectorAll(":scope > lf-column")];
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
        const cols = [...this.querySelectorAll(":scope > lf-column")].filter(
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
      announce(
        `${this.#title(card)} — ${now.getAttribute("label")}, position ${
          cards.indexOf(card) + 1
        } of ${cards.length}`,
      );
    }

    #drop() {
      const { card, from, index } = this.#grabbed;
      this.#release();
      const to = card.parentElement;
      if (to === from && this.#cards(to).indexOf(card) === index) {
        this.#finishGesture();
        return;
      }
      this.#send(card, from, to);
    }

    #cancel(refocus = false) {
      const { card, grip, from, index } = this.#grabbed;
      this.#release();
      // Escape keeps focus and returns the view to the origin. Blur restores the card
      // without taking the viewport from the control the user deliberately entered.
      this.#place(card, from, index, refocus ? grip : null);
      this.#finishGesture();
      announce(`${this.#title(card)} — move cancelled`);
    }

    #beginGesture() {
      this.#resumeProjection ??= this.controller.defer();
      dragging(this, true);
    }

    #finishGesture() {
      dragging(this, false);
      this.#resumeProjection?.();
      this.#resumeProjection = null;
    }

    // The one writer of "no card is held", so the grip's rows change back here and nowhere
    // else: a drop, a cancel, and any later way out of a grab all end through it.
    #release() {
      this.#grabbed.card.classList.remove("lf-lift");
      this.#grabbed = null;
    }

    // Arrow steps and a cancelled grab place through one writer. Start from the
    // current paint before cancelling a superseded FLIP, so a reversal continues
    // where the user sees the card. Cancel smooth reveal before measuring, too.
    // Keyboard placement refocuses and reveals the final box before FLIP puts its paint
    // back at the old box; native scrolling and the card's motion then run together.
    #place(card, col, index, grip = null) {
      for (const box of [this, scrollerFor(this)])
        setScroll(box, {
          left: box.scrollLeft,
          top: box.scrollTop,
          behavior: "instant",
        });
      const first = card.getBoundingClientRect();
      for (const a of card.getAnimations()) a.cancel();
      const rest = this.#cards(col).filter((c) => c !== card);
      move(col, card, rest[index] ?? null);
      if (grip) {
        focusDestination(grip, "return");
        scrollIntoView(card, {
          behavior: scrollBehavior(),
          block: "nearest",
        });
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
    #send(card, from, to) {
      const shown = shownAnswer(card);
      if (shown) {
        // The answer moves the card, through its widget's own command; a move within
        // its column changes nothing, and the release below puts it back.
        if (to !== from)
          shown.answer(
            this.#holds(to, card),
            `Moved “${this.#title(card)}” to ${to.getAttribute("label")}`,
          );
        this.#finishGesture();
        return;
      }
      this.controller.dispatch({
        kind: "action",
        verb: "move",
        detail: {
          unit: card.id,
          value: to.id,
          // Among the cards as the board shows them, those standing by an answer
          // included.
          rank: rankAt(
            { ...this.state.move, value: this.#placement() },
            to.id,
            this.#cards(to).indexOf(card),
            card.id,
          ),
        },
        says: `${to === from ? "Reordered in" : "Moved to"} ${to.getAttribute("label")}`,
      });
      // A gesture can outlive the reading that enabled it. If admission has already
      // closed by commit time, resuming the deferred controller repaints the moved
      // native node from current semantic state immediately.
      this.#finishGesture();
    }

    // Sortable owns drag teardown; the grip's Cancel command ends it through
    // the dependency's drag-end handler, and onEnd restores rather than records.
    #activeDrag() {
      const active =
        /** @type {typeof Sortable & {active: typeof Sortable.prototype | null}} */ (
          Sortable
        ).active;
      return this.#sortables.has(active) ? active : null;
    }

    #sortable(col) {
      const sortable = new Sortable(col, {
        disabled: !this.#available(),
        group: `board-${this.id}`, // per board: two boards on a page don't cross-drag
        draggable: "lf-card",
        handle: ".lf-grip",
        // Movability is the card's own where it shows an answer (#movable).
        filter: (_event, card) => !this.#movable(card),
        preventOnFilter: false,
        // Named because a board an agent sent in a reply is scrolled by the panel's list,
        // while one in the page is scrolled by the browser root. Sortable cannot infer
        // that product boundary from the board alone.
        scroll: scrollerFor(this),
        forceFallback: true, // pointer-driven label preview, including touch
        cloneElement: (card) => motionPreview(this.#title(card)),
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
              this.#release();
            } else this.#cancel();
          }
          this.#beginGesture();
          // The held card owns the keyboard too, through its existing grip scope.
          focusDestination(evt.item.querySelector(":scope > .lf-grip"), "return");
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
          if (
            ["pointercancel", "touchcancel"].includes(evt.originalEvent.type) ||
            evt.originalEvent.detail === "cancel"
          ) {
            this.#place(card, from, oldIndex, card.querySelector(":scope > .lf-grip"));
            this.#finishGesture();
            announce(`${this.#title(card)} — move cancelled`);
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
      if (!this.reading) return nothing;
      this.#arrange(this.#placement());
      this.#paintAvailability();
      return nothing;
    }

    // Every column's cards in order: the board's own move state, with each card that
    // shows an answer moved to the column that answer names. Reading the answer here
    // follows its widget's state, so a pick in its section, an undo, a refusal and a
    // revision's retraction all redraw the board. Each column lists its cards by rank,
    // a shown card keeping its authored one.
    #placement() {
      const { value, ranks } = this.state.move;
      const columns = Object.fromEntries(
        Object.entries(value).map(([id, cards]) => [id, [...cards]]),
      );
      for (const card of this.querySelectorAll(":scope > lf-column > lf-card")) {
        const shown = shownAnswer(card);
        const target = shown && this.#columnFor(card, shown.value);
        if (!target || !(target.id in columns)) continue;
        for (const cards of Object.values(columns)) {
          const index = cards.indexOf(card.id);
          if (index >= 0) cards.splice(index, 1);
        }
        columns[target.id].push(card.id);
      }
      // By rank, ties by id, as the position fold orders a column (projection/model.js).
      const key = (id) => [ranks[id] ?? "", id];
      const before = (a, b) => {
        const [x, y] = [key(a), key(b)];
        return x[0] !== y[0] ? (x[0] < y[0] ? -1 : 1) : x[1] < y[1] ? -1 : 1;
      };
      for (const cards of Object.values(columns)) cards.sort(before);
      return columns;
    }

    // Whether the card can stand in `column`: any column for a card the board places,
    // one holding a value its answer can take for a card showing an answer.
    #takes(card, column) {
      const shown = shownAnswer(card);
      return !shown || (column && shown.takes(this.#holds(column, card)));
    }

    #arrange(columns) {
      const cards = [...this.querySelectorAll(":scope > lf-column > lf-card")];
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
      for (const card of cards) {
        const last = card.getBoundingClientRect();
        const dx = first.get(card).left - last.left;
        const dy = first.get(card).top - last.top;
        if (dx || dy) {
          const played = motion(
            card,
            [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }],
            150,
          );
          if (played) movements.push(played.finished);
        }
      }
      layoutChanged(this);
      if (movements.length)
        void Promise.allSettled(movements).then(() => layoutChanged(this));
    }
  },
);
