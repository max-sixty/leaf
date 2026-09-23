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
   beyond the scrollport. The explicit `t`/`T` walk remains on a thread's native title
   in the panel and on the card root inline; Enter and Space therefore keep their native
   disclosure meaning. An accepted anchored comment continues in the open Threads panel,
   widening a filter that would hide it.

   `backFromBox` and `standingConversation` climb the same conversation relation, so
   “comment on the thread” going in and “back to thread” coming out name one element. It
   answers for every arrival — a keyboard command, a Tab, a pointer — because a box's way
   out is the conversation it belongs to whichever of them put the reader in it, and the
   panel's own general box hands back to the Threads list. A page-owned first-message seat
   has no standing place of its own; a widget control that explicitly enters its box
   supplies the caller-owned return target through `landInConversation`. */
import { landingBand, shownBox } from "../geometry.js";
import { documentFocused, focused } from "../keyboard/scopes.js";
import { takesLetters } from "../focus.js";
import { scrollBehavior } from "../motion.js";
import { closestAcross } from "../passages.js";
import { panel, threadsBox } from "./panel-elements.js";
import { reachedForWords, reveal } from "../widget-elements.js";
import { finishFold } from "./folding.js";
import { SAYS_IN, SAY_BOX } from "./selectors.js";
import { retainReaderIntent } from "../reader-intent.js";
import { focusDestination, readCaret } from "../focus.js";
import { pageScope } from "../keyboard/register.js";
import { TEXT_ENTRY } from "../keyboard/text-entry.js";
import { threadList } from "./state.js";
import { focusedThread, focusThread } from "./focus.js";
import { threadSearchActive } from "./narrowing.js";

export { SAY_BOX } from "./selectors.js";
const conversationReturns = new WeakMap();

// Keep a whole conversation in view when it fits. A long thread reveals its reply
// area, including Send and Resolve; an oversized editor reveals only its control.
// scrollIntoView(nearest) on a card spanning both edges otherwise moves nothing.
const landingTarget = (held, control) => {
  let room = Infinity;
  for (let parent = held.parentElement; parent; parent = parent.parentElement) {
    const band = landingBand(parent);
    if (band) room = Math.min(room, band.bottom - band.top);
  }
  if (shownBox(held).height <= room) return held;
  const reply = control.closest(".lf-compose, .lf-say");
  return reply?.parentElement === held && shownBox(reply).height <= room
    ? reply
    : control;
};

export function revealConversation(
  held,
  control,
  behavior = scrollBehavior(),
  block = "nearest",
) {
  landingTarget(held, control).scrollIntoView({
    behavior,
    block,
  });
}

const conversationInputOf = (held) => {
  const box = held?.querySelector(SAY_BOX);
  return box && (shownBox(box).height || box.lfRevealReply) ? box : null;
};

// Start a long direct arrival on the earliest complete content block that still leaves
// its reply target in the list's landable band. Native nearest-edge scrolling guarantees
// the target is visible, but it can put the sticky heading through the middle of a text
// line. The thread header and message bodies expose complete block boundaries; use
// those rather than attempting to infer line boxes from prose.
const threadLandingStart = (held, target, threadsBox) => {
  const band = landingBand(threadsBox);
  if (!band) return target;
  const room = band.bottom - band.top;
  const targetBox = shownBox(target);
  const candidates = [
    ...held.querySelectorAll(
      ":scope > *, :scope > .lf-msg .lf-msg-body > *, " +
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

// Where a box hands the reader back, however they reached it. This once asked only for
// `.lf-thread` and the panel, so the two boxes outside the chrome — a conversation seated
// on the page, and each thread on that seat — had no relation to return through. The climb
// is `heldConversation`'s, the same relation contextual `c` uses when it names a thread.
//
// A seat holding no thread yet has no standing place of its own. A widget control that
// explicitly sends the reader into that box can supply its own return through
// `landInConversation`; a visit reached by Tab still falls through to the page's "let go".
// Otherwise the question is "can the reader be put here", rather than a list of which two
// containers happen to be focusable — which is also why a seat that `reachScrollers` makes
// focusable, having grown a scrollbar and no focusable child, becomes a rung without anyone
// editing this: the question is the same one, and the answer moved.
function backFromBox() {
  const held = heldConversation();
  if (held?.matches(".lf-thread, .lf-conversation-thread"))
    return { target: held, line: "back to thread" };
  const route = backFromConversation(focused());
  return route?.target?.isConnected ? route : null;
}
// Whether the box the reader is typing in has somewhere to hand them back: the
// conversation it belongs to, or the panel's list where it is the chrome's own box. The
// page's standing scope asks the same question, since a box with nowhere to go back to
// is a control the reader is standing on, theirs to let go of.
export const boxHandsBack = () =>
  Boolean(backFromBox()) || panel.contains(documentFocused());

// A box words are typed into takes character keys and the keys that edit it: Enter,
// deletion, caret movement, Home/End, and page movement, including their modified forms.
// Escape remains the box's to declare or pass on. What it declares is the way back out — to
// the thread a reply belongs to, so Esc then Enter round-trips, or to the list, so t/T walk
// on from where the backing-out started. Drafts are kept at every rung.
//
// A control the reader is standing on rather than writing in keeps that rung without this
// scope carrying a second branch for it: the scope claims the keys a box takes and leaves
// every other press — c, the walks, the versions, the reference — to the scopes behind it.
pageScope("text entry", {
  title: "In a text box",
  root: focused,
  at: () => takesLetters(focused()),
  claims: TEXT_ENTRY,
  rows: [
    {
      id: "text.leave",
      keys: ["Escape"],
      does: "Leave the box, keeping what is typed",
      line: () => backFromBox()?.line ?? "back to list",
      // The conversation the box belongs to, or the panel's list where it is the chrome's
      // own box. A page textarea that is neither leaves the row dead and the page's rung
      // standing, which is the honest answer: nothing there to go back to.
      when: boxHandsBack,
      run: () => {
        const back = backFromBox();
        document.activeElement.blur();
        const target = back?.target ?? threadsBox;
        if (target.matches?.(".lf-thread, .lf-conversation-thread"))
          focusThread(target);
        else target.focus();
      },
    },
  ],
});

// A thread's own keys, live wherever the reader stands in one: the card, the message a
// click on its words focuses, the quote, a link in a reply. `r` settles the thread from any
// of them, since a control, a widget, or a text box that owns a letter is walked first.
// Enter replies or reopens only from the card, where no control inside has an Enter of its
// own to lose. The reopen button tells the two states apart; absent a thread, the reference
// describes the open state readers first meet.
const heldThread = () =>
  documentFocused()?.closest(".lf-thread, .lf-conversation-thread") ?? null;
const resolutionControl = (thread) =>
  thread?.querySelector(
    ":scope .lf-thread-meta-actions > .lf-resolve, " +
      ":scope > .lf-thread-actions > .lf-reopen, " +
      ":scope > .lf-conversation-resolved .lf-reopen",
  ) ?? null;

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

const retainLanding = (source, available, fallback = null) => {
  return retainReaderIntent({ source, available, fallback });
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
  const caret = readCaret(input);
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
    focusDestination(restored, caret);
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
const land = (thread, behavior) => {
  if (thread && threadsBox.contains(thread))
    revealConversation(thread, focused(), behavior);
};
// The primary pointer owns the provisional landing until that same gesture ends. A
// cancellation means the browser took it for something else — commonly a touch scroll —
// so release the hold without undoing the gesture by landing the thread.
const finishPress = (event, shouldLand) => {
  if (event.pointerId !== pressedPointer?.id) return;
  const pressedThread = pressedPointer.thread;
  pressedPointer = null;
  if (!shouldLand) return;
  const thread = standing() ?? pressedThread;
  if (thread && !reachedForWords(thread)) {
    if (!thread.contains(focused())) focusThread(thread, { preventScroll: true });
    // Instantly, because this correction is the one with a later writer behind it. The
    // press's click is the next thing to run, and a click on a thread title reflows the
    // list, whose hold writes `scrollTop` a frame after (thread-list.js). A write lands
    // on a smooth scroll as a cancellation rather than a supersession, so an animated
    // correction is not superseded by what the gesture asks for next — it is dropped,
    // and the reader keeps neither the landing nor the place. Arriving before the click
    // is also what lets that hold take its reference from the landed geometry rather
    // than from the band this was still leaving. The `focusin` landing below has no
    // such successor and keeps the shared behavior.
    land(thread, "instant");
  }
};
addEventListener("pointerup", (event) => finishPress(event, true), true);
addEventListener("pointercancel", (event) => finishPress(event, false), true);
// Mounted from leaf.js.
export function wireThreadLanding() {
  threadsBox.addEventListener("pointerdown", (event) => {
    if (event.isPrimary)
      pressedPointer = {
        id: event.pointerId,
        thread: event.target.closest?.(".lf-thread") ?? null,
      };
  });
  threadsBox.addEventListener("focusin", () => {
    if (pressedPointer === null) land(standing());
  });
}

// Shown, not merely standing: a card the narrowing hid keeps its node (thread-list.js),
// and a destination in one is as unreachable as a destination with no node at all.
const listNode = (id, preferMessage = false) => {
  const message = `.lf-msg[data-mid="${CSS.escape(id)}"]`;
  const thread = `.lf-thread[data-id="${CSS.escape(id)}"]`;
  const node = preferMessage
    ? (threadsBox.querySelector(message) ?? threadsBox.querySelector(thread))
    : (threadsBox.querySelector(thread) ?? threadsBox.querySelector(message));
  return node?.closest(".lf-thread[hidden]") ? null : node;
};

// Direct navigation reveals what was requested, including a message's interactive
// controls or a resolved thread. A thread arrives ready for a reply; a message keeps
// focus at its own words so Tab reaches its controls.
async function showThreadNow(id, focus, revealThread) {
  const mayArrive = retainReaderIntent({
    source: focused(),
    available: () => threadsBox.isConnected,
    fallback: threadsBox,
  });
  // A direct arrival owns the target's one transition cue. Remove a retained arrival
  // animation before an asynchronous reveal gives the browser a frame to start it.
  threadsBox
    .querySelector(
      `.lf-thread[data-id="${CSS.escape(id)}"], .lf-msg[data-mid="${CSS.escape(id)}"]`,
    )
    ?.classList.remove("grow");
  threadsBox.revealNavigation(id);
  let node = listNode(id, focus === "message");
  const going = node?.closest(".lf-going");
  if (going) {
    finishFold(going.dataset.id);
    const revealed = revealThread(id);
    if (!revealed) return false;
    await revealed;
    if (!mayArrive()) return false;
    node = listNode(id, focus === "message");
  } else if (!node) {
    const revealed = revealThread(id);
    if (!revealed) return false;
    await revealed;
    if (!mayArrive()) return false;
    node = listNode(id, focus === "message");
  }
  threadsBox.revealNavigation(id);
  node = listNode(id, focus === "message");
  if (!node || !mayArrive()) return false;
  if (node.closest(".lf-summary-originals[hidden]")) {
    await reveal(node, mayArrive);
    if (!mayArrive()) return false;
  }
  const thread = node.closest(".lf-thread");
  if (focus) {
    const destination =
      focus === "thread"
        ? thread
        : node === thread
          ? (conversationInputOf(thread) ?? thread)
          : node;
    if (destination === thread) focusThread(thread, { preventScroll: true });
    else destination.focus({ preventScroll: true });
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
  return true;
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
    const ready = showThreadNow(id, focus, revealThread);
    // Pointer and keyboard routes deliberately discard this ticket. The conversation
    // coordinator reports its one failure; the landing result keeps that rejection out
    // of both discarded event-handler promises and callers that continue a delivery.
    return ready.then(
      (arrived) => arrived,
      () => false,
    );
  };
  return { landIn, landInConversation, showThread };
}

/** Declare a thread's own keys against the landing the page is using.
 *
 * Separate from constructing that landing, because they are separate acts: a second
 * landing owner — one a test builds to hold a reveal open — is another way of landing,
 * not another set of keys, and declaring from the constructor would let it quietly take
 * the page's. */
export function declareThreadKeys(landIn, read) {
  pageScope("thread", {
    title: "In a thread",
    root: focused,
    when: () => threadList().length > 0,
    at: () => Boolean(heldThread()),
    rows: [
      {
        id: "thread.primary",
        keys: ["Enter"],
        does: () =>
          resolutionControl(focusedThread())?.matches(".lf-reopen")
            ? "Reopen it"
            : "Write a reply",
        line: () =>
          resolutionControl(focusedThread())?.matches(".lf-reopen")
            ? "reopen"
            : "reply",
        when: () =>
          Boolean(conversationInput(focusedThread())) ||
          resolutionControl(focusedThread())?.matches(
            '.lf-reopen:not(:disabled, [aria-disabled="true"])',
          ),
        // Find the thread's own compose row rather than the first textarea: a message may
        // contain a widget with an editor of its own before the reply box in DOM order.
        run: () => {
          const thread = focusedThread();
          const reopen = resolutionControl(thread)?.matches(".lf-reopen")
            ? resolutionControl(thread)
            : null;
          if (reopen) reopen.click();
          else landIn({ held: thread, box: conversationInput(thread) });
        },
      },
      {
        id: "thread.read.mark",
        keys: ["m"],
        does: "Mark this thread read",
        line: "mark read",
        when: () => {
          const id = heldThread()?.dataset.id ?? heldThread()?.dataset.thread;
          return Boolean(
            id &&
            threadList().find(
              (thread) => thread.root.id === id && thread.unread.length,
            ),
          );
        },
        run: () => {
          const id = heldThread()?.dataset.id ?? heldThread()?.dataset.thread;
          if (id) read.markThread(id);
        },
      },
      {
        id: "thread.resolution.toggle",
        keys: ["r"],
        does: () =>
          resolutionControl(heldThread())?.matches(".lf-reopen")
            ? "Reopen it"
            : "Resolve it",
        line: () =>
          resolutionControl(heldThread())?.matches(".lf-reopen") ? "reopen" : "resolve",
        // Search keeps its next/previous hints; resolution remains in the reference.
        lineWhen: () => !threadSearchActive(),
        when: () =>
          resolutionControl(heldThread())?.matches(
            ':not(:disabled, [aria-disabled="true"])',
          ),
        run: () => resolutionControl(heldThread()).click(),
      },
    ],
  });
}
