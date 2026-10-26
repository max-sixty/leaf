/* lf-deck: a pile of cards worked through one at a time, as Slack's Catch up works
 * through unread conversations. Each authored child is a card, an `lf-ask` or a
 * decision widget the user answers there with its own controls. A card waits while it
 * holds an obligation open on the user (`obligationsIn`, read from the server's
 * inventory, the rule `lf-tally` counts by). When the server's reading says the open
 * card no longer waits, after the user answered it on the card or on a control standing
 * for it, such as a suggestion's margin entry, the card flies right and the next waiting
 * card after it comes up; a draft editor open on the card saves as the press leaves it
 * (`lf-draft`), so moving on hides no unsaved words. A wait that ends anywhere else, as
 * when the user comments on the card and leaves it with the agent, the agent ends the
 * question, or the user answers it in another window, leaves the card where it is with
 * Next, since news never moves what the user is reading. Later sends a card left and
 * leaves its obligation open, which is Leaf's keep unread: nothing is recorded, the
 * pass ends with the cards kept for later still waiting, and Go through starts again
 * from the first of them. Back returns to the card before, where the widget's own
 * controls change an answer. Where nothing waits, as in Review, and until the page's
 * first reading is in, as offline, Later and Next step to the next card in order.
 *
 * Which card is open is view state for this user, as a tab set's open panel is
 * (`x-views`): the runtime names the opening card (`openingView`), the module records
 * each card it shows (`keepView`), so a reload comes back to it, and no event carries
 * it. Where neither the address nor the tab names a card, the deck opens on the first
 * that waits once the first reading is in. Inactive cards are `hidden="until-found"`, so find-in-page, a fragment and the On
 * walk (`m`, `obligationActions.next`) open the card holding what they reach
 * (`beforematch`, `lf-reveal`); `m` is therefore the keyboard's Later, and a card the
 * walk leaves behind stays waiting for the end of the pass. Leaf's Undo travels to the
 * answer it takes back before taking it, which opens its card the same way, so the deck
 * has no Undo of its own.
 *
 * The bar above the cards holds Back, the tally's count of the deck's obligations
 * (`tallyWords`) with a mark per card, Reply on a card asked in words, and one forward
 * control: Later on a waiting card, Next on any other, then Go through the cards left,
 * or Review, once the pass is over. Then a quiet frame stands where the cards stood,
 * saying how many still wait, with the same step back in as words, since a symbol
 * alone at the end of the pass went unnoticed. They are symbols of one size and one style, named by
 * their titles as a draft's actions are, that never take focus from a pointer, so none
 * wears a frame another lacks. Each is a command row whose control it is, so the arrow
 * keys toward and away from the text's start are Back and forward wherever the user is
 * in the deck, and Leaf shows Back unavailable on the first card while focus stays on it.
 * Reply puts the user on the question and opens its comment box, as `c` there would
 * (`executeCommand`): a question asked in words is answered by a comment, and nothing on
 * the card says so otherwise. The bar stands above the card, so cards of different
 * heights never move a control under the pointer; for the same reason a card that comes
 * up takes no press until it has settled. A touch
 * drag across the card sends it either way, flying on from where the finger let go:
 * left is Later, right is Next once the card no longer waits, and a short or early drag
 * settles back. A mouse or pen drag stays
 * text selection, which comments start from. Unupgraded, and on paper, the cards stand
 * one after another.
 *
 * Rejected: a Catch up button at the Leaf panel's foot opening a deck over the whole
 * window, built from the On me list. Catch up is a widget the agent puts on the page
 * around the questions it is waiting on, chosen by the user on 2026-10-24. */
import {
  agentName,
  answeredInWords,
  commands,
  elementById,
  executeCommand,
  iconElement,
  rowArrows,
  dragging,
  focusDestination,
  focused,
  currentLocationIn,
  keepView,
  keeps,
  keepsHidden,
  keepsText,
  layoutChanged,
  LeafElement,
  motion,
  obligationActions,
  obligationsIn,
  offer,
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
    #status = null;
    #back = null;
    #reply = null;
    #forward = null;
    #end = null;
    #again = null;
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
    // Whether the deck opened on its first card only because this tab kept no card
    // and the address named none, so the first reading may open the first that waits.
    #defaulted = false;

    createRenderRoot() {
      return this.#status ?? this;
    }

    setup() {
      this.#cards = [...this.children].filter(isCard);
      if (!this.#cards.length) return;
      this.#bar = offer("div", "lf-deck-bar");
      this.#status = document.createElement("span");
      this.#status.className = "lf-deck-status";
      const control = (name, icon) => {
        const button = offer(
          "button",
          `lf-btn lf-quiet-action lf-deck-action lf-deck-${name}`,
        );
        button.append(iconElement(icon, "lf-action-icon"));
        button.dataset.icon = icon;
        // A press never takes focus, so no control keeps a frame the others lack.
        button.addEventListener("mousedown", (event) => event.preventDefault());
        return button;
      };
      this.#back = control("back", "previous");
      this.#reply = control("reply", "comment");
      this.#forward = control("forward", "next");
      this.#bar.append(this.#back, this.#status, this.#reply, this.#forward);
      // Where the cards stood once the pass is over: what is left, and a way back in.
      this.#end = offer("div", "lf-deck-end");
      this.#end.hidden = true;
      this.#end.append(document.createElement("p"));
      this.#again = offer("button", "lf-btn lf-deck-again");
      this.#again.addEventListener("click", () => this.#forwardPress(this.#readings()));
      this.#end.append(this.#again);
      const [back, ahead] = rowArrows(this);
      commands(this, "In a deck", [
        {
          id: "deck.back",
          keys: [back],
          title: "Back",
          control: this.#back,
          bindingBadge: null,
          touch: false,
          when: () => this.#index() > 0,
          run: () => this.#stepBack(),
        },
        {
          id: "deck.reply",
          keys: [],
          title: "Reply",
          control: this.#reply,
          touch: false,
          when: () => Boolean(this.#asking()),
          run: () => this.#replyHere(),
        },
        {
          id: "deck.forward",
          keys: [ahead],
          title: () => this.#forwardWord(),
          control: this.#forward,
          bindingBadge: null,
          touch: false,
          run: () => this.#forwardPress(this.#readings()),
        },
      ]);
      for (const card of this.#cards) {
        card.addEventListener("beforematch", () => this.#show(card));
        card.addEventListener("lf-reveal", (event) => {
          if (this.#open.value !== card) event.detail.replacedView?.();
          event.detail.present?.(this.#show(card));
        });
      }
      this.prepend(this.#bar);
      this.append(this.#end);
      this.classList.add("lf-rendered");
      const opening = openingView(this, this.#cards, null);
      this.#show(opening ?? this.#cards[0]);
      this.#defaulted = !opening;
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
      this.#defaulted = false;
      this.#waited = null;
      this.#pressed = null;
      if (card) keepView(this, card);
      return layoutChanged(this);
    }

    // Leave the open card toward `side` and bring up `next` (null ends the pass). The
    // leaving card keeps its box over the deck while it flies, so the next card is
    // already in place beneath it.
    #go(next, side, { from = "none", answered = false } = {}) {
      this.#leaving?.finish();
      const card = this.#open.value;
      if (!card || next === card) return this.#show(next);
      // Whether the user is on the leaving card, and whether they came by keyboard,
      // as the browser's focus-visible reading says.
      const carry = this.#carry(card);
      const top = card.offsetTop;
      const flight = motion(
        card,
        [
          { transform: from, opacity: 1 },
          {
            transform: `translateX(${side === "left" ? -110 : 110}%) rotate(${side === "left" ? -6 : 6}deg)`,
            opacity: 0,
          },
        ],
        LEAVE_MS,
      );
      if (flight) {
        card.style.setProperty("--lf-deck-leave-top", `${top}px`);
        keeps(card, "data-lf-deck-leaving", side);
        keeps(this, "data-lf-deck-flying", "");
        this.#leaving = flight;
        const land = () => {
          if (this.#leaving === flight) {
            this.#leaving = null;
            keeps(this, "data-lf-deck-flying", null);
          }
          keeps(card, "data-lf-deck-leaving", null);
          card.style.removeProperty("--lf-deck-leave-top");
          if (this.#open.value !== card) keeps(card, "hidden", "until-found");
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
      this.#defaulted = false;
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
        keeps(next, "data-lf-deck-settling", "");
        setTimeout(() => keeps(next, "data-lf-deck-settling", null), SETTLE_MS);
      }
      layoutChanged(this);
      carry(next, answered ? SETTLE_MS : 0);
      if (this.getBoundingClientRect().top < 0)
        scrollIntoView(this, { block: "start", behavior: scrollBehavior() });
    }

    // The next waiting card after `card`, or the next card where there is no reading or
    // the user steps through a deck where nothing waits, as Review does; null at the
    // end of the pass.
    #after(card, readings, stepping) {
      const rest = this.#cards.slice(this.#cards.indexOf(card) + 1);
      const waiting = (each) => waitsOn(readings.get(each));
      if (!readings || (stepping && !this.#cards.some(waiting))) return rest[0] ?? null;
      return rest.find(waiting) ?? null;
    }

    // The user sends the open card toward `side`, from where a drag left it.
    #onward(side, from) {
      const card = this.#open.value;
      if (card) this.#go(this.#after(card, this.#readings(), true), side, { from });
    }

    #index() {
      const card = this.#open.value;
      return card ? this.#cards.indexOf(card) : this.#cards.length;
    }

    // What becomes of the user on a card the deck puts away, or on a control standing
    // for it such as a suggestion's margin entry or its thread's reply box: one who was
    // there by keyboard arrives at the card that comes up as `m` would, on what waits
    // there, so its own keys answer it, or at the forward control once the pass is
    // over; one who pressed lets go of the hidden card, and Tab goes on from where it
    // was. After an answer the arrival waits until the card has settled, so a key
    // pressed twice answers one card. Read before the card goes.
    #carry(card) {
      const here = focused();
      const place = here && placeOf(here);
      const inside = Boolean(
        card && (currentLocationIn(card) || (place && under(place, card))),
      );
      const keyed = inside && here.matches(":focus-visible");
      return (next, wait = 0) => {
        // A caret or selection left in the hidden card would start the next walk there.
        const selection = getSelection();
        if (selection.rangeCount && card && under(selection.anchorNode, card))
          selection.removeAllRanges();
        if (!inside) return;
        if (!keyed || wait) here.blur();
        if (!keyed) return;
        if (!wait) return this.#arrive(next);
        setTimeout(() => {
          if ([null, document.body].includes(focused())) this.#arrive(next);
        }, wait);
      };
    }

    #arrive(card) {
      if (!card) {
        keepsHidden(this.#end, false);
        return void focusDestination(this.#again, "move");
      }
      const waiting = this.#readings()
        ?.get(card)
        .find(
          (item) =>
            item.status === "open" && item.next_actor === "user" && !answeredInWords(item),
        );
      if (waiting) obligationActions.open(waiting.id);
      else focusDestination(card, "move");
    }

    #stepBack() {
      const index = this.#index();
      if (index <= 0) return;
      const carry = this.#carry(this.#open.value);
      this.#show(this.#cards[index - 1]);
      carry(this.#open.value);
    }

    // The open card's question asked in words that waits on the user, if it holds one.
    #asking() {
      const card = this.#open.value;
      const held = card && this.#readings()?.get(card);
      return (
        held?.find(
          (item) =>
            item.status === "open" &&
            item.next_actor === "user" &&
            answeredInWords(item),
        ) ?? null
      );
    }

    // Put the user on the question and open its comment box, as `c` there would.
    #replyHere() {
      const asking = this.#asking();
      const target = asking && elementById(asking.prompt.target);
      if (!target) return;
      focusDestination(target, "press");
      executeCommand("comment.create");
    }

    // The forward control's word, its accessible name and tooltip, and its symbol: on a
    // card, Later or Next; once the pass is over, back to its start.
    #forwardWord() {
      const readings = this.#readings();
      const card = this.#open.value;
      const waits = (each) => Boolean(readings) && waitsOn(readings.get(each));
      if (card) return waits(card) ? "Later" : "Next";
      const left = this.#cards.filter(waits).length;
      return left ? `Go through the ${left} left` : "Review from the start";
    }

    #forwardPress(readings) {
      const card = this.#open.value;
      if (card)
        return this.#onward(readings && waitsOn(readings.get(card)) ? "left" : "right");
      const waiting =
        readings && this.#cards.find((each) => waitsOn(readings.get(each)));
      const keyed = this.#end.contains(focused()) && focused().matches(":focus-visible");
      this.#show(waiting ?? this.#cards[0]);
      if (keyed) this.#arrive(this.#open.value);
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
      const from = `translateX(${drag.dx}px) rotate(${drag.dx / 30}deg)`;
      this.#settle();
      if (drag.dx <= -SWIPE) this.#onward("left", from);
      else if (drag.dx >= SWIPE && !(readings && waitsOn(readings.get(card))))
        this.#onward("right", from);
    }

    #settle() {
      const card = this.#open.value;
      if (this.#drag?.moving) dragging(this, false);
      this.#drag = null;
      if (!card?.style.translate) return;
      card.style.removeProperty("translate");
      card.style.removeProperty("rotate");
    }

    render() {
      if (!this.#cards.length) return nothing;
      const items = readObligations();
      const readings = this.#readings();
      const card = this.#open.value;
      const waits = (each) => Boolean(readings) && waitsOn(readings.get(each));
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
      return html`
        <span class="lf-deck-pips" aria-hidden="true"
          >${this.#cards.map(
            (each) => html`<span class="lf-deck-pip" data-state=${mark(each)}></span>`,
          )}</span
        >
        <span class="lf-deck-count" role="status">${count}</span>
      `;
    }

    updated() {
      if (!this.#cards.length) return;
      const word = this.#forwardWord();
      keeps(this.#forward, "aria-label", word);
      keeps(this.#forward, "title", word);
      const icon = this.#open.value ? "next" : "start";
      if (this.#forward.dataset.icon !== icon) {
        this.#forward.dataset.icon = icon;
        this.#forward
          .querySelector("svg")
          ?.replaceWith(iconElement(icon, "lf-action-icon"));
      }
      for (const [button, word] of [
        [this.#back, "Back"],
        [this.#reply, "Reply"],
      ]) {
        keeps(button, "aria-label", word);
        keeps(button, "title", word);
      }
      keeps(this.#reply, "hidden", this.#asking() ? null : "");
      // Once the pass is over the end frame's button is the step back in.
      keeps(this.#forward, "hidden", this.#open.value ? null : "");
      const readings = this.#readings();
      keepsHidden(this.#end, Boolean(this.#open.value));
      if (!this.#open.value) {
        const left = readings
          ? this.#cards.filter((each) => waitsOn(readings.get(each))).length
          : 0;
        keepsText(
          this.#end.firstChild,
          left
            ? `You've been through every card. ${left === 1 ? "One still waits" : `${left} still wait`} on you.`
            : "You've been through every card, and none waits on you.",
        );
        keepsText(this.#again, word);
      }
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
      if (this.#defaulted) {
        this.#defaulted = false;
        if (waiting.length && !waiting.includes(card)) return void this.#show(waiting[0]);
      }
      const waits = waiting.includes(card);
      // The reading that ends the open card's wait sends it on when the user answered
      // it from the card: every obligation it holds is closed, at least one by an
      // answer, and the user is in this window and on the card, on a control standing
      // for it such as a suggestion's margin entry (`placeOf`), or pressed in it and is
      // on nothing else. A comment leaves an obligation open with the agent, the agent
      // ending one closes it without an answer, and an answer from another window
      // arrives here while this one lacks focus, so none of them moves the card.
      const held = readings.get(card);
      const closed =
        held.some((item) => item.status === "answered") &&
        !held.some((item) => item.status === "open");
      const here = focused();
      const place = here && placeOf(here);
      const onCard =
        document.hasFocus() &&
        (Boolean(place && under(place, card)) ||
          (this.#pressed === card && [null, document.body].includes(here)));
      if (this.#waited && !waits && closed && onCard) {
        this.#go(this.#after(card, readings), "right", { answered: true });
      } else this.#waited = waits;
    }
  },
);
