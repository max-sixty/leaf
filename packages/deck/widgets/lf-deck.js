/* lf-deck: a pile of cards worked through one at a time, as Slack's Catch up works
 * through unread conversations. Each authored child is a card, an `lf-ask` or a
 * decision widget the user answers there with its own controls. A card waits while it
 * holds an obligation open on the user (`obligationsIn`, read from the server's
 * inventory, the rule `lf-tally` counts by). When the server's reading says the open
 * card no longer waits, after the user answered it on the card or on a control standing
 * for it, such as a suggestion's margin entry, the card flies right and the next waiting
 * card after it comes up. A wait that ends anywhere else, as when
 * the user comments on the card and leaves it with the agent, or the agent ends the
 * question, leaves the card where it is with Next, since news never moves what the user
 * is reading. Later sends a card left and leaves its obligation open, which is Leaf's
 * keep unread: nothing is recorded, the pass ends with the cards kept for later still
 * waiting, and Go through starts again from the first of them. Back returns to the card
 * before, where the widget's own controls change an answer. Until the page's first
 * reading is in, as offline, Later and Next step to the next card in order.
 *
 * Which card is open is view state for this user, as a tab set's open panel is
 * (`x-views`): the runtime names the opening card (`openingView`), the module records
 * each card it shows (`keepView`), so a reload comes back to it, and no event carries
 * it. Inactive cards are `hidden="until-found"`, so find-in-page, a fragment and the On
 * walk (`m`, `obligationActions.next`) open the card holding what they reach
 * (`beforematch`, `lf-reveal`); `m` is therefore the keyboard's Later, and a card the
 * walk leaves behind stays waiting for the end of the pass.
 *
 * The bar above the cards holds Back, the tally's count of the deck's obligations
 * (`tallyWords`) with a mark per card, and one forward control: Later on a waiting
 * card, Next on any other, then Go through or Review once the pass is over. It stands
 * above the card, and the forward control keeps the room of its widest label, so cards
 * of different heights and changing labels never move a control under the pointer; for
 * the same reason a card that comes up takes no press until it has settled. A touch
 * drag across the card sends it either way: left is Later, right is Next once the card
 * no longer waits, and a short or early drag settles back. A mouse or pen drag stays
 * text selection, which comments start from. Unupgraded, and on paper, the cards stand
 * one after another. */
import {
  agentName,
  dragging,
  focusDestination,
  focused,
  currentLocationIn,
  keepView,
  keeps,
  layoutChanged,
  LeafElement,
  motion,
  obligationsIn,
  offer,
  offered,
  placeOf,
  openingView,
  quoted,
  readObligations,
  scrollBehavior,
  scrollIntoView,
  signal,
  tally,
  tallyWords,
  under,
  whileConnected,
  html,
  nothing,
} from "/runtime/widget-api.js";

// How far a touch drag travels before a release sends the card; how long a card takes
// to leave, and the next to come up; and how long a card that came up takes no press.
const SWIPE = 80;
const LEAVE_MS = 200;
const RISE_MS = 160;
const SETTLE_MS = 250;

// Whether a card's obligations, by the reading, wait on the user.
const waitsOn = (held) =>
  held.some((item) => item.status === "open" && item.next_actor === "user");

const isCard = (node) =>
  node instanceof HTMLElement && !node.matches("script, style, template");

customElements.define(
  "lf-deck",
  class extends LeafElement {
    #bar = null;
    #forward = null;
    #cards = [];
    // The open card, or null once the pass is over.
    #open = signal(null);
    // Whether the open card waited on the user at the last reading, so the reading
    // that ends its wait is the one that can send it on.
    #waited = null;
    // The card the user last pressed in, which an answer by pointer leaves focus
    // outside of where the platform doesn't focus the control pressed.
    #pressed = null;
    #leaving = null;
    #drag = null;

    createRenderRoot() {
      return this.#bar ?? this;
    }

    setup() {
      this.#cards = [...this.children].filter(isCard);
      if (!this.#cards.length) return;
      this.#bar = offer("div", "lf-deck-bar");
      for (const card of this.#cards) {
        card.addEventListener("beforematch", () => this.#show(card));
        card.addEventListener("lf-reveal", (event) => {
          if (this.#open.value !== card) event.detail.replacedView?.();
          event.detail.present?.(this.#show(card));
        });
      }
      this.prepend(this.#bar);
      this.classList.add("lf-rendered");
      this.#show(openingView(this, this.#cards));
      if (quoted(this)) return;
      whileConnected(this, (signal) => {
        const options = { signal };
        this.addEventListener("pointerdown", (event) => this.#press(event), options);
        this.addEventListener("pointermove", (event) => this.#follow(event), options);
        this.addEventListener("pointerup", (event) => this.#release(event), options);
        this.addEventListener("pointercancel", () => this.#settle(), options);
        return () => this.#settle();
      });
    }

    // Each card's obligations, or null until the page's first reading is in.
    #readings() {
      const items = readObligations();
      if (items.phase !== "ready") return null;
      return new Map(this.#cards.map((card) => [card, obligationsIn(card, items.all)]));
    }

    // Show one card, or none once the pass is over, without motion.
    #show(card) {
      this.#leaving?.finish();
      for (const each of this.#cards) {
        keeps(each, "data-lf-deck-open", each === card ? "" : null);
        keeps(each, "hidden", each === card ? null : "until-found");
      }
      if (card === this.#open.value) return Promise.resolve();
      this.#open.value = card;
      this.#waited = null;
      this.#pressed = null;
      if (card) keepView(this, card);
      return layoutChanged(this);
    }

    // Leave the open card toward `side` and bring up `next` (null ends the pass). The
    // leaving card keeps its box over the deck while it flies, so the next card is
    // already in place beneath it.
    #go(next, side) {
      this.#leaving?.finish();
      const card = this.#open.value;
      if (!card || next === card) return this.#show(next);
      // Whether the user is on the leaving card, and whether they came by keyboard,
      // as the browser's focus-visible reading says.
      const inside = currentLocationIn(card);
      const keyed = inside && focused()?.matches(":focus-visible");
      const top = card.offsetTop;
      const flight = motion(
        card,
        [
          { transform: "none", opacity: 1 },
          {
            transform: `translateX(${side === "left" ? -110 : 110}%) rotate(${side === "left" ? -6 : 6}deg)`,
            opacity: 0,
          },
        ],
        LEAVE_MS,
      );
      if (flight) {
        card.style.setProperty("--lf-deck-leave-top", `${top}px`);
        card.setAttribute("data-lf-deck-leaving", side);
        this.setAttribute("data-lf-deck-flying", "");
        this.#leaving = flight;
        const land = () => {
          if (this.#leaving === flight) {
            this.#leaving = null;
            this.removeAttribute("data-lf-deck-flying");
          }
          card.removeAttribute("data-lf-deck-leaving");
          card.style.removeProperty("--lf-deck-leave-top");
          if (this.#open.value !== card) card.setAttribute("hidden", "until-found");
        };
        flight.finished.then(land, land);
      }
      // Bring up the next card beneath the leaving one, which `#show` would land.
      for (const each of this.#cards) {
        keeps(each, "data-lf-deck-open", each === next ? "" : null);
        if (each !== card || !flight)
          keeps(each, "hidden", each === next ? null : "until-found");
      }
      this.#open.value = next;
      this.#waited = null;
      this.#pressed = null;
      if (next) {
        keepView(this, next);
        motion(
          next,
          [
            { transform: "translateY(10px) scale(0.97)", opacity: 0.4 },
            { transform: "none", opacity: 1 },
          ],
          RISE_MS,
        );
        next.setAttribute("data-lf-deck-settling", "");
        setTimeout(() => next.removeAttribute("data-lf-deck-settling"), SETTLE_MS);
      }
      layoutChanged(this);
      // A user who was on the card that left by keyboard goes to the one that came up,
      // where its own keys answer it, or to the forward control once the pass is over.
      // One who pressed lets go of the hidden card, and Tab goes on from where it was.
      if (keyed) focusDestination(next ?? this.#forward, "move");
      else if (inside) focused().blur();
      if (this.getBoundingClientRect().top < 0)
        scrollIntoView(this, { block: "start", behavior: scrollBehavior() });
    }

    // The next waiting card after `card`, or, with no reading, the next card; null at
    // the end of the pass.
    #after(card, readings) {
      const rest = this.#cards.slice(this.#cards.indexOf(card) + 1);
      if (!readings) return rest[0] ?? null;
      return rest.find((each) => waitsOn(readings.get(each))) ?? null;
    }

    #onward(side) {
      const card = this.#open.value;
      if (card) this.#go(this.#after(card, this.#readings()), side);
    }

    #back() {
      const card = this.#open.value;
      const index = card ? this.#cards.indexOf(card) : this.#cards.length;
      if (index <= 0) return;
      const pressed = focused();
      this.#show(this.#cards[index - 1]);
      // Back on the second card disables itself; the user stays in the bar.
      if (index === 1 && pressed?.matches(".lf-deck-back"))
        focusDestination(this.#forward, "return");
    }

    #forwardPress(readings) {
      const card = this.#open.value;
      if (card)
        return this.#onward(readings && waitsOn(readings.get(card)) ? "left" : "right");
      const waiting =
        readings && this.#cards.find((each) => waitsOn(readings.get(each)));
      this.#show(waiting ?? this.#cards[0]);
    }

    // A touch drag on the open card, begun anywhere but on a control inside it.
    #press(event) {
      const card = this.#open.value;
      if (!card?.contains(event.target)) return;
      this.#pressed = card;
      if (event.pointerType !== "touch") return;
      if (
        event.target.closest(
          "button, a, input, textarea, select, [contenteditable], [role=button], [role=radio], [role=checkbox], [data-lf-offer]",
        )
      )
        return;
      this.#drag = {
        id: event.pointerId,
        x: event.clientX,
        y: event.clientY,
        dx: 0,
        moving: false,
      };
    }

    #follow(event) {
      const drag = this.#drag;
      const card = this.#open.value;
      if (drag?.id !== event.pointerId || !card) return;
      drag.dx = event.clientX - drag.x;
      if (!drag.moving) {
        // A vertical move is the page scrolling (`touch-action: pan-y`).
        if (Math.abs(event.clientY - drag.y) > Math.abs(drag.dx))
          return (this.#drag = null);
        if (Math.abs(drag.dx) < 8) return;
        drag.moving = true;
        card.setPointerCapture(event.pointerId);
        dragging(this, true);
      }
      card.style.translate = `${drag.dx}px`;
      card.style.rotate = `${drag.dx / 30}deg`;
    }

    #release(event) {
      const drag = this.#drag;
      if (drag?.id !== event.pointerId) return;
      if (!drag.moving) return (this.#drag = null);
      const readings = this.#readings();
      const card = this.#open.value;
      this.#settle();
      if (drag.dx <= -SWIPE) this.#onward("left");
      else if (drag.dx >= SWIPE && !(readings && waitsOn(readings.get(card))))
        this.#onward("right");
    }

    #settle() {
      const card = this.#open.value;
      if (this.#drag?.moving) dragging(this, false);
      this.#drag = null;
      card?.style.removeProperty("translate");
      card?.style.removeProperty("rotate");
    }

    render() {
      if (!this.#cards.length) return nothing;
      const items = readObligations();
      const readings = this.#readings();
      const card = this.#open.value;
      const index = card ? this.#cards.indexOf(card) : this.#cards.length;
      const waits = (each) => Boolean(readings) && waitsOn(readings.get(each));
      const left = readings ? this.#cards.filter(waits).length : 0;
      const count = readings
        ? tallyWords(tally(obligationsIn(this, items.all)), agentName())
        : "";
      // A card's mark: open, waiting on the user, open with the agent, or answered.
      const mark = (each) => {
        if (each === card) return "open";
        const held = readings?.get(each);
        if (!held?.length) return "";
        if (waits(each)) return "waiting";
        return held.some((item) => item.status === "open") ? "agent" : "done";
      };
      const forward = card
        ? waits(card)
          ? "Later"
          : "Next"
        : left
          ? `Go through ${left === 1 ? "it" : `the ${left}`}`
          : "Review";
      return html`
        <button
          ${offered("lf-btn lf-quiet-action lf-deck-back")}
          type="button"
          ?disabled=${index === 0}
          @mousedown=${(event) => event.preventDefault()}
          @click=${() => this.#back()}
        >
          Back
        </button>
        <span class="lf-deck-count" role="status">${count}</span>
        <span class="lf-deck-pips" aria-hidden="true"
          >${this.#cards.map(
            (each) => html`<span class="lf-deck-pip" data-state=${mark(each)}></span>`,
          )}</span
        >
        <button
          ${offered(`lf-btn lf-deck-forward${card && !waits(card) ? " primary" : ""}`)}
          type="button"
          title=${card && waits(card) ? "Leave this card for later" : ""}
          @mousedown=${(event) => card && event.preventDefault()}
          @click=${() => this.#forwardPress(this.#readings())}
        >
          <span data-room=${"Later\nNext\nReview\nGo through the 00"}
            ><span>${forward}</span></span
          >
        </button>
      `;
    }

    updated() {
      this.#forward = this.#bar?.querySelector(".lf-deck-forward") ?? null;
      const readings = this.#readings();
      if (!readings || this.#drag) return;
      const card = this.#open.value;
      const waiting = this.#cards.filter((each) => waitsOn(readings.get(each)));
      // The edges under the open card are the cards still waiting after it.
      const behind = card
        ? waiting.filter(
            (each) => this.#cards.indexOf(each) > this.#cards.indexOf(card),
          )
        : [];
      keeps(this, "data-lf-deck-behind", String(Math.min(2, behind.length)));
      if (!card) return;
      const waits = waiting.includes(card);
      // The reading that ends the open card's wait sends it on when the user answered
      // it from the card: every obligation it holds is closed, at least one by an
      // answer, and the user is on the card, on a control standing for it such as a
      // suggestion's margin entry (`placeOf`), or pressed in it and is on nothing else.
      // A comment leaves an obligation open with the agent, and the agent ending one
      // closes it without an answer, so neither moves the card.
      const held = readings.get(card);
      const answered =
        held.some((item) => item.status === "answered") &&
        !held.some((item) => item.status === "open");
      const here = focused();
      const place = here && placeOf(here);
      const onCard =
        Boolean(place && under(place, card)) ||
        (this.#pressed === card && [null, document.body].includes(here));
      if (this.#waited && !waits && answered && onCard)
        this.#go(this.#after(card, readings), "right");
      else this.#waited = waits;
    }
  },
);
