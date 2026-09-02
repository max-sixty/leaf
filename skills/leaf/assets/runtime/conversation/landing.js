import { shownBand, shownBox } from "../geometry.js";
import { focused } from "../keyboard/scopes.js";
import { scrollBehavior } from "../motion.js";
import { closestAcross } from "../passages.js";

const SAYS_IN = ".lf-thread, .lf-conversation-thread, .lf-conversation";
export const SAY_BOX = ":scope > .lf-compose textarea, :scope > .lf-say textarea";
const conversationReturns = new WeakMap();

// Keep a whole conversation in view when it fits. A long thread reveals its reply
// area, including Send and Resolve; an oversized editor reveals only its control.
// scrollIntoView(nearest) on a card spanning both edges otherwise moves nothing.
const landingTarget = (held, control) => {
  let room = Infinity;
  for (let parent = held.parentElement; parent; parent = parent.parentElement) {
    const band = shownBand(parent);
    if (!band) continue;
    const style = getComputedStyle(parent);
    room = Math.min(
      room,
      band.bottom -
        band.top -
        (parseFloat(style.scrollPaddingTop) || 0) -
        (parseFloat(style.scrollPaddingBottom) || 0),
    );
  }
  if (shownBox(held).height <= room) return held;
  const reply = control.closest(".lf-compose, .lf-say");
  return reply?.parentElement === held && shownBox(reply).height <= room
    ? reply
    : control;
};

export function revealConversation(held, control) {
  landingTarget(held, control).scrollIntoView({
    behavior: scrollBehavior(),
    block: "nearest",
  });
}

const conversationInputOf = (held) => {
  const box = held?.querySelector(SAY_BOX);
  return box && shownBox(box).height ? box : null;
};

export function conversationInput(node) {
  const held = node && closestAcross(node, SAYS_IN);
  return conversationInputOf(held);
}

export const heldConversation = () => focused() && closestAcross(focused(), SAYS_IN);
export const standingConversation = () => {
  const held = heldConversation();
  const box = conversationInputOf(held);
  return box ? { held, box } : null;
};
export const backFromConversation = (box) => conversationReturns.get(box) ?? null;

let publishedLand;
export const landIn = (...args) => publishedLand(...args);
export function landInConversation(box, route = null) {
  return publishedLand({ box, route });
}

export function createConversationLanding({ scrollToThread }) {
  const focusConversation = ({ held, box }) => {
    box.focus({ preventScroll: true });
    revealConversation(held, box);
    if (held.dataset.id) scrollToThread(held.dataset.id);
  };
  publishedLand = ({ held = null, box, route = null }) => {
    if (
      route &&
      (!(route.target instanceof Element) ||
        typeof route.line !== "string" ||
        !route.line.trim())
    )
      throw new TypeError(
        "landInConversation return route needs an element target and a non-empty line",
      );
    held ??= box && closestAcross(box, SAYS_IN);
    if (!held) return false;
    if (route && !held.hasAttribute("tabindex")) {
      conversationReturns.set(box, route);
      box.addEventListener("blur", () => conversationReturns.delete(box), {
        once: true,
      });
    }
    focusConversation({ held, box });
    return true;
  };
}

export function createPanelLanding({
  finishFold,
  reachedForWords,
  setPanel,
  threadsBox,
  widen,
}) {
  // Landing belongs to the list, not to whatever moved the focus. The list already says
  // which of its own edges cannot be stood on — `scroll-padding`, room for a stuck
  // heading and for a ring — and every route that could reach a thread was scrolling it
  // into that band for itself, so a route that did not scroll got nothing. A press does
  // not: the browser focuses the card under the pointer and scrolls nothing, so a list
  // nudged a dozen pixels leaves the first card of a run two pixels under its heading,
  // which is the whole of an inset ring's top run and reads as a card with three sides.
  // The routes that resolve a thread rather than press one — a page mark's comment note,
  // the thread a resolve or a reopen hands the reader on to — landed only by chance of
  // having remembered the line.
  //
  // Focus is the one fact all of them share, so the landing hangs off that and each of
  // them gives up its copy. Four callers still write this list's scroll, and each says
  // something focus cannot: `stepThread` for the press at either end of the walk, which
  // moves no focus at all; `showThread` for a deliberate centring, which runs after
  // the focus it follows and wins; `placeThreadEdge` for an explicit edge placement;
  // and `landIn`, which puts the reader in a thread's box and lands the thread around it,
  // the same correction this makes and the reason a reply box reached by key was never
  // the case that was wrong.
  //
  // The thread holding the focus, not the card alone: the ring is the thread's, drawn
  // for `:focus-within`, so it is cut in the same place whether the reader is standing
  // on the card or writing in its box. `block: "nearest"` moves the least that clears
  // the band, so a control at the card's foot comes with it rather than going under.
  //
  // A press is the reader's hand, and it may be the start of a drag across the comment's
  // own words. Focus lands on the way down, so scrolling there takes the words out from
  // under the pointer and the selection runs on past where they stopped — measured at
  // three times the run the reader drew. A press therefore holds its landing until the
  // hand comes up, and gives it up altogether where the press was a drag for the
  // thread's own words: the question `offer` already asks of a click, read the same way,
  // since the selection's focus end is the character the button came up on.
  //
  // The hand comes up before the press's click, which is where a deliberate placement
  // begins — a quote jumping to its passage, a travel centring a widget in a reply. So
  // the order holds without a word between them: the landing is a correction under the
  // gesture, and whatever the gesture then asks for is later and wins.
  //
  // What the press lands is where it left the reader, which is not the same question as
  // which thread the focus moved to. A press on the thread the reader is already in
  // moves no focus and so was heard as nothing at all — and that is the reader's own
  // gesture: they are standing in a comment, the list carries a little, and they press
  // the card to bring it back. Asking the completed gesture instead of the focus event
  // costs a variable rather than buying one, and the walk's own end-of-clamp press is
  // the same shape one scope out.
  let pressedPointer = null;
  const standing = () => focused()?.closest?.(".lf-thread");
  const land = (thread) => {
    if (thread && threadsBox.contains(thread)) revealConversation(thread, focused());
  };
  // The primary pointer owns the provisional landing until that same gesture ends. A
  // cancellation means the browser took it for something else — commonly a touch scroll —
  // so release the hold without undoing the gesture by landing the thread.
  threadsBox.addEventListener("pointerdown", (event) => {
    if (event.isPrimary) pressedPointer = event.pointerId;
  });
  const finishPress = (event, shouldLand) => {
    if (event.pointerId !== pressedPointer) return;
    pressedPointer = null;
    if (!shouldLand) return;
    const thread = standing();
    if (thread && !reachedForWords(thread)) land(thread);
  };
  addEventListener("pointerup", (event) => finishPress(event, true), true);
  addEventListener("pointercancel", (event) => finishPress(event, false), true);
  threadsBox.addEventListener("focusin", () => {
    if (pressedPointer === null) land(standing());
  });

  const listNode = (id) =>
    threadsBox.querySelector(`.lf-thread[data-id="${id}"], .lf-msg[data-mid="${id}"]`);

  // Direct navigation reveals what was requested, including a message's interactive
  // controls or a resolved thread. A thread arrives ready for a reply; a message keeps
  // focus at its own words so Tab reaches its controls. Sending a reply stays with its
  // editor through revealConversation instead.
  function showThread(id, { stand = true } = {}) {
    setPanel(true);
    if (!listNode(id)) widen();
    let node = listNode(id);
    const going = node?.closest(".lf-going");
    if (going) {
      finishFold(going.dataset.id);
      node = listNode(id);
    }
    if (!node) return;
    const thread = node.closest(".lf-thread");
    const disclosure = thread.closest(".lf-details");
    if (disclosure) disclosure.open = true;
    if (stand) {
      const destination =
        node === thread ? (conversationInputOf(thread) ?? thread) : node;
      destination.focus({ preventScroll: true });
    }
    const target =
      node === thread && thread.contains(focused())
        ? landingTarget(thread, focused())
        : node;
    target.scrollIntoView({
      behavior: scrollBehavior(),
      block: target === thread ? "center" : "nearest",
    });
    thread.classList.remove("grow");
    thread.classList.add("flash");
    setTimeout(() => thread.classList.remove("flash"), 1300);
  }

  return { showThread };
}
