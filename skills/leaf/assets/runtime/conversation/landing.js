/* Landing the reader in a conversation: which node a reveal shows, and where focus
   goes.

   `showThread` reveals a directly requested thread or message. It clears a narrowing
   that hides the destination and finishes an outgoing resolution fold before choosing
   its lifecycle state. A thread reached in the complete panel opens in its reply box;
   the compact margin view opens on its card and reveals that box only when the reader
   asks to reply. A resolved thread opens on its card. A message takes focus at its own
   words so Tab reaches its controls. A
   thread too tall for its scrollport starts at the earliest complete content block
   that still leaves its reply area visible. That puts the first visible content on a
   clean boundary instead of leaving an arbitrary partial message line below the pinned
   heading. The transient arrival flash belongs to the revealed target — short card,
   reply area, message, or oversized editor — rather than to a long card spanning
   beyond the scrollport. The explicit `t`/`T` walk remains on card roots—inline while
   Threads is closed, in the panel while it is open; Enter starts a reply and Escape
   returns to the card. An accepted anchored comment continues in the open Threads panel,
   widening a filter that would hide it.

   A keyboard-entered box hands the reader back through its captured return frame.
   `boxReturnFrame` and `standingConversation` climb the same conversation relation, so
   “comment on the thread” going in and “back to thread” coming out name one element. The
   panel's general box returns to the Threads list when it was entered there, and to the
   prior page place and auxiliary chrome state when page `c` entered it directly. `backFromBox` remains
   the fallback for Tab or pointer arrival, where no keyboard entry exists to restore. A
   page-owned first-message seat has no standing place of its own; a widget control that
   explicitly enters its box supplies the caller-owned return target through
   `landInConversation`. */
import { shownBand, shownBox } from "../geometry.js";
import { focused } from "../keyboard/scopes.js";
import { scrollBehavior } from "../motion.js";
import { closestAcross } from "../passages.js";
import { threadsBox } from "./panel-elements.js";
import { reachedForWords } from "../widget-elements.js";
import { finishFold } from "./folding.js";
import { SAYS_IN, SAY_BOX } from "./selectors.js";

export { SAY_BOX } from "./selectors.js";
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

export function revealConversation(held, control, behavior = scrollBehavior()) {
  landingTarget(held, control).scrollIntoView({
    behavior,
    block: "nearest",
  });
}

const conversationInputOf = (held) => {
  const box = held?.querySelector(SAY_BOX);
  return box && (shownBox(box).height || box.lfRevealReply) ? box : null;
};

// Start a long direct arrival on the earliest complete content block that still leaves
// its reply target in the list's landable band. Native nearest-edge scrolling guarantees
// the target is visible, but it can put the sticky heading through the middle of a text
// line. The message bodies already expose their authored block boundaries; use those
// rather than attempting to infer line boxes from prose.
const threadLandingStart = (held, target, threadsBox) => {
  const band = shownBand(threadsBox);
  if (!band) return target;
  const style = getComputedStyle(threadsBox);
  const room =
    band.bottom -
    band.top -
    (parseFloat(style.scrollPaddingTop) || 0) -
    (parseFloat(style.scrollPaddingBottom) || 0);
  const targetBox = shownBox(target);
  const candidates = [
    ...held.querySelectorAll(
      ":scope > .lf-msg, :scope > .lf-msg .lf-msg-body > *, " +
        ":scope > .lf-msg .lf-msg-text > *",
    ),
    target,
  ]
    .map((node) => ({ node, box: shownBox(node) }))
    .filter(
      ({ node, box }) =>
        node === target ||
        (getComputedStyle(node).display !== "contents" &&
          box.height > 0 &&
          box.top <= targetBox.top &&
          targetBox.bottom - box.top <= room),
    )
    .sort((a, b) => a.box.top - b.box.top);
  return candidates[0]?.node ?? target;
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

function prepareLanding({ held = null, box, route = null }) {
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
  return { held, box };
}

// A completion may navigate only until the reader's next gesture or focus moves
// elsewhere. Replacing its control can drop focus to body without a new intent.
let landingIntent = 0;
const leaveLanding = () => landingIntent++;
for (const type of ["pointerdown", "keydown", "input", "wheel"])
  addEventListener(type, leaveLanding, { capture: true, passive: true });
addEventListener("blur", leaveLanding);
const retainLanding = (source, available, fallback = null) => {
  const intent = landingIntent;
  return () => {
    const at = focused();
    return (
      available() &&
      intent === landingIntent &&
      (at === document.body || at === fallback || source.contains(at))
    );
  };
};

export const retainPanelLanding = (source, panelIsOpen) =>
  retainLanding(source, panelIsOpen, threadsBox);

// A candidate can remove the reader's direct conversation box before a later renderer
// refuses that state. Restore the same logical conversation and caret after its prior
// view is reconciled, unless a newer reader gesture has taken over.
export function retainConversationFocus(panelIsOpen) {
  const input = focused();
  const held = input && closestAcross(input, SAYS_IN);
  if (!held || held.querySelector(SAY_BOX) !== input) return () => {};
  const selection = [
    input.selectionStart,
    input.selectionEnd,
    input.selectionDirection,
  ];
  let restoredInput;
  let mayLand;
  if (held.matches(".lf-thread") && held.parentElement === threadsBox) {
    const id = held.dataset.id;
    restoredInput = () =>
      threadsBox
        .querySelector(`.lf-thread[data-id="${CSS.escape(id)}"]`)
        ?.querySelector(SAY_BOX);
    mayLand = retainPanelLanding(held, panelIsOpen);
  } else if (held.matches(".lf-conversation-thread")) {
    const host = held.parentElement;
    const id = held.dataset.thread;
    restoredInput = () =>
      host
        .querySelector(
          `:scope > .lf-conversation-thread[data-thread="${CSS.escape(id)}"]`,
        )
        ?.querySelector(SAY_BOX);
    mayLand = retainLanding(held, () => host.isConnected);
  } else if (held.matches(".lf-conversation")) {
    restoredInput = () => held.querySelector(SAY_BOX);
    mayLand = retainLanding(held, () => held.isConnected);
  } else return () => {};
  return () => {
    if (!mayLand()) return;
    const restored = restoredInput();
    if (!restored) return;
    restored.focus({ preventScroll: true });
    restored.setSelectionRange(...selection);
  };
}
// Landing belongs to the list, not to whatever moved the focus. The list already says
// which of its own edges cannot be stood on — `scroll-padding`, room for a stuck
// heading and for the focused card's edge — and every route that could reach a thread
// was scrolling it into that band for itself, so a route that did not scroll got
// nothing. A press does not: the browser focuses the card under the pointer and scrolls
// nothing, so a list nudged a dozen pixels leaves the first card of a run two pixels
// under its heading, which hides its top border and leaves the current card's quiet
// edge-and-surface cue incomplete.
// The routes that resolve a thread rather than press one — a page mark's comment note,
// the thread a resolve or a reopen hands the reader on to — landed only by chance of
// having remembered the line.
//
// Focus is the one fact all of them share, so the landing hangs off that and each of
// them gives up its copy. Four callers still write this list's scroll, and each says
// something focus cannot: `stepThread` for the press at either end of the walk, which
// moves no focus at all; `showThread` for a deliberate arrival, which runs after
// the focus it follows and wins; `placeThreadEdge` for an explicit edge placement;
// and `landIn`, which puts the reader in a thread's box and lands the thread around it,
// the same correction this makes and the reason a reply box reached by key was never
// the case that was wrong.
//
// The thread holding the focus, not the card alone: the current-card paint belongs to
// the thread and follows `:focus-within`, so the same edge must clear the band whether
// the reader is standing on the card or writing in its box. `block: "nearest"` moves
// the least that clears the band, so a control at the card's foot comes with it rather
// than going under.
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
const finishPress = (event, shouldLand) => {
  if (event.pointerId !== pressedPointer) return;
  pressedPointer = null;
  if (!shouldLand) return;
  const thread = standing();
  if (thread && !reachedForWords(thread)) land(thread);
};
addEventListener("pointerup", (event) => finishPress(event, true), true);
addEventListener("pointercancel", (event) => finishPress(event, false), true);
// Mounted from leaf.js.
export function wireThreadLanding() {
  threadsBox.addEventListener("pointerdown", (event) => {
    if (event.isPrimary) pressedPointer = event.pointerId;
  });
  threadsBox.addEventListener("focusin", () => {
    if (pressedPointer === null) land(standing());
  });
}

// Shown, not merely standing: a card the narrowing hid keeps its node (thread-list.js),
// and a destination in one is as unreachable as a destination with no node at all.
const listNode = (id) => {
  const node = threadsBox.querySelector(
    `.lf-thread[data-id="${id}"], .lf-msg[data-mid="${id}"]`,
  );
  return node?.closest(".lf-thread[hidden]") ? null : node;
};

// Direct navigation reveals what was requested, including a message's interactive
// controls or a resolved thread. A thread arrives ready for a reply; a message keeps
// focus at its own words so Tab reaches its controls. Sending a reply stays with its
// editor through revealConversation instead.
function showThreadNow(id, focus, revealThread) {
  let node = listNode(id);
  const going = node?.closest(".lf-going");
  if (going) {
    finishFold(going.dataset.id);
    revealThread(id);
    node = listNode(id);
  } else if (!node) {
    revealThread(id);
    node = listNode(id);
  }
  if (!node) return;
  const thread = node.closest(".lf-thread");
  if (focus) {
    const destination =
      focus === "thread"
        ? thread
        : node === thread
          ? (conversationInputOf(thread) ?? thread)
          : node;
    destination.focus({ preventScroll: true });
  }
  const directThread = node === thread && thread.contains(focused());
  const target = directThread ? landingTarget(thread, focused()) : node;
  const scrollTarget =
    directThread && target !== thread
      ? threadLandingStart(thread, target, threadsBox)
      : target;
  scrollTarget.scrollIntoView({
    behavior: scrollBehavior(),
    // A long thread begins at the clean content boundary chosen above. A short card
    // is context in full; a requested message keeps the least-moving direct route.
    block: target === thread ? "center" : directThread ? "start" : "nearest",
  });
  target.classList.remove("grow");
  target.classList.add("flash");
  setTimeout(() => target.classList.remove("flash"), 1300);
}

export function createConversationLanding({ setPanel, scrollToThread, revealThread }) {
  const landIn = (destination) => {
    const prepared = prepareLanding(destination);
    if (!prepared) return false;
    const { held, box } = prepared;
    box.lfRevealReply?.();
    box.focus({ preventScroll: true });
    revealConversation(held, box);
    if (held.dataset.id) scrollToThread(held.dataset.id);
    return true;
  };
  const landInConversation = (box, route = null) => landIn({ box, route });
  const showThread = (id, { focus = "reply" } = {}) => {
    setPanel(true);
    showThreadNow(id, focus, revealThread);
  };
  return { landIn, landInConversation, showThread };
}
