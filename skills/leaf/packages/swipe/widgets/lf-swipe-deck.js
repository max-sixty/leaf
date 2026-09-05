/* lf-swipe-deck: a position-recorded classification queue with one activation path.
 * The Pass and Keep buttons own the semantic action. Arrow keys and pointer swipes call
 * those buttons, whose click handler first places one card optimistically and then sends
 * the same absolute action the runtime replays after reload, sync, or undo. The final
 * classification is `finish`: that one event both places its card and completes the
 * deck's Ask, so one undo restores both. Complete projection supplies the ordered cards
 * in every pile; this module places the retained nodes and carries only the live pointer
 * gesture. A card's parent pile presents whether it is unseen, passed, or kept.
 *
 * Piles remain labeled lists in quoted exhibits and static copies. Quoted decks stop at
 * that structure: no controls, tab stops, key scope, or pointer listeners are installed.
 * The active card alone takes horizontal motion. Its exit is a short generated visual
 * echo so the real card can occupy its recorded destination immediately; `motion` makes
 * that echo still under reduced motion and during initial state projection. */
import {
  actionAvailable,
  dragging,
  commands,
  layoutChanged,
  motion,
  once,
  offer,
  paintKeys,
  quoted,
  sendAction,
  undoableAction,
  watchActions,
  withdraw,
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
    #undo = null;
    #progress = null;
    #pointer = null;
    #interactive = false;
    #stop = null;

    connectedCallback() {
      if (once(this)) {
        const exhibit = quoted(this);
        this.classList.toggle("lf-swipe-quoted", exhibit);
        this.#structure();
        if (!exhibit) this.#wire();
      }
      if (!this.#interactive) return;
      this.#stop ??= watchActions(this, null, this.#render);
    }

    disconnectedCallback() {
      this.#stop?.();
      this.#stop = null;
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
      this.setAttribute("aria-label", "Technical design triage");
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
        heading.textContent = label;
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
      this.#undo = offer("button", "lf-swipe-undo", "Undo last swipe");
      this.#undo.hidden = true;
      controls.append(this.#pass, this.#progress, this.#keep, this.#undo);
      this.append(controls);

      this.#pass.addEventListener("click", () => this.#swipe("pass", -1));
      this.#keep.addEventListener("click", () => this.#swipe("keep", 1));
      this.#undo.addEventListener("click", async () => {
        const event = undoableAction(this, "finish");
        if (event) await withdraw(event);
      });
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
      return action !== null && actionAvailable(this, action);
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
      const available = Boolean(active && action && actionAvailable(this, action));
      this.#pass.disabled = !available;
      this.#keep.disabled = !available;
      this.#undo.hidden = !undoableAction(this, "finish");

      const unseen = this.#cards(this.#pile("unseen"));
      const classified =
        this.#cards(this.#pile("pass")).length + this.#cards(this.#pile("keep")).length;
      this.#progress.textContent = unseen.length
        ? `${unseen.length} queued · ${classified} done`
        : `${classified} done · queue clear`;

      for (const pile of this.#piles()) {
        const cards = this.#cards(pile);
        for (const card of cards) card.tabIndex = card === active && available ? 0 : -1;
        const label = pile.querySelector(':scope > [data-lf-said="verdict"]');
        if (label)
          label.textContent = `${VERDICTS[pile.getAttribute("verdict")]} · ${cards.length}`;
      }
      paintKeys();
    };

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
      if (!action || !actionAvailable(this, action)) return;
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
      void sendAction(this, action, detail);
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
        return;
      }
      played.finished.then(
        () => echo.remove(),
        () => echo.remove(),
      );
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
    }
  },
);
