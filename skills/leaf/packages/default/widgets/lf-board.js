/* lf-board: the one widget the user edits directly, movable two ways that
 * share one send path and one gesture gate. Dragging is wired via the vendored
 * SortableJS (pointer-driven `forceFallback` mode, so touch works and the
 * follower is stylable — native HTML5 DnD is not used). The grip is a press
 * (`offer`), so the keyboard path needs no pointer: Enter grabs, arrows restate
 * the card's placement (announced through the live region), Enter drops, and
 * Escape or focus loss restores the origin. Either way the board wears
 * .lf-dragging for the whole gesture — the runtime's poll gates on it (no
 * version-follow, no foreign-action replay mid-gesture) — and a completed move
 * reports through #send as one absolute `move` action, indistinguishable on
 * the wire. renderState receives every column's final ordered card ids. One render
 * preserves native nodes, syncs a second tab, and no-ops on the sender. Presentation is theme CSS; authored content
 * is never replaced, so there is no failSoft.
 *
 * The board also says what it is non-visually: columns are labeled lists and
 * cards their items (#structure), and each grip is named for the column its
 * card now sits in and whether its move awaits a version (#names). Both are
 * attributes on authored elements — the light DOM stays verbatim, which is
 * what the anchor pass and the version diff walk. The theme's column heading
 * is CSS generated content with empty alt text, so the label reaches the tree
 * once, as the list's name, rather than twice. */
import Sortable from "/vendor/sortable.esm.js";
import {
  actionAvailable,
  once,
  offer,
  quoted,
  says,
  sendAction,
  notice,
  announce,
  commands,
  labelOf,
  measure,
  saying,
  watchActions,
  dragging,
  motion,
  scrollerFor,
  PRESS,
  onMotionPreferenceChange,
  reducedMotion,
  scrollBehavior,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-board",
  class extends HTMLElement {
    #grabbed = null; // {card, grip, from, index} — the origin, for cancel and no-op drops
    #superseded = null; // a grab folded into a pointer drag of the same card (see onStart)
    #rows = new WeakMap(); // grip → its declared rows, for the grab announcement
    #namesObserver = null;
    #sortables = new Set();
    #stopActions = null;
    #stopMotion = null;

    connectedCallback() {
      if (!once(this)) {
        if (!quoted(this)) {
          this.#stopActions ??= watchActions(this, null, this.#paintAvailability);
          for (const col of this.querySelectorAll(":scope > lf-column"))
            this.#sortable(col);
        }
        this.#observeNames();
        this.#observeMotion();
        return;
      }
      this.#structure();
      // A quoted board is an exhibit: no grips, no sortable, no grip keys in
      // the "?" overlay — it stays the static board the theme renders anyway.
      if (quoted(this)) return;
      // Own cards only (:scope-deep would double-wire a nested board's cards).
      for (const card of this.querySelectorAll(":scope > lf-column > lf-card"))
        this.#grip(card);
      // The room a card's text keeps clear of its grip, measured off the grip's own
      // box rather than stated as a number (the pick column's answer): the theme
      // spends it (--lf-grip-room), and only a board that grew grips states it, so
      // paper, copies and quoted boards hold no dead column.
      // Off the grip's own box, so it waits for one (`measure`): a board quoted into
      // a reply is built into the thread panel, which may not be open yet.
      measure(this, () => {
        const grip = this.querySelector(":scope > lf-column > lf-card > .lf-grip");
        if (grip)
          this.style.setProperty(
            "--lf-grip-room",
            Math.ceil(grip.getBoundingClientRect().width) + "px",
          );
      });
      for (const col of this.querySelectorAll(":scope > lf-column"))
        this.#sortable(col);
      this.#stopActions ??= watchActions(this, null, this.#paintAvailability);
      this.#observeMotion();
      this.#names();
      // Grip names come from where their cards sit and whether the runtime has
      // marked the placement as their move, so mutations of those two inputs
      // restate them — not the four paths that move a card (arrow step, drag,
      // cancel, replay) plus the origin pass, any of which would eventually
      // forget. Only the origin attribute is observed, so #names writing an
      // aria-label cannot feed the pass back into itself.
      this.#observeNames();
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
    // the line the layer's CLAUDE.md draws and lf-milestone's chips are the
    // other case of.
    #structure() {
      for (const col of this.querySelectorAll(":scope > lf-column")) {
        col.setAttribute("role", "list");
        col.setAttribute("aria-label", col.getAttribute("label"));
        for (const card of this.#cards(col)) card.setAttribute("role", "listitem");
        if (col.querySelector(':scope > [data-lf-said="label"]')) continue;
        const heading = document.createElement("span");
        heading.dataset.lfSaid = "label";
        heading.dataset.lfGen = "1";
        // The column already carries these words as its name, so the heading is
        // the visible half only: the tree hears them once, the user can still
        // select them, and the theme's generated copy is left to the no-script case.
        heading.setAttribute("aria-hidden", "true");
        heading.textContent = col.getAttribute("label");
        col.prepend(heading);
      }
    }

    // Every grip's name, in the idiom the live region already announces moves in
    // ("card — column"): the user who lands on a grip by Tab hears where the
    // card is without having read the list it sits in, and whether the placement comes
    // from their move after its transient announcement has faded.
    #names() {
      for (const col of this.querySelectorAll(":scope > lf-column")) {
        const where = col.getAttribute("label");
        for (const card of this.#cards(col)) {
          const origin = card.hasAttribute("data-lf-reader-override")
            ? " — your move"
            : "";
          const name = `Move: ${this.#title(card)} — ${where}${origin}`;
          const grip = card.querySelector(":scope > .lf-grip");
          if (grip && grip.getAttribute("aria-label") !== name)
            grip.setAttribute("aria-label", name);
        }
      }
    }

    // A board inside a Claude reply detaches when its thread's node is rebuilt —
    // resolving is the occasion the reconciled panel leaves, its cached body
    // re-adopted into the new node — and no blur fires for a detached grip, so
    // drop a live grab here or it wedges the .lf-dragging gate open — freezing
    // action replay and version-follow.
    disconnectedCallback() {
      this.#stopActions?.();
      this.#stopActions = null;
      this.#namesObserver?.disconnect();
      this.#namesObserver = null;
      this.#stopMotion?.();
      this.#stopMotion = null;
      if (this.#grabbed) this.#cancel();
      this.#superseded = null;
      dragging(this, false);
      for (const sortable of this.#sortables) sortable.destroy();
      this.#sortables.clear();
    }

    #observeMotion() {
      if (this.#stopMotion || !this.#sortables.size) return;
      for (const sortable of this.#sortables)
        sortable.option("animation", reducedMotion() ? 0 : 150);
      this.#stopMotion = onMotionPreferenceChange((reduced) => {
        for (const sortable of this.#sortables)
          sortable.option("animation", reduced ? 0 : 150);
      });
    }

    #paintAvailability = () => {
      const available = actionAvailable(this, "move");
      for (const sortable of this.#sortables) sortable.option("disabled", !available);
      for (const grip of this.querySelectorAll(
        ":scope > lf-column > lf-card > .lf-grip",
      )) {
        grip.setAttribute("aria-disabled", String(!available));
        grip.tabIndex = available ? 0 : -1;
      }
    };

    #observeNames() {
      if (
        this.#namesObserver ||
        !this.querySelector(":scope > lf-column > lf-card > .lf-grip")
      )
        return;
      this.#namesObserver = new MutationObserver(() => this.#names());
      for (const col of this.querySelectorAll(":scope > lf-column")) {
        this.#namesObserver.observe(col, { childList: true });
        for (const card of this.#cards(col))
          this.#namesObserver.observe(card, {
            attributes: true,
            attributeFilter: ["data-lf-reader-override"],
          });
      }
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
    // therefore cannot be stranded by a press that moves the reader elsewhere, which is
    // what suspending the page would have been for.
    #keys(card, grip) {
      const held = () => this.#grabbed?.grip === grip;
      const grab = {
        id: "board.grab",
        keys: PRESS,
        does: "Grab the card",
        line: "grab the card",
        // .lf-dragging without a grab is a live pointer drag — one gesture at a time.
        when: () =>
          actionAvailable(this, "move") &&
          !held() &&
          !this.classList.contains("lf-dragging"),
        run: () => this.#grab(card, grip),
      };
      // The tooltip names the keys the row binds rather than a letter typed beside it: the
      // grip answers Space too, and said Enter on every surface for as long as the word and
      // the press were separate objects.
      grip.title = `Drag to move — or ${labelOf(grab)} to grab`;
      return commands(grip, "On a card grip", [
        grab,
        {
          id: "board.move",
          keys: ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"],
          routes: [
            { id: "board.move-up", binding: "ArrowUp", does: "Move it up" },
            { id: "board.move-down", binding: "ArrowDown", does: "Move it down" },
            { id: "board.move-left", binding: "ArrowLeft", does: "Move it left" },
            { id: "board.move-right", binding: "ArrowRight", does: "Move it right" },
          ],
          label: "arrows",
          does: "Move it",
          line: "move",
          when: held,
          repeat: true,
          run: (binding) =>
            this.#step(
              card,
              grip,
              { ArrowLeft: -1, ArrowRight: 1 }[binding] ?? 0,
              { ArrowUp: -1, ArrowDown: 1 }[binding] ?? 0,
            ),
        },
        {
          id: "board.drop",
          keys: PRESS,
          does: "Drop it here",
          line: "drop",
          when: held,
          run: () => this.#drop(),
        },
        {
          id: "board.cancel",
          keys: ["Escape"],
          does: "Cancel the move",
          line: "cancel the move",
          when: held,
          run: () => this.#cancel(true),
        },
      ]);
    }
    #grip(card) {
      const grip = offer("button", "lf-grip", "⠿");
      this.#rows.set(grip, this.#keys(card, grip));
      // Leaving the grip drops the grab: restore the origin. Arrow moves reparent
      // the grip (which blurs it) and synchronously refocus, so by the time this
      // settles only a real departure still lacks focus.
      grip.addEventListener("blur", () => {
        if (this.#grabbed?.grip !== grip) return;
        setTimeout(() => {
          if (this.#grabbed?.grip === grip && document.activeElement !== grip)
            this.#cancel();
        });
      });
      card.append(grip);
    }

    #grab(card, grip) {
      if (!actionAvailable(this, "move")) return;
      const from = card.parentElement;
      const cards = this.#cards(from);
      const index = cards.indexOf(card);
      this.#grabbed = { card, grip, from, index };
      dragging(this, true);
      card.classList.add("lf-lift");
      // Where the card starts, in the idiom every arrow step announces — a reader about to
      // move it needs the position the moves count from.
      announce(
        `${this.#title(card)} grabbed — ${from.getAttribute("label")}, position ${
          index + 1
        } of ${cards.length} — ${saying(this.#rows.get(grip))}`,
      );
    }

    #step(card, grip, dCol, dRow) {
      const col = card.parentElement;
      if (dRow) {
        const cards = this.#cards(col);
        const to = cards.indexOf(card) + dRow;
        if (to < 0 || to >= cards.length) return;
        this.#place(card, col, to);
      } else {
        const cols = [...this.querySelectorAll(":scope > lf-column")];
        const target = cols[cols.indexOf(col) + dCol];
        if (!target) return;
        // Same visual index; #place clamps to the target's end.
        this.#place(card, target, this.#cards(col).indexOf(card));
      }
      grip.focus({ preventScroll: true }); // reparenting blurred it (Chromium)
      card.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
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
      if (to === from && this.#cards(to).indexOf(card) === index) return;
      this.#send(card, from, to);
    }

    #cancel(refocus = false) {
      const { card, grip, from, index } = this.#grabbed;
      this.#release();
      this.#place(card, from, index);
      if (refocus) grip.focus({ preventScroll: true }); // Esc keeps focus; blur means it left
      announce(`${this.#title(card)} — move cancelled`);
    }

    // The one writer of "no card is held", so the grip's rows change back here and nowhere
    // else — a drop and a cancel each used to restate it, and a third way out would have
    // had to remember.
    #release() {
      this.#grabbed.card.classList.remove("lf-lift");
      this.#grabbed = null;
      dragging(this, false);
    }

    // The one writer of "card X sits at index i among column C's cards": arrow steps,
    // a cancelled grab, refusal reconciliation, and replay all place through it. Every
    // placement FLIPs from where the card stood, so a move reads as motion wherever it
    // came from — a restore arriving at response time has no gesture behind it, which
    // is the case the norm says needs the motion more. A FLIP already in flight is
    // cancelled before measuring, or its transform would be read as position.
    #place(card, col, index) {
      for (const a of card.getAnimations()) a.cancel();
      const first = card.getBoundingClientRect();
      const rest = this.#cards(col).filter((c) => c !== card);
      col.insertBefore(card, rest[index] ?? null);
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

    // One completed move, drag or keyboard: an absolute placement, sent once. The
    // notice's word follows the branch the reader can see — a card kept in its column
    // was reordered, not moved to where it already was. A refusal is restored by the
    // layer from the declared record plus its outbox, never from this gesture's DOM
    // snapshot: that snapshot may be another queued move the server also refused.
    #send(card, from, to) {
      sendAction(this, "move", {
        card: card.id,
        to: to.id,
        index: this.#cards(to).indexOf(card),
      }).then((ok) => {
        if (ok)
          notice(
            `${to === from ? "Reordered in" : "Moved to"} ${to.getAttribute(
              "label",
            )} — recorded`,
          );
      });
    }

    #sortable(col) {
      const sortable = new Sortable(col, {
        disabled: !actionAvailable(this, "move"),
        group: `board-${this.id}`, // per board: two boards on a page don't cross-drag
        draggable: "lf-card",
        handle: ".lf-grip",
        // Named because a board an agent sent in a reply is scrolled by the panel's list,
        // while one in the page is scrolled by the browser root. Sortable cannot infer
        // that product boundary from the board alone.
        scroll: scrollerFor(this),
        forceFallback: true, // pointer-driven: stylable follower, touch, no native ghost
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
          dragging(this, true);
        },
        onEnd: (evt) => {
          // Ahead of the branches below, because the one that returns early sends
          // nothing: a card dropped where it was picked up puts the hand down with
          // nothing following it to say so.
          dragging(this, false);
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
          if (from === to && oldIndex === newIndex) return;
          this.#send(card, from, to);
        },
      });
      this.#sortables.add(sortable);
    }

    // The complete column composition names every card in its final order. Measure
    // once around that placement so FLIP animates the resulting layout together.
    renderState(state) {
      const columns = state.placement.value;
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
          for (const animation of card.getAnimations()) animation.cancel();
          return [card, card.getBoundingClientRect()];
        }),
      );
      const focus = document.activeElement;
      for (const [id, order] of Object.entries(columns)) {
        const column = document.getElementById(id);
        if (!column || column.closest("lf-board") !== this) continue;
        order.forEach((id, index) => {
          const card = cards.find((candidate) => candidate.id === id);
          if (card && this.#cards(column)[index] !== card)
            column.insertBefore(card, this.#cards(column)[index] ?? null);
        });
      }
      if (focus?.isConnected && document.activeElement !== focus)
        focus.focus({ preventScroll: true });
      for (const card of cards) {
        const last = card.getBoundingClientRect();
        const dx = first.get(card).left - last.left;
        const dy = first.get(card).top - last.top;
        if (dx || dy)
          motion(
            card,
            [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }],
            150,
          );
      }
    }
  },
);
