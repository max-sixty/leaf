/* lf-deck: a pile of cards worked through one at a time, as Slack's Catch up works
 * through unread conversations. Each authored child is a card, the named group of a
 * question or a decision widget the user answers there with its own controls. A card waits while it
 * holds an obligation open on the user (`readObligations(card)`, read from the page's
 * inventory, the rule `lf-tally` counts by). When the page's obligations say the open
 * card's questions are answered, the card flies right and the next waiting card after
 * it comes up; a draft editor open on the card saves as the press leaves it
 * (`lf-draft`), so moving on hides no unsaved words. Whether a card still waits is what
 * the obligations say: a press here that answers the card's widget says so in the
 * press's own task (`awaits`), so the card moves on at once, and an answer given
 * elsewhere arrives with the server's reading, however late, wherever the user is by
 * then. It
 * takes the page or focus with it only while the user's latest gesture toward the card
 * in this window still stands (`retainUserIntent`), so a user who has gone on to read
 * elsewhere stays there. An answer given in another window moves the card on here too.
 * A wait that ends without an answer, as when the user comments on the card and leaves
 * it with the agent or the agent ends the question, leaves the card where it is with
 * Next, since news never moves what the user is reading. Later sends a card left and
 * leaves its obligation open, which is Leaf's keep unread: nothing is recorded, the
 * pass ends with the cards kept for later still waiting, and Go through starts again
 * from the first of them. Back returns to the card before, where the widget's own
 * controls change an answer. Where nothing waits, as in Review, and until the page's
 * first reading is in, as offline, Later and Next step to the next card in order.
 *
 * Which card is open is view state for this user, as a tab set's open panel is
 * (`views`): the runtime names the opening card (`openingView`), the module
 * records each card it shows (`keepView`), so a reload comes back to it, and no event
 * carries it. Where neither the address nor the tab names a card, the deck opens on the
 * first that waits once the first reading is in. Inactive cards are
 * `hidden="until-found"`, so find-in-page, a fragment and the On walk (`m`,
 * `obligationActions.next`) open the card holding what they reach (`beforematch`); `m`
 * is therefore the keyboard's Later, and a card the walk leaves behind stays waiting
 * for the end of the pass. Leaf's Undo opens the card holding the answer it takes back
 * the same way, where the card stood, so the deck has no Undo of its own.
 *
 * The bar above the cards holds Back, the tally's count of the deck's obligations
 * (`tallyWords`) with a mark per card, and one forward control: Later on a waiting card, Next on any other, then Go through the cards left,
 * or Review, once the pass is over. Then a quiet frame stands where the cards stood,
 * saying how many still wait, with the same step back in as words, since a symbol
 * alone at the end of the pass went unnoticed. Under that line it lists each card that
 * asks something: its question, linked to the card, beside what became of it, the
 * answer in the runtime's words (`answerWords`) or who it still waits on. The cards are
 * put away by then, and without the list the record of the pass hid behind Back, one
 * card at a time. A row links to where its question is answered, so it opens the card
 * holding it as any fragment link does (`beforematch`), by pointer, finger or Enter,
 * whether or not the card has an id of its own. `render()` draws the bar and the end
 * frame, each a generated container, keeping Back, forward and the step back in as
 * retained nodes and each row by its card (`repeat`), so a reading that arrives while
 * a row has focus leaves it there. The bar's controls are symbols of one size and one style, named by
 * their titles as a draft's actions are. Each is a command row whose control it is, so the arrow
 * keys toward and away from the text's start are Back and forward wherever the user is
 * in the deck, and Leaf shows Back unavailable on the first card while focus stays on it.
 * Neither wears a key chip: its symbol already points the way its arrow key does, a
 * chip beside it read as a second pair of arrows, and its preview names the key.
 * The bar stands above the card, so cards of different
 * heights never move a control under the pointer; for the same reason a card that comes
 * up after an answer takes no press until it has settled. Cards move as a stack: the
 * open one flies off the side it was sent, the one behind rises into place, and Back
 * brings a card in over the open one from the left (`#go`). The deck's height glides to
 * each card's. At a page's end, the room a document keeps below its last line
 * (`layouts.css`) takes up what a shorter card leaves, so the bar stays where it stood.
 * A card a press brings up that would end under the panel then
 * scrolls up until its options clear it, the bar still above it, since a deck below the
 * page's opening brought a tall card back with its options out of reach. A touch drag
 * across the card sends it either way, flying on from
 * where the finger let go: left is Later, right is Next once the card no longer waits,
 * and a short or early drag settles back. A mouse or pen drag stays text selection,
 * which comments start from. Unupgraded, and on paper, the cards stand one after
 * another.
 *
 * Rejected: a Catch up button at the Leaf panel's foot opening a deck over the whole
 * window, built from the On Me list. Catch up is a widget the agent puts on the page
 * around the questions it is waiting on, chosen by the user. Rejected by the user too:
 * telling an answer sent from this window from one sent from another (`sentHere`), so
 * that another window's answer left the card in place. It cost a name in the package
 * interface for a rare path, on which the card that moves is one the user answered.
 * Rejected by the user too: a deck holding the tallest height it had stood at, so a
 * shorter card at the page's end didn't let the browser pull the page down. It left
 * room inside a short card's frame, or below it, and ran in the deck's own code for a
 * fault every block at the page's end shares. */
import { html, nothing, render, repeat } from "/vendor/lit.js";
import {
  agentName,
  answerWords,
  focusDestination,
  keepView,
  motion,
  obligationActions,
  onUserInput,
  placeOf,
  openingView,
  viewMembers,
  nameOf,
  readObligations,
  readQueues,
  retainUserIntent,
  scrollIntoView,
  whileConnected,
} from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { nameAction, offer, offerAction } from "/runtime/lib/controls.js";
import { rowArrows } from "/runtime/lib/keys.js";
import { under } from "/runtime/lib/shadow-tree.js";
import { keeps, keepsText } from "/runtime/lib/keeps.js";
import { tally, tallyWords } from "/runtime/lib/obligation-tally.js";

// How far a touch drag travels before a release sends the card; how long a card takes
// to leave, and the next to come up; and how long a card that came up takes no press.
// A leaving card accelerates away and an arriving one decelerates into place, on
// Material 3's emphasized curves, so the motion starts at once and lands softly.
const SWIPE = 80;
const LEAVE_MS = 200;
const ARRIVE_MS = 260;
const FADE_MS = 140;
const SETTLE_MS = 250;
// The inputs that aim a gesture at the deck, as against a wheel that reads past it.
const GESTURES = new Set(["pointerdown", "keydown"]);
const LEAVE = "cubic-bezier(0.3, 0, 0.8, 0.15)";
const ARRIVE = "cubic-bezier(0.05, 0.7, 0.1, 1)";

// Whether a card's obligations, by the reading, wait on the user, as the tally counts
// them.
/** @param {DeckHeld} held */
const waitsOn = (held) => tally(held).onUser > 0;

// The element focus is on, followed down through each open shadow tree, so that a
// control inside a widget's tree is the one the deck blurs and asks about.
const focusedElement = () => {
  let at = document.activeElement;
  while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
  return at;
};

/** @typedef {ReturnType<typeof readObligations>["all"]} DeckHeld */
/** @typedef {(card: HTMLElement) => DeckHeld} DeckReadings */

customElements.define(
  "lf-deck",
  class extends LeafElement {
    static lfPatch = "members";
    #bar = offer("div", "lf-deck-bar");
    #back = offerAction("symbol", "lf-deck-back", "Back", { action: "previous" });
    #forward = offerAction("symbol", "lf-deck-forward", undefined, { action: "next" });
    #end = offer("div", "lf-deck-end");
    #again = offerAction("word", "lf-deck-again");
    /** @type {HTMLElement[]} */
    #cards = [];
    // The open card, or null once the pass is over.
    /** @type {HTMLElement | null} */
    #open = null;
    // Whether the open card has waited on the user at a reading since it opened, so an
    // answer on a card Back returned to, answered already, leaves it open.
    #waited = false;
    // The open card's answers as the deck last read them, and the intent of the user's
    // latest gesture toward the card in this window: a press or key in the deck, or,
    // for one made from a control standing for the card such as a margin entry, the
    // change of answer it made, which shows at once, while the card still waits. Null
    // where there was none, as when another window answered.
    #answers = "";
    /** @type {(() => boolean) | null} */
    #moves = null;
    // Ends the motion in flight at once, landing every element where it belongs.
    /** @type {((upcoming?: HTMLElement | null) => void) | null} */
    #landing = null;
    /** @type {{id: number, x: number, y: number, dx: number, moving: boolean, held?: PromiseWithResolvers<void>} | null} */
    #drag = null;
    // Whether the deck opened on its first card only because this tab kept no card
    // and the address named none, so the first reading may open the first that waits.
    #defaulted = false;

    // The bar is the render root, holding Back and the forward control as retained nodes
    // around the drawn status; `render()` draws the end frame too.
    createRenderRoot() {
      return this.#cards.length ? this.#bar : this;
    }

    setup() {
      this.#cards = viewMembers(this).map((card) => {
        if (!(card instanceof HTMLElement))
          throw new Error("A deck card must be an HTML element");
        return card;
      });
      if (!this.#cards.length) return;
      // Where the cards stood once the pass is over: what is left, a way back in, and
      // the record of the pass (`#drawEnd`). Drawn now so the step back in is in the
      // page for a keyboard user who reaches the end before the next render.
      this.#end.hidden = true;
      this.#drawEnd(null);
      this.#again.addEventListener("click", () => this.#forwardPress(this.#readings()));
      const [back, ahead] = rowArrows(this);
      /** @type {HTMLElement["lfCommands"]} */
      const commands = {
        title: "In a deck",
        rows: [
          {
            id: "deck.back",
            keys: [back],
            title: "Back",
            control: this.#back,
            touch: false,
            when: () => this.#index() > 0,
            run: () => this.#stepBack(),
          },
          {
            id: "deck.forward",
            keys: [ahead],
            title: () => this.#forwardWord(),
            control: this.#forward,
            touch: false,
            run: () => this.#forwardPress(this.#readings()),
          },
        ],
      };
      this.lfCommands = commands;
      this.dispatchEvent(
        new CustomEvent("lf-commands", { bubbles: true, composed: true }),
      );
      for (const card of this.#cards) {
        card.addEventListener("beforematch", () => this.#show(card));
      }
      this.prepend(this.#bar);
      this.append(this.#end);
      this.classList.add("lf-rendered");
      const selected = openingView(this, null);
      const opening = this.#cards.find((card) => card === selected);
      this.#show(opening ?? this.#cards[0]);
      this.#defaulted = !opening;
      if (this.matches("[data-lf-exhibit] *")) return;
      whileConnected(this, (signal) => {
        const options = { signal };
        // A press or key in the deck is the user's latest gesture toward it, read from
        // the document's one reading of the user's inputs, which binds no key.
        const forget = onUserInput((event) => {
          if (GESTURES.has(event.type) && event.composedPath().includes(this))
            this.#moves = retainUserIntent();
        });
        signal.addEventListener("abort", forget);
        this.addEventListener("pointerdown", (event) => this.#press(event), options);
        this.addEventListener("pointermove", (event) => this.#follow(event), options);
        this.addEventListener("pointerup", (event) => this.#release(event), options);
        this.addEventListener("pointercancel", () => this.#settle(), options);
        return () => this.#settle();
      });
    }

    // Each card's obligations, or null until the page's first reading is in: what the
    // card holds by the one rule every count of a region reads.
    /** @returns {DeckReadings | null} */
    #readings() {
      if (readObligations().phase !== "ready") return null;
      return (/** @type {HTMLElement} */ card) => readObligations(card).all;
    }

    // Show one card, or none once the pass is over, without motion.
    /** @param {HTMLElement | null} [card] */
    #show(card = null) {
      // Arriving at the open card, as `m` does at the card a motion is bringing up,
      // leaves that motion to finish.
      if (card === this.#open) return;
      this.#landing?.();
      keepView(this, card);
      for (const each of this.#cards) {
        keeps(each, "data-lf-deck-open", each === card ? "" : null);
      }
      this.#end.toggleAttribute("hidden", Boolean(card));
      this.#open = card;
      this.requestUpdate();
      this.#defaulted = false;
      this.#waited = false;
      this.#answers = "";
      this.#moves = null;
      this.dispatchEvent(
        new CustomEvent("lf-layout", { bubbles: true, composed: true }),
      );
    }

    // Move from the open card to `next`, or to the end of the pass when it is null.
    // Toward the left (Later) or right (Next, or an answer) the open card flies off that
    // side, from where a drag left it, and `next` rises from the edge of the stack
    // beneath, where it stood as the card behind. Back brings `next` in over the open
    // card from the left, the side Later sent it to. The deck's height glides to the
    // card's, so the page below slides rather than jumps. A card in flight keeps its box
    // over the deck while the new one takes the flow.
    /** @param {HTMLElement | null} next @param {string} side @param {{from?: string, answered?: boolean, moves?: () => boolean}} [options] */
    #go(
      next = null,
      side,
      { from = "none", answered = false, moves = retainUserIntent() } = {},
    ) {
      this.#landing?.(next);
      const card = this.#open;
      if (next === card) return this.#show(next);
      // Once the pass is over the forward control goes too, the end frame's step back in
      // standing for it.
      const carry = this.#carry([card ?? this.#end, ...(next ? [] : [this.#forward])]);
      const before = parseFloat(getComputedStyle(this).height);
      const arriving = next ?? this.#end;
      const back = side === "back";
      const toward = side === "left" ? -1 : 1;
      // The card behind stands a stack edge lower and that much narrower on each side.
      const edge = 1 - 12 / Math.max(this.offsetWidth, 12);
      // A card crossing the deck's side fades on a shorter clock than it travels, so
      // it is faint by the time it meets the clip there.
      const leaves = card !== null && !back;
      const leave =
        leaves &&
        motion(
          card,
          [
            { transform: from, easing: LEAVE },
            { transform: `translateX(${toward * 40}%) rotate(${toward * 3}deg)` },
          ],
          LEAVE_MS,
        );
      const enter = motion(
        arriving,
        [
          {
            transform: back
              ? "translateX(-40%) rotate(-3deg)"
              : `translateY(12px) scale(${edge})`,
            easing: ARRIVE,
          },
          { transform: "none" },
        ],
        ARRIVE_MS,
      );
      const running = [
        leave,
        leaves &&
          motion(
            card,
            [
              { opacity: 1 },
              { opacity: 0, offset: FADE_MS / LEAVE_MS },
              { opacity: 0 },
            ],
            LEAVE_MS,
          ),
        enter,
        back &&
          motion(
            arriving,
            [
              { opacity: 0 },
              { opacity: 1, offset: FADE_MS / ARRIVE_MS },
              { opacity: 1 },
            ],
            ARRIVE_MS,
          ),
        back &&
          card &&
          motion(
            card,
            [
              { opacity: 1 },
              { opacity: 0, offset: FADE_MS / ARRIVE_MS },
              { opacity: 0 },
            ],
            ARRIVE_MS,
          ),
      ].filter(
        /** @returns {animation is Animation} */ (animation) => Boolean(animation),
      );
      // Where motion plays, the card that goes keeps its box over the deck while it
      // moves; where it doesn't, as under reduced motion, the cards change places at once.
      // It takes no focus while it moves, since it stands before the card that came up,
      // so Shift+Tab from that card would otherwise land in the one flying off.
      const moving = card !== null && running.length > 0;
      if (moving) {
        card.style.setProperty("--lf-deck-leave-top", `${card.offsetTop}px`);
        keeps(card, "data-lf-deck-leaving", side);
        keeps(card, "inert", "");
      }
      keepView(this, next, moving ? card : null);
      for (const each of this.#cards) {
        keeps(each, "data-lf-deck-open", each === next ? "" : null);
      }
      this.#end.toggleAttribute("hidden", Boolean(next));
      this.#open = next;
      this.requestUpdate();
      // The end frame holds its words and its record of the pass before the deck
      // measures the height it grows to.
      if (!next) this.#drawEnd(this.#readings());
      this.#defaulted = false;
      this.#waited = false;
      this.#answers = "";
      this.#moves = null;
      // The deck glides to the height of the card that came up.
      if (running.length) {
        const after = parseFloat(getComputedStyle(this).height);
        if (Math.abs(after - before) > 1) {
          const resize = motion(
            this,
            [{ height: `${before}px`, easing: ARRIVE }, { height: `${after}px` }],
            ARRIVE_MS,
          );
          if (resize) running.push(resize);
        }
      }
      // The card that went is put away as its own motion ends, before the motion's last
      // frame lets go of it: the card it flew from, or the one Back covered.
      // A motion the next one cuts short (`upcoming` names the card that one opens) leaves
      // that card shown and the deck in flight for it, rather than undo them only for the
      // next motion to write them back.
      let departing = moving ? card : null;
      const putAway = (upcoming = this.#open) => {
        const leaving = departing;
        if (!leaving) return;
        departing = null;
        keeps(leaving, "data-lf-deck-leaving", null);
        keeps(leaving, "inert", null);
        leaving.style.removeProperty("--lf-deck-leave-top");
        keepView(this, this.#open, leaving === upcoming ? leaving : null);
      };
      const land = (
        /** @type {HTMLElement | null | undefined} */ upcoming = undefined,
      ) => {
        if (this.#landing !== land) return;
        this.#landing = null;
        // Only a motion still running is cut short: finishing one the runtime already let
        // go of would play it again and hold its last frame.
        for (const each of running) if (each.playState === "running") each.finish();
        putAway(upcoming);
        if (upcoming === undefined) keeps(this, "data-lf-deck-flying", null);
      };
      this.#landing = land;
      // Where the deck began above the window, it comes back from its top at once.
      // Elsewhere the card is brought in nearest once its motion ends, since until then
      // the deck keeps the height of the card that went and the page may not reach far
      // enough. A nearest landing counts what the panel covers as unseen
      // (`alreadyShown`), so a card ending under it comes up to its foot where it fits
      // and to its top where it doesn't, its `scroll-margin-block` keeping the bar and
      // edges in view. Neither moves the page once the gesture is no longer the user's
      // latest (`moves`).
      const above = this.getBoundingClientRect().top < 0;
      const reveal = () => {
        if (above || !next || this.#open !== next || !moves()) return;
        scrollIntoView(next, { block: "nearest", behavior: "smooth" });
      };
      keeps(this, "data-lf-deck-flying", running.length ? "" : null);
      if (running.length) {
        (leave || enter)?.finished.then(
          () => putAway(),
          () => putAway(),
        );
        Promise.all(running.map((each) => each.finished.catch(() => {}))).then(() => {
          land();
          reveal();
        });
      } else {
        land();
        reveal();
      }
      // After an answer, a second press meant for the card that left lands on the one
      // that came up, so it takes none until it settles.
      if (next && answered) {
        keeps(next, "data-lf-deck-settling", "");
        setTimeout(() => keeps(next, "data-lf-deck-settling", null), SETTLE_MS);
      }
      this.dispatchEvent(
        new CustomEvent("lf-layout", { bubbles: true, composed: true }),
      );
      carry(next, answered ? SETTLE_MS : 0, moves);
      if (above && moves())
        scrollIntoView(this, { block: "start", behavior: "smooth" });
    }

    // The next waiting card after `card`, or the next card where there is no reading or
    // the user steps through a deck where nothing waits, as Review does; null at the
    // end of the pass.
    /** @param {HTMLElement} card @param {DeckReadings | null} readings @param {boolean} [stepping] */
    #after(card, readings, stepping = false) {
      const rest = this.#cards.slice(this.#cards.indexOf(card) + 1);
      const waiting = (/** @type {HTMLElement} */ each) =>
        Boolean(readings && waitsOn(readings(each)));
      if (!readings || (stepping && !this.#cards.some(waiting))) return rest[0] ?? null;
      return rest.find(waiting) ?? null;
    }

    // The user sends the open card toward `side`, from where a drag left it.
    /** @param {string} side @param {string} [from] */
    #onward(side, from = "none") {
      const card = this.#open;
      if (card) this.#go(this.#after(card, this.#readings(), true), side, { from });
    }

    #index() {
      const card = this.#open;
      return card ? this.#cards.indexOf(card) : this.#cards.length;
    }

    // What becomes of the user on what the deck puts away: the open card, a control
    // standing for it such as a suggestion's margin entry or its thread's reply box, the
    // forward control as the pass ends, or the end frame once a step back in leaves it.
    // One who was there by keyboard arrives at the card that comes up as `m` would, on
    // what waits there, so its own keys answer it, or at the step back in once the pass
    // is over; one who pressed lets go of what is hidden, and Tab goes on from where it
    // was. After an answer the arrival waits until the card has settled, so a key
    // pressed twice answers one card, and is made only while the gesture that moved
    // the deck is still the user's latest (`moves`), read as it lands. Read before
    // `leaving` goes.
    /** @param {HTMLElement[]} leaving */
    #carry(leaving) {
      const here = focusedElement();
      const place = here && placeOf(here);
      const inside = leaving.some(
        (each) =>
          (here !== null && here !== document.body && under(here, each)) ||
          Boolean(place && under(place, each)),
      );
      const focusVisible = inside && here !== null && here.matches(":focus-visible");
      return (/** @type {HTMLElement | null} */ next, wait = 0, moves = () => true) => {
        const keyed = focusVisible && moves();
        // A caret or selection left in the hidden card would start the next walk there.
        const selection = getSelection();
        if (
          selection?.rangeCount &&
          leaving.some((each) => under(selection.anchorNode, each))
        )
          selection.removeAllRanges();
        if (!inside) return;
        if (
          (!keyed || wait) &&
          (here instanceof HTMLElement || here instanceof SVGElement)
        )
          here.blur();
        if (!keyed) return;
        if (!wait) return this.#arrive(next);
        setTimeout(() => {
          const at = document.activeElement;
          if ((at === null || at === document.body) && moves()) this.#arrive(next);
        }, wait);
      };
    }

    /** @param {HTMLElement | null} card */
    #arrive(card) {
      if (!card) {
        this.#end.toggleAttribute("hidden", false);
        return void focusDestination(this.#again, "move");
      }
      const items = readObligations(card);
      const waiting = items.phase === "ready" ? items.user[0] : undefined;
      if (waiting) obligationActions.open(waiting.id);
      else focusDestination(card, "move");
    }

    #stepBack() {
      const index = this.#index();
      if (index <= 0) return;
      this.#go(this.#cards[index - 1], "back");
    }

    // The forward control's word, its accessible name and tooltip, and its symbol: on a
    // card, Later or Next; once the pass is over, back to its start.
    #forwardWord() {
      const readings = this.#readings();
      const card = this.#open;
      const waits = (/** @type {HTMLElement} */ each) =>
        Boolean(readings && waitsOn(readings(each)));
      if (card) return waits(card) ? "Later" : "Next";
      const left = this.#cards.filter(waits).length;
      return left ? `Go through the ${left} left` : "Review from the start";
    }

    /** @param {DeckReadings | null} readings */
    #forwardPress(readings) {
      const card = this.#open;
      if (card)
        return this.#onward(readings && waitsOn(readings(card)) ? "left" : "right");
      const waiting = readings && this.#cards.find((each) => waitsOn(readings(each)));
      this.#go(waiting ?? this.#cards[0], "rise");
    }

    // A touch drag on the open card, begun anywhere but on a control inside it.
    /** @param {PointerEvent} event */
    #press(event) {
      const card = this.#open;
      if (!(event.target instanceof Element) || !card?.contains(event.target)) return;
      if (event.pointerType !== "touch") return;
      if (
        event.target.closest(
          "button, a, input, textarea, select, [contenteditable], [role=button], [role=radio], [role=checkbox], [data-lf-offer]",
        )
      )
        return;
      // A second finger leaves a swipe under way to the first, whose hold it would
      // otherwise take with it unsettled.
      if (this.#drag?.moving) return;
      this.#drag = {
        id: event.pointerId,
        x: event.clientX,
        y: event.clientY,
        dx: 0,
        moving: false,
      };
    }

    /** @param {PointerEvent} event */
    #follow(event) {
      const drag = this.#drag;
      const card = this.#open;
      if (drag?.id !== event.pointerId || !card) return;
      drag.dx = event.clientX - drag.x;
      if (!drag.moving) {
        // A vertical move is the page scrolling (`touch-action: pan-y`).
        if (Math.abs(event.clientY - drag.y) > Math.abs(drag.dx))
          return (this.#drag = null);
        if (Math.abs(drag.dx) < 8) return;
        drag.moving = true;
        card.setPointerCapture(event.pointerId);
        // The user holds the card until the swipe settles, so no revision or undo
        // replaces it under the finger.
        drag.held = Promise.withResolvers();
        this.dispatchEvent(
          Object.assign(new Event("lf-hold", { bubbles: true, composed: true }), {
            complete: drag.held.promise,
          }),
        );
      }
      card.style.translate = `${drag.dx}px`;
      card.style.rotate = `${drag.dx / 30}deg`;
    }

    /** @param {PointerEvent} event */
    #release(event) {
      const drag = this.#drag;
      if (drag?.id !== event.pointerId) return;
      if (!drag.moving) return (this.#drag = null);
      const readings = this.#readings();
      const card = this.#open;
      const from = `translateX(${drag.dx}px) rotate(${drag.dx / 30}deg)`;
      this.#settle();
      if (drag.dx <= -SWIPE) this.#onward("left", from);
      else if (drag.dx >= SWIPE && !(readings && card && waitsOn(readings(card))))
        this.#onward("right", from);
    }

    #settle() {
      const card = this.#open;
      this.#drag?.held?.resolve();
      this.#drag = null;
      if (!card?.style.translate) return;
      card.style.removeProperty("translate");
      card.style.removeProperty("rotate");
    }

    render() {
      if (!this.#cards.length) return nothing;
      const readings = this.#readings();
      const card = this.#open;
      const count = readings
        ? tallyWords(tally(readObligations(this).all), agentName())
        : "";
      // A card's mark: open, waiting on the user, open with the agent, or answered.
      const mark = (/** @type {HTMLElement} */ each) => {
        if (each === card) return "open";
        if (!readings) return "";
        const { onUser, open, total } = tally(readings(each));
        return !total ? "" : onUser ? "waiting" : open ? "agent" : "done";
      };
      if (!card) this.#drawEnd(readings);
      return html`${this.#back}<span class="lf-deck-status"
          ><span class="lf-deck-pips" aria-hidden="true"
            >${this.#cards.map(
              (each) =>
                html`<span class="lf-deck-pip" data-lf-state=${mark(each)}></span>`,
            )}</span
          ><span class="lf-deck-count" role="status">${count}</span></span
        >${this.#forward}`;
    }

    // The end frame once the pass is over: how many still wait, the step back in (a
    // retained node), and the record of the pass, a row for each card that asks
    // something. A row names its question as On Me does, by the runtime's own rule
    // (`nameOf` on the question's row there), so the two lists never call one
    // question two things: a widget set among words, such as a suggestion, asks in no
    // group and so has no prompt words, and On Me names it by the words it suggests. The row
    // links to where the user answers it (`prompt.target`), so a card with no id of
    // its own opens too.
    /** @param {DeckReadings | null} readings */
    #drawEnd(readings) {
      const left = readings
        ? this.#cards.filter((each) => waitsOn(readings(each))).length
        : 0;
      const asked = readings ? this.#cards.filter((each) => readings(each).length) : [];
      const queues = readQueues();
      const listed = new Map(
        queues.phase === "ready"
          ? [...queues.on_user, ...queues.on_agent, ...queues.done].map((item) => [
              item.id,
              item,
            ])
          : [],
      );
      const row = (/** @type {HTMLElement} */ each) => {
        const held = readings?.(each) ?? [];
        const [first] = held;
        if (!first) return nothing;
        const target = first.prompt.target ?? each.id;
        const item = listed.get(first.id);
        const question = (item && nameOf(item)) || first.prompt.text || target;
        const [words, voice] = this.#ending(held);
        return html`<li>
          <a href=${target ? `#${target}` : nothing}>${question}</a
          ><span data-lf-voice=${voice ?? nothing}>${words}</span>
        </li>`;
      };
      render(
        html`<p>
            ${
              left
                ? `You've been through every card. ${left === 1 ? "One still waits" : `${left} still wait`} on you.`
                : "You've been through every card, and none waits on you."
            }
          </p>
          ${this.#again}
          ${
            asked.length
              ? html`<ol class="lf-deck-recap">
                  ${repeat(asked, (each) => each, row)}
                </ol>`
              : nothing
          }`,
        this.#end,
      );
      keepsText(this.#again, this.#forwardWord());
    }

    // What became of a card's question, and who says it: the answers given, in the
    // runtime's words and the interface's face, or Leaf's word for whom it waits on.
    /** @param {DeckHeld} held @returns {[string, "leaf" | null]} */
    #ending(held) {
      if (waitsOn(held)) return ["Still waiting", "leaf"];
      if (held.some((item) => item.state !== "done"))
        return [`Waiting on ${agentName()}`, "leaf"];
      const words = held.map(answerWords).filter(Boolean).join("; ");
      return words ? [words, null] : ["Answered", "leaf"];
    }

    updated() {
      if (!this.#cards.length) return;
      const word = this.#forwardWord();
      nameAction(this.#forward, this.#open ? "next" : "start", { label: word });
      // Once the pass is over the end frame's button is the step back in.
      keeps(this.#forward, "hidden", this.#open ? null : "");
      const readings = this.#readings();
      this.#end.toggleAttribute("hidden", Boolean(this.#open));
      if (!readings || this.#drag) return;
      const card = this.#open;
      const waiting = this.#cards.filter((each) => waitsOn(readings(each)));
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
        if (waiting.length && !waiting.includes(card))
          return void this.#show(waiting[0]);
      }
      const waits = waiting.includes(card);
      const held = readings(card);
      const answers = JSON.stringify(held.map((item) => item.answer?.value ?? null));
      if (waits && this.#answers && answers !== this.#answers)
        this.#moves = retainUserIntent();
      this.#answers = answers;
      // The reading that ends the open card's wait sends it on when an answer ended
      // each of its obligations and it waited on the user at a reading since it opened.
      // A comment leaves an obligation open with the agent, and the agent ending one
      // ends it without an answer, so neither moves the card.
      const answered = held.every((item) => item.state === "done" && item.answered);
      if (waits) this.#waited = true;
      else if (this.#waited && held.length && answered)
        this.#go(this.#after(card, readings), "right", {
          answered: true,
          moves: this.#moves ?? (() => false),
        });
    }
  },
);
