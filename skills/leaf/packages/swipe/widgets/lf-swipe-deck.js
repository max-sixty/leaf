/* lf-swipe-deck: a position-recorded classification queue with one activation path.
 * The Pass and Keep buttons own the semantic action. Arrow keys and pointer swipes call
 * those buttons, whose click handler first places one card optimistically and then sends
 * the same absolute action the runtime replays after reload, sync, or undo. A classified
 * card can withdraw its own action and return to the queue. The final classification is
 * `finish`: that one event both places its card and completes the deck's Ask, so returning
 * that card restores both. Complete projection supplies the ordered cards in every pile;
 * this module places the retained nodes and carries only the live pointer gesture. A
 * card's parent pile presents whether it is unseen, passed, or kept. The complete
 * painted reading is memoized, so a broad action heartbeat that changes no deck state
 * writes nothing and repaints keyboard scopes only when action availability changes.
 *
 * Piles remain labeled lists in quoted exhibits and static copies. Quoted decks stop at
 * that structure: no controls, tab stops, key scope, or pointer listeners are installed.
 * The active card alone takes horizontal motion. Its exit is a short generated visual
 * echo so the real card can occupy its recorded destination immediately; `motion` makes
 * that echo still under reduced motion and during initial state projection. */
import {
  dragging,
  commands,
  layoutChanged,
  motion,
  once,
  offer,
  paintKeys,
  quoted,
  widgetController,
  worksInside,
} from "/runtime/widget-api.js";

const VERDICTS = {
  unseen: "Queue",
  pass: "Passed",
  keep: "Kept",
};

customElements.define(
  "lf-swipe-deck",
  class extends HTMLElement {
    #pass = null;
    #keep = null;
    #progress = null;
    #pointer = null;
    #interactive = false;
    #returning = new Set();
    #painted = null;
    #keysAvailable = null;
    #stop = null;
    #controller = null;

    connectedCallback() {
      if (once(this)) {
        const exhibit = quoted(this);
        this.classList.toggle("lf-swipe-quoted", exhibit);
        this.#structure();
        if (!exhibit) this.#wire();
      }
      if (!this.#interactive) return;
      this.#controller ??= widgetController(this);
      this.#stop ??= this.#controller.subscribe(this.#render);
    }

    disconnectedCallback() {
      this.#stop?.();
      this.#stop = null;
      this.#painted = null;
      this.#keysAvailable = null;
      this.#restorePointer();
    }

    #piles() {
      return [...this.querySelectorAll(":scope > lf-swipe-pile")];
    }

    #pile(verdict) {
      return this.#piles().find((pile) => pile.getAttribute("verdict") === verdict);
    }

    #cards(pile) {
      return pile ? [...pile.querySelectorAll(":scope > lf-swipe-card")] : [];
    }

    #active() {
      return this.#cards(this.#pile("unseen"))[0] ?? null;
    }

    #structure() {
      this.setAttribute("role", "group");
      const heading = this.closest("lf-ask")?.querySelector(
        ":scope > :is(h1, h2, h3, h4, h5, h6)",
      );
      this.setAttribute(
        "aria-label",
        heading?.textContent.trim() || "Card classification",
      );
      for (const pile of this.#piles()) {
        const verdict = pile.getAttribute("verdict");
        const label = VERDICTS[verdict] ?? verdict;
        pile.setAttribute("role", "list");
        pile.setAttribute("aria-label", label);
        for (const card of this.#cards(pile)) card.setAttribute("role", "listitem");
        if (pile.querySelector(':scope > [data-lf-said="verdict"]')) continue;
        const heading = document.createElement("span");
        heading.dataset.lfSaid = "verdict";
        heading.dataset.lfGen = "1";
        heading.className = "lf-swipe-pile-label";
        heading.setAttribute("aria-hidden", "true");
        heading.textContent = `${label} · ${this.#cards(pile).length}`;
        pile.prepend(heading);
      }
    }

    #wire() {
      this.#interactive = true;
      const controls = offer("div", "lf-swipe-controls");
      this.#pass = offer("button", "lf-swipe-pass", "← Pass");
      this.#progress = document.createElement("span");
      this.#progress.className = "lf-swipe-progress lf-ui";
      this.#progress.dataset.lfGen = "1";
      this.#progress.setAttribute("role", "status");
      this.#progress.setAttribute("aria-live", "polite");
      this.#progress.tabIndex = -1;
      this.#keep = offer("button", "lf-swipe-keep", "Keep →");
      controls.append(this.#pass, this.#progress, this.#keep);
      this.append(controls);

      for (const card of this.#piles().flatMap((pile) => this.#cards(pile)))
        this.#returnControl(card);

      this.#pass.addEventListener("click", () => this.#swipe("pass", -1));
      this.#keep.addEventListener("click", () => this.#swipe("keep", 1));
      commands(
        this,
        "In a swipe deck",
        [
          {
            id: "swipe.pass",
            keys: ["ArrowLeft"],
            control: this.#pass,
            decision: "Pass",
            does: "Pass the active card",
            line: "pass the active card",
            when: () => this.#canSwipe(),
            run: () => this.#pass.click(),
          },
          {
            id: "swipe.keep",
            keys: ["ArrowRight"],
            control: this.#keep,
            decision: "Keep",
            does: "Keep the active card",
            line: "keep the active card",
            when: () => this.#canSwipe(),
            run: () => this.#keep.click(),
          },
        ],
        {
          answer: () =>
            `${this.#cards(this.#pile("keep")).length} kept · ${
              this.#cards(this.#pile("pass")).length
            } passed`,
        },
      );

      this.addEventListener("pointerdown", this.#pointerDown);
      this.addEventListener("pointermove", this.#pointerMove);
      this.addEventListener("pointerup", this.#pointerUp);
      this.addEventListener("pointercancel", this.#pointerCancel);
      this.addEventListener("lostpointercapture", this.#pointerCancel);
    }

    #canSwipe() {
      const action = this.#action();
      return Boolean(action && this.#controller.read().actions[action]?.available);
    }

    #action() {
      const queued = this.#cards(this.#pile("unseen")).length;
      if (!queued) return null;
      return queued === 1 ? "finish" : "swipe";
    }

    #render = () => {
      if (!this.#interactive) return;
      const active = this.#active();
      const action = this.#action();
      const available = Boolean(
        active && action && this.#controller.read().actions[action]?.available,
      );
      const unseen = this.#cards(this.#pile("unseen"));
      const classified =
        this.#cards(this.#pile("pass")).length + this.#cards(this.#pile("keep")).length;
      const progress = unseen.length
        ? `${unseen.length} queued · ${classified} done`
        : `All done! · ${classified} classified`;
      const piles = this.#piles().map((pile) => ({
        pile,
        verdict: pile.getAttribute("verdict"),
        cards: this.#cards(pile).map((card) => ({
          card,
          active: card === active && available,
          returnable: Boolean(this.#returnable(card)),
          returning: this.#returning.has(card.id),
        })),
      }));
      const reading = JSON.stringify({
        available,
        progress,
        piles: piles.map(({ verdict, cards }) => ({
          verdict,
          cards: cards.map(({ card, active, returnable, returning }) => ({
            id: card.id,
            active,
            returnable,
            returning,
          })),
        })),
      });
      if (reading === this.#painted) return;

      const keysMoved = available !== this.#keysAvailable;
      this.#pass.disabled = !available;
      this.#keep.disabled = !available;
      this.#progress.textContent = progress;

      for (const { pile, verdict, cards } of piles) {
        for (const { card, active, returnable, returning } of cards) {
          card.tabIndex = active ? 0 : -1;
          const button = card.querySelector(":scope > .lf-swipe-return");
          if (!button) continue;
          button.hidden = !returnable;
          button.disabled = returning;
        }
        const label = pile.querySelector(':scope > [data-lf-said="verdict"]');
        if (label) label.textContent = `${VERDICTS[verdict]} · ${cards.length}`;
      }
      if (keysMoved) paintKeys();
      this.#keysAvailable = available;
      this.#painted = reading;
    };

    #returnable(card) {
      const { actions } = this.#controller.read();
      return ["finish", "swipe"]
        .flatMap((action) => actions[action]?.undo ?? [])
        .find((event) => event.detail?.card === card.id);
    }

    #returnControl(card) {
      const button = offer("button", "lf-swipe-return", "Return to queue");
      const title =
        card.querySelector(":scope > strong")?.textContent.trim() || card.id;
      button.setAttribute("aria-label", `Return ${title} to queue`);
      button.hidden = true;
      button.addEventListener("click", async () => {
        const event = this.#returnable(card);
        if (!event || this.#returning.has(card.id)) return;
        const refocus = document.activeElement === button;
        this.#returning.add(card.id);
        this.#render();
        let returned = false;
        try {
          returned = Boolean(
            await this.#controller.dispatch({
              kind: "undo",
              target: event.attempt ?? event.id,
            })?.delivery,
          );
        } finally {
          this.#returning.delete(card.id);
          if (this.isConnected) this.#render();
        }
        if (refocus)
          (returned ? this.#active() : button).focus({ preventScroll: true });
      });
      card.append(button);
    }

    #place(card, destination, index) {
      const without = this.#cards(destination).filter(
        (candidate) => candidate !== card,
      );
      const bounded = Math.min(index, without.length);
      if (
        card.parentElement === destination &&
        this.#cards(destination).indexOf(card) === bounded
      )
        return false;
      destination.insertBefore(card, without[bounded] ?? null);
      return true;
    }

    #swipe(verdict, direction) {
      const action = this.#action();
      if (!action || !this.#controller.read().actions[action]?.available) return;
      const card = this.#active();
      const destination = this.#pile(verdict);
      if (!card || !destination) return;

      const focusWasInside = this.contains(document.activeElement);
      const focusWasCard = card === document.activeElement;
      this.#exit(card, direction);
      this.#restorePointer();
      const detail = {
        card: card.id,
        to: destination.id,
        index: this.#cards(destination).length,
      };
      this.#place(card, destination, detail.index);
      this.#render();
      layoutChanged(this);

      const next = this.#active();
      if (focusWasCard && next) next.focus({ preventScroll: true });
      else if (focusWasInside && !next) this.#progress.focus({ preventScroll: true });
      void this.#controller.dispatch({ kind: "action", verb: action, detail })
        ?.delivery;
    }

    #exit(card, direction) {
      const rect = card.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const echo = card.cloneNode(true);
      echo.removeAttribute("id");
      for (const node of echo.querySelectorAll("[id]")) node.removeAttribute("id");
      echo.classList.remove("lf-swipe-dragging");
      echo.classList.add("lf-swipe-exit");
      echo.dataset.lfGen = "1";
      echo.setAttribute("aria-hidden", "true");
      echo.setAttribute("inert", "");
      Object.assign(echo.style, {
        position: "fixed",
        inset: "auto",
        left: `${rect.left}px`,
        top: `${rect.top}px`,
        width: `${rect.width}px`,
        height: `${rect.height}px`,
        margin: "0",
        transform: "none",
      });
      document.body.append(echo);
      const played = motion(
        echo,
        [
          { transform: "translateX(0)", opacity: 1 },
          {
            transform: `translateX(${direction * Math.max(240, rect.width * 0.8)}px)`,
            opacity: 0,
          },
        ],
        170,
      );
      if (!played) {
        echo.remove();
        return null;
      }
      played.finished.then(
        () => echo.remove(),
        () => echo.remove(),
      );
      return played;
    }

    #restorePointer() {
      const gesture = this.#pointer;
      this.#pointer = null;
      if (!gesture) return;
      if (gesture.card.hasPointerCapture?.(gesture.id))
        gesture.card.releasePointerCapture(gesture.id);
      gesture.card.classList.remove("lf-swipe-dragging");
      gesture.card.style.removeProperty("--lf-swipe-drag-x");
      dragging(this, false);
    }

    #pointerDown = (event) => {
      const card = event.target.closest?.("lf-swipe-card");
      if (
        event.button !== 0 ||
        card !== this.#active() ||
        !this.#canSwipe() ||
        worksInside(event.target, card)
      )
        return;
      this.#pointer = {
        id: event.pointerId,
        card,
        x: event.clientX,
        y: event.clientY,
        dragging: false,
      };
      card.setPointerCapture(event.pointerId);
      dragging(this, true);
    };

    #pointerMove = (event) => {
      const gesture = this.#pointer;
      if (!gesture || gesture.id !== event.pointerId) return;
      const dx = event.clientX - gesture.x;
      const dy = event.clientY - gesture.y;
      if (!gesture.dragging) {
        if (Math.abs(dx) < 8 || Math.abs(dx) <= Math.abs(dy)) return;
        gesture.dragging = true;
        gesture.card.classList.add("lf-swipe-dragging");
        window.getSelection()?.removeAllRanges();
      }
      event.preventDefault();
      gesture.card.style.setProperty("--lf-swipe-drag-x", `${dx}px`);
    };

    #pointerUp = (event) => {
      const gesture = this.#pointer;
      if (!gesture || gesture.id !== event.pointerId) return;
      const dx = event.clientX - gesture.x;
      const threshold = gesture.card.getBoundingClientRect().width * 0.28;
      const commits = gesture.dragging && Math.abs(dx) >= threshold;
      if (!commits) {
        this.#restorePointer();
        return;
      }
      (dx < 0 ? this.#pass : this.#keep).click();
    };

    #pointerCancel = (event) => {
      if (this.#pointer?.id === event.pointerId) this.#restorePointer();
    };

    renderState(state) {
      if (this.#pointer) return false;
      const focused = document.activeElement;
      const focusedCard =
        this.#interactive &&
        focused?.localName === "lf-swipe-card" &&
        focused.closest("lf-swipe-deck") === this;
      const cards = this.#piles().flatMap((pile) => this.#cards(pile));
      // A position facet keeps action metadata on its units. Work newest-first so one
      // state read that brings several classifications animates the last arrival; all
      // cards still reach their complete projected placement below. During initial
      // projection motion() returns null, so standing units load directly at rest.
      const transitions = Object.values(state.verdict.units ?? {}).reverse();
      const transition = transitions.find(({ action, detail }) => {
        const card = detail?.card
          ? cards.find((candidate) => candidate.id === detail.card)
          : null;
        const destination = detail?.to ? document.getElementById(detail.to) : null;
        return (
          ["swipe", "finish"].includes(action) &&
          card?.parentElement?.getAttribute("verdict") === "unseen" &&
          destination?.closest("lf-swipe-deck") === this &&
          ["pass", "keep"].includes(destination.getAttribute("verdict"))
        );
      });
      const detail = transition?.detail;
      const movingCard = detail?.card
        ? cards.find((candidate) => candidate.id === detail.card)
        : null;
      const destination = detail?.to ? document.getElementById(detail.to) : null;
      const verdict = destination?.getAttribute("verdict");
      const played = transition
        ? this.#exit(movingCard, verdict === "pass" ? -1 : 1)
        : null;
      let moved = false;
      for (const [id, order] of Object.entries(state.verdict.value)) {
        const destination = document.getElementById(id);
        if (destination?.closest("lf-swipe-deck") !== this) continue;
        order.forEach((id, index) => {
          const card = cards.find((candidate) => candidate.id === id);
          if (card && this.#place(card, destination, index)) moved = true;
        });
      }
      this.#render();
      if (focusedCard && focused !== this.#active())
        (this.#active() ?? this.#progress).focus({ preventScroll: true });
      else if (focused?.isConnected && document.activeElement !== focused)
        focused.focus({ preventScroll: true });
      if (moved) layoutChanged(this);
      return played;
    }
  },
);

export const interactionGalleryScenario = {
  reset(root) {
    const deck = root.querySelector("lf-swipe-deck");
    const card = deck.querySelector("lf-swipe-card");
    const piles = [...deck.querySelectorAll(":scope > lf-swipe-pile")];
    deck.renderState({
      verdict: {
        units: {},
        value: Object.fromEntries(
          piles.map((pile) => [
            pile.id,
            pile.getAttribute("verdict") === "unseen" ? [card.id] : [],
          ]),
        ),
      },
    });
  },
  async play({ root, arrive, press, track, until, finish }) {
    await arrive();
    const deck = root.querySelector("lf-swipe-deck");
    const keep = deck.querySelector(".lf-swipe-keep");
    await press(keep);
    const card = deck.querySelector("lf-swipe-card");
    const piles = [...deck.querySelectorAll(":scope > lf-swipe-pile")];
    const keepPile = piles.find((pile) => pile.getAttribute("verdict") === "keep");
    await track(
      deck.renderState({
        verdict: {
          units: {
            [card.id]: {
              action: "finish",
              value: keepPile.id,
              detail: { card: card.id, to: keepPile.id, index: 0 },
            },
          },
          value: Object.fromEntries(
            piles.map((pile) => [pile.id, pile === keepPile ? [card.id] : []]),
          ),
        },
      }),
    );
    await until(
      () =>
        deck.querySelector("lf-swipe-card").parentElement?.getAttribute("verdict") ===
        "keep",
      "the swipe card did not move to Kept",
    );
    await finish();
  },
};
