/* Landing the user in a thread: which node a reveal shows, and where focus
   goes.

   `showThread` reveals a directly requested thread or message. It clears a narrowing
   that hides the destination and finishes an outgoing resolution fold before choosing
   its lifecycle state. A thread reached in the complete panel opens in its reply box;
   the compact margin view opens on its card and reveals that box only when the user
   asks to reply. A resolved thread opens on its card. A message takes focus at its own
   words so Tab reaches its controls. A
   thread too tall for its scrollport starts at the earliest complete content block
   that still leaves its reply area visible. That puts the first visible content on a
   clean boundary instead of leaving an arbitrary partial message line below the pinned
   heading. The transient arrival flash belongs to the revealed target — short card,
   reply area, message, or oversized editor — rather than to a long card spanning
   beyond the scrollport. The explicit `t`/`T` walk remains on a thread's native title
   in the panel and on the card root inline, and a title arriving by key shows a thread
   too tall for the list from its start; Enter and Space choose a closed panel thread,
   and Enter on an open one's title writes a reply. An accepted anchored comment
   continues in the open Threads panel, widening a filter that would hide it. A landing
   waits for the render in flight and for a resolution fold to end, since both move what
   it would measure. Where a thread lands in its scroller is `reply-landing.js`'s.

   `backFromBox` and `standingThread` climb the same thread relation, so
   “comment on the thread” going in and “back to thread” coming out name one element. It
   answers for every arrival — a keyboard command, a Tab, a pointer — because a box's way
   out is the thread it belongs to whichever of them put the user in it, and the
   panel's own general box hands back to the Threads list. A page-owned first-message seat
   has no standing place of its own; a widget control that explicitly enters its box
   supplies the caller-owned return target through `landInThread`. A send from a
   thread's box leaves it the same way, onto the thread, except in the margin card,
   whose thread stands for the element it is about (`landSent`). */
import { landingBand, seenRect, shownBox } from "../geometry.js";
import { documentFocused, focused } from "../keyboard/scopes.js";
import { focusDestination, takesLetters } from "../focus.js";
import { scrollBehavior } from "../motion.js";
import { bringBackSurfaceOf } from "../off-flow.js";
import { closestAcross } from "../passages.js";
import { reachedForWords, reveal } from "../widget-elements.js";
import { finishFold, hasFolding, whenFolded } from "./folding.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { SAYS_IN, THREAD } from "./selectors.js";
import { retainUserIntent } from "../user-intent.js";
import { pageScope } from "../keyboard/register.js";
import { TEXT_ENTRY } from "../keyboard/text-entry.js";
import { threadList } from "./state.js";
import {
  focusedThreadTarget,
  focusThread,
  heldThread,
  threadReplyInput,
  threadFocusDestination,
} from "./focus.js";
import { fitsWhole, landingTarget, scrollThreadIntoView } from "./reply-landing.js";

export { SAY_BOX } from "./selectors.js";
export { scrollThreadIntoView } from "./reply-landing.js";
const threadReturns = new WeakMap();

// Start a long direct arrival on the earliest complete content block that still leaves
// its reply target in the list's landable band: the reply area, or the thread's end
// where the target is the thread itself, since a reply row pinned at the list's foot
// stands over that end. Native nearest-edge scrolling guarantees the target is visible,
// but it can put the sticky heading through the middle of a text line. The thread
// header and message bodies expose complete block boundaries; use those rather than
// attempting to infer line boxes from prose.
const threadLandingStart = (held, target, threadsBox) => {
  const band = landingBand(threadsBox);
  if (!band) return null;
  const room = band.bottom - band.top;
  const targetBox = shownBox(target);
  const last = target === held ? targetBox.bottom : targetBox.top;
  const candidates = [
    ...held.querySelectorAll(
      ":scope > *, :scope > .lf-thread-content > *, " +
        ".lf-thread-transcript .lf-msg .lf-msg-body > *, " +
        ".lf-thread-transcript .lf-msg .lf-msg-text > *",
    ),
    target,
  ]
    .filter((node) => node !== held)
    .map((node) => ({ node, box: shownBox(node) }))
    .filter(
      ({ node, box }) =>
        node === target ||
        (getComputedStyle(node).display !== "contents" &&
          box.height > 0 &&
          box.top <= last &&
          targetBox.bottom - box.top <= room),
    )
    .sort((a, b) => a.box.top - b.box.top);
  return candidates[0]?.node ?? null;
};

export function threadInput(node) {
  const held = node && closestAcross(node, SAYS_IN);
  return threadReplyInput(held);
}

const heldThreadOrSeat = () => focused() && closestAcross(focused(), SAYS_IN);
export const standingThread = () => {
  const held = heldThreadOrSeat();
  const box = threadReplyInput(held);
  return box ? { held, box } : null;
};
const backFromThread = (box) => threadReturns.get(box) ?? null;

// Where a box hands the user back, however they reached it. This once asked only for
// `.lf-thread` and the panel, so the two boxes outside the chrome — a thread seated
// on the page, and each thread on that seat — had no relation to return through. The climb
// is `heldThreadOrSeat`'s, the same relation contextual `c` uses when it names a thread.
//
// A seat holding no thread yet has no standing place of its own. A widget control that
// explicitly sends the user into that box can supply its own return through
// `landInThread`; a visit reached by Tab still falls through to the page's "let go".
// Otherwise the question is "can the user be put here", rather than a list of which two
// containers happen to be focusable — which is also why a seat that `reachScrollers` makes
// focusable, having grown a scrollbar and no focusable child, becomes a rung without anyone
// editing this: the question is the same one, and the answer moved.
function backFromBox() {
  const held = heldThreadOrSeat();
  if (held?.matches(THREAD)) return { target: held, line: "back to thread" };
  const route = backFromThread(focused());
  return route?.target?.isConnected ? route : null;
}
// Whether the box the user is typing in has somewhere to hand them back: the
// thread it belongs to, or the panel's list where it is the chrome's own box. The
// page's standing scope asks the same question, since a box with nowhere to go back to
// is a control the user is standing on, theirs to let go of.
export const boxHandsBack = () =>
  Boolean(backFromBox()) || Boolean(documentFocused()?.closest?.(".lf-thread-panel"));

// A box words are typed into takes character keys and the keys that edit it: Enter,
// deletion, caret movement, Home/End, and page movement, including their modified forms.
// Escape remains the box's to declare or pass on. What it declares is the way back out — to
// the thread a reply belongs to, so Esc then Enter round-trips, or to the list, so t/T walk
// on from where the backing-out started. Drafts are kept at every rung.
//
// A control the user is standing on rather than writing in keeps that rung without this
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
      // The thread the box belongs to, or the panel's list where it is the chrome's
      // own box. A page text box that is neither leaves the row dead and the page's rung
      // standing, which is the honest answer: nothing there to go back to.
      when: boxHandsBack,
      run: () => {
        const back = backFromBox();
        const panelList = documentFocused()
          ?.closest?.(".lf-thread-panel")
          ?.querySelector(".lf-threads");
        document.activeElement.blur();
        const target = back?.target ?? panelList;
        if (!target) return;
        if (!target.matches?.(THREAD)) return target.focus();
        standOnThread(target);
      },
    },
  ],
});

// Coming back out of a thread's box onto the thread, by Escape or by a send, is no
// arrival. A thread too tall to show whole is already on screen around the box, and
// landing its title would take the user away from the turn they were answering.
export function standOnThread(thread) {
  if (fitsWhole(thread)) return focusThread(thread);
  keepingPlace = true;
  try {
    focusThread(thread, { preventScroll: true });
  } finally {
    keepingPlace = false;
  }
}

// A thread's own keys, live wherever the user stands in one: the card, the message a
// click on its words focuses, the quote, a link in a reply. `r` settles the thread from any
// of them, since a control, a widget, or a text box that owns a letter is walked first.
// Enter replies or reopens only from the card, where no control inside has an Enter of its
// own to lose. The reopen button tells the two states apart; absent a thread, the reference
// describes the open state users first meet.
// The thread whose card the user stands on: an inline card root, or a panel thread's
// title once it is open. A closed title keeps Enter for itself, to open the thread.
const cardThread = () => {
  const thread = focusedThreadTarget();
  return thread?.localName === "details" && !thread.open ? null : thread;
};
const resolutionControl = (thread) =>
  thread?.querySelector(
    ":scope .lf-thread-meta-actions > .lf-resolve, " +
      ":scope .lf-thread-meta-actions > .lf-reopen, " +
      ":scope > .lf-thread-actions > .lf-reopen, " +
      ":scope > .lf-page-thread-resolved .lf-reopen",
  ) ?? null;

function prepareLanding({ held = null, box, route = null }) {
  if (
    route &&
    (!(route.target instanceof Element) ||
      typeof route.line !== "string" ||
      !route.line.trim())
  )
    throw new TypeError(
      "landInThread return route needs an element target and a non-empty line",
    );
  held ??= box && closestAcross(box, SAYS_IN);
  if (!held) return false;
  if (route && !held.hasAttribute("tabindex")) {
    threadReturns.set(box, route);
    box.addEventListener("blur", () => threadReturns.delete(box), {
      once: true,
    });
  }
  return { held, box };
}

export const retainPanelLanding = (source, panelIsOpen, threadsBox) =>
  retainUserIntent({ source, available: panelIsOpen, fallback: threadsBox });

// Landing belongs to the list, not to whatever moved the focus. The list already says
// which of its own edges cannot be stood on — `scroll-padding`, room for the focused
// card's edge — and every route that could reach a thread was scrolling it into that
// band for itself, so a route that did not scroll got nothing. A press does not: the
// browser focuses the card under the pointer and scrolls nothing, so a list nudged a
// dozen pixels leaves its first card two pixels past the top edge, which hides its top
// border and leaves the current card's quiet edge-and-surface cue incomplete.
// The routes that resolve a thread rather than press one — a page mark's comment note,
// the thread a resolve or a reopen hands the user on to — landed only by chance of
// having remembered the line.
//
// Thread focus is the shared arrival, so the landing hangs off it. Reply entry is
// different: `landIn` reveals only the writing area and leaves a visible box where
// the reader put it. The list does not turn that focus handoff into thread navigation.
// Explicit movement still belongs to `stepThread` at a walk's boundary (no focus
// change), `showThread` for a deliberate arrival, and `placeThreadEdge` for an edge
// placement. Those landings clear the list's band with the least movement.
//
// A press is the user's hand, and it may be the start of a drag across the comment's
// own words. Focus lands on the way down, so scrolling there takes the words out from
// under the pointer and the selection runs on past where they stopped — measured at
// three times the run the user drew. A press therefore holds its landing until the
// hand comes up, and gives it up altogether where the press was a drag for the
// thread's own words: the question `offer` already asks of a click, read the same way,
// since the selection's focus end is the character the button came up on.
//
// The hand comes up before the press's click, which is where a deliberate placement
// begins — a quote jumping to its passage, a travel centring a widget in a reply. So
// the order holds without a word between them: the landing is a correction under the
// gesture, and whatever the gesture then asks for is later and wins.
//
// What the press lands is where it left the user, which is not the same question as
// which thread the focus moved to. A press on the thread the user is already in
// moves no focus and so was heard as nothing at all — and that is the user's own
// gesture: they are standing in a comment, the list carries a little, and they press
// the card to bring it back. Asking the completed gesture instead of the focus event
// costs a variable rather than buying one, and the walk's own end-of-clamp press is
// the same shape one scope out.
const standing = () => focused()?.closest?.(".lf-thread");
let keepingPlace = false;
const land = (thread, behavior, threadsBox, block) => {
  if (!thread || !threadsBox.contains(thread)) return;
  // A fold still holds the room it is giving back, so a landing measured now aims past
  // where the thread will stand, and the fold's place hold then writes over a smooth one:
  // resolving a long thread left the next one's title above the list. Land once the fold
  // has ended and its removal painted, if the user is still standing there and has
  // made no newer gesture.
  if (hasFolding(threadsBox)) {
    const mayLand = retainUserIntent({
      source: thread,
      available: () => thread.isConnected,
    });
    void whenFolded(threadsBox)
      .then(whenDocumentPresented)
      .catch(() => {})
      .then(() => {
        if (mayLand() && thread.contains(focused()))
          land(thread, behavior, threadsBox, block);
      });
    return;
  }
  scrollThreadIntoView(thread, focused(), behavior, block);
};
// A key arriving on the title of a thread too tall to show whole shows it from its start:
// the nearest edge put the title at the list's foot with none of the thread under it.
const arrivalBlock = (thread) =>
  focused()?.matches?.(".lf-thread-summary") && !fitsWhole(thread)
    ? "start"
    : "nearest";
// The primary pointer owns the provisional landing until that same gesture ends. A
// cancellation means the browser took it for something else — commonly a touch scroll —
// so release the hold without undoing the gesture by landing the thread.
// Mounted from leaf.js.
export function wireThreadLanding(threadsBox) {
  let pressedPointer = null;
  const finishPress = (event, shouldLand) => {
    if (event.pointerId !== pressedPointer?.id) return;
    const pressedThread = pressedPointer.thread;
    pressedPointer = null;
    if (!shouldLand) return;
    const thread = standing() ?? pressedThread;
    if (thread && !reachedForWords(thread)) {
      if (!thread.contains(focused())) focusThread(thread, { preventScroll: true });
      // The press's click may reflow the list and takes its hold from this geometry.
      land(thread, "instant", threadsBox);
    }
  };
  addEventListener("pointerup", (event) => finishPress(event, true), true);
  addEventListener("pointercancel", (event) => finishPress(event, false), true);
  threadsBox.addEventListener("pointerdown", (event) => {
    if (event.isPrimary)
      pressedPointer = {
        id: event.pointerId,
        thread: event.target.closest?.(".lf-thread") ?? null,
      };
  });
  threadsBox.addEventListener("focusin", () => {
    if (pressedPointer !== null || keepingPlace) return;
    const thread = standing();
    // Native focus and reply entry reveal their own writing area. Re-landing the
    // thread here would turn that focus move into a second navigation gesture.
    if (thread && threadReplyInput(thread) !== focused())
      land(thread, undefined, threadsBox, arrivalBlock(thread));
  });
}

// Shown, not merely standing: a card the narrowing hid keeps its node (thread-list.js),
// and a destination in one is as unreachable as a destination with no node at all.
const listNode = (id, threadsBox, preferMessage = false) => {
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
async function showThreadNow(id, focus, revealThread, threadsBox, mayArrive) {
  // A direct arrival owns the target's one transition cue. Remove a retained arrival
  // animation before an asynchronous reveal gives the browser a frame to start it.
  threadsBox
    .querySelector(
      `.lf-thread[data-id="${CSS.escape(id)}"], .lf-msg[data-mid="${CSS.escape(id)}"]`,
    )
    ?.classList.toggle("grow", false);
  threadsBox.revealNavigation(id);
  let node = listNode(id, threadsBox, focus === "message");
  const going = node?.closest(".lf-going");
  if (going) {
    finishFold(going);
    const revealed = revealThread(id);
    if (!revealed) return null;
    await revealed;
    if (!mayArrive()) return null;
    node = listNode(id, threadsBox, focus === "message");
  } else if (!node) {
    const revealed = revealThread(id);
    if (!revealed) return null;
    await revealed;
    if (!mayArrive()) return null;
    node = listNode(id, threadsBox, focus === "message");
  }
  threadsBox.revealNavigation(id);
  node = listNode(id, threadsBox, focus === "message");
  if (!node || !mayArrive()) return null;
  if (node.closest(".lf-summary-originals[hidden]")) {
    await reveal(node, mayArrive);
    if (!mayArrive()) return null;
  }
  // A render still in flight holds the list's place as it finishes, and that write
  // cancels a smooth landing already under way: a thread sent from the panel's foot was
  // left below it. Land on the list the render leaves.
  await whenDocumentPresented().catch(() => {});
  node = listNode(id, threadsBox, focus === "message");
  if (!node || !mayArrive()) return null;
  const thread = node.closest(".lf-thread");
  if (focus) {
    const destination =
      node === thread ? threadFocusDestination(thread, { focus }) : node;
    mayArrive.handoff(() => {
      if (destination === thread) focusThread(thread, { preventScroll: true });
      else destination.focus({ preventScroll: true });
    });
  }
  const directThread = node === thread && thread.contains(focused());
  // A direct arrival aims at the reply area wherever the user stands in the thread; a
  // long thread whose reply row is pinned aims at the thread's end, which the row
  // stands over.
  const aim = directThread
    ? landingTarget(thread, threadReplyInput(thread) ?? focused())
    : { node };
  const target = aim.node ?? thread;
  const long = directThread && (target !== thread || aim.block === "end");
  const start = long ? threadLandingStart(thread, target, threadsBox) : null;
  (start ?? target).scrollIntoView({
    behavior: scrollBehavior(),
    // A long thread begins at the clean content boundary chosen above. A short card
    // is context in full; a requested message keeps the least-moving direct route.
    block: start
      ? "start"
      : long
        ? (aim.block ?? "start")
        : target === thread
          ? "center"
          : "nearest",
  });
  const revealed =
    (aim.block === "end" && thread.querySelector(":scope > .lf-thread-reply")) ||
    target;
  revealed.classList.toggle("grow", false);
  revealed.classList.toggle("flash", true);
  setTimeout(() => revealed.classList.toggle("flash", false), 1300);
  return focus ? focused() : node;
}

// The open panel's side of standing at a target: the list's one expanded thread becomes
// the thread about where the user stands, as the margin card does with the panel shut.
// It accompanies rather than arrives, so it takes no focus, draws no flash, widens no
// narrowing that hides the thread, and moves the list only as far as shows it. `ids` are
// the target's threads: one of them already expanded is where the user is on that
// target, perhaps mid-reply, so it stays; otherwise the first the list shows expands.
const listedThreads = (ids, threadsBox) =>
  ids
    .map((id) => listNode(id, threadsBox))
    .filter((node) => node?.matches(".lf-thread") && !node.closest(".lf-going"));
export const accompaniedThread = (ids, threadsBox) =>
  listedThreads(ids, threadsBox).find((node) => node.open) ?? null;
export function accompanyThread(ids, threadsBox) {
  const thread =
    accompaniedThread(ids, threadsBox) ?? listedThreads(ids, threadsBox)[0];
  if (!thread) return;
  threadsBox.revealNavigation(thread.dataset.id);
  const room = landingBand(threadsBox);
  const fits = !room || shownBox(thread).height <= room.bottom - room.top;
  thread.scrollIntoView({
    behavior: scrollBehavior(),
    block: fits ? "nearest" : "start",
  });
}

export function createThreadLanding({
  setPanel,
  revealThread,
  threadsBox,
  cardTarget,
}) {
  const landIn = (destination) => {
    const prepared = prepareLanding(destination);
    if (!prepared) return false;
    const { box } = prepared;
    box.lfRevealReply?.();
    // Entering a reply is a focus move, not a trip to its thread or passage.
    // Reveal only the writing area; an already visible box leaves every scroller
    // where the reader put it, including the transcript inside a margin card.
    bringBackSurfaceOf(box);
    box.focus({ preventScroll: true });
    const shown = shownBox(box);
    const visible = seenRect(box, new Map());
    if (
      !visible ||
      visible.top > shown.top ||
      visible.bottom < shown.bottom ||
      visible.left > shown.left ||
      visible.right < shown.right
    )
      box.scrollIntoView({
        block: "nearest",
        inline: "nearest",
        behavior: "instant",
      });
    return true;
  };
  const landInThread = (box, route = null) => landIn({ box, route });
  // Where a sent reply or first comment leaves the user: out of the box, standing on the
  // thread, or, for a thread in the margin card, on the element the thread is about, with
  // the card still up (`cardTarget`, the card's own step out). A user who sends is
  // usually done with the thread until the agent answers, so they move on from there
  // without Escaping out of the box first.
  const landSent = (thread) => {
    const target = cardTarget(thread);
    if (target) focusDestination(target);
    else standOnThread(thread);
  };
  const showThread = (
    id,
    {
      focus = "reply",
      intent = retainUserIntent({
        source: focused(),
        available: () => threadsBox.isConnected,
        fallback: threadsBox,
      }),
    } = {},
  ) => {
    if (!intent.handoff(() => setPanel(true))) return Promise.resolve(null);
    const ready = showThreadNow(id, focus, revealThread, threadsBox, intent);
    // Pointer and keyboard routes deliberately discard this ticket. The thread
    // coordinator reports its one failure; the landing result keeps that rejection out
    // of both discarded event-handler promises and callers that continue a delivery.
    return ready.then(
      (arrived) => arrived,
      () => null,
    );
  };
  return {
    landIn,
    landInThread,
    landSent,
    showThread,
    accompaniedThread: (ids) => accompaniedThread(ids, threadsBox),
    accompanyThread: (ids) => accompanyThread(ids, threadsBox),
  };
}

/** Declare a thread's own keys against the landing the page is using.
 *
 * Separate from constructing that landing, because they are separate acts: a second
 * landing owner — one a test builds to hold a reveal open — is another way of landing,
 * not another set of keys, and declaring from the constructor would let it quietly take
 * the page's. */
export function declareThreadKeys(landIn, narrowing) {
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
          resolutionControl(cardThread())?.matches(".lf-reopen")
            ? "Reopen it"
            : "Write a reply",
        line: () =>
          resolutionControl(cardThread())?.matches(".lf-reopen") ? "reopen" : "reply",
        // A panel title's bar keeps its room for resolution; the reply box under it
        // already names its key, and the reference lists this row.
        lineWhen: () => !focused()?.matches?.(".lf-thread-summary"),
        when: () =>
          Boolean(threadInput(cardThread())) ||
          resolutionControl(cardThread())?.matches(
            '.lf-reopen:not(:disabled, [aria-disabled="true"])',
          ),
        // Find the thread's own compose row rather than the first text box: a message may
        // contain a widget with an editor of its own before the reply box in DOM order.
        run: () => {
          const thread = cardThread();
          const reopen = resolutionControl(thread)?.matches(".lf-reopen")
            ? resolutionControl(thread)
            : null;
          if (reopen) reopen.click();
          else landIn({ held: thread, box: threadInput(thread) });
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
        lineWhen: () => !narrowing.threadSearchActive(),
        when: () =>
          resolutionControl(heldThread())?.matches(
            ':not(:disabled, [aria-disabled="true"])',
          ),
        run: () => resolutionControl(heldThread()).click(),
      },
    ],
  });
}
