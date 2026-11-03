/* Landing the user in a thread: which box a reply lands in, and where focus goes
   coming back out of one.

   `backFromBox` and `currentLocationThread` climb the same thread relation, so
   “comment on the thread” going in and “back to thread” coming out name one element. It
   answers for every arrival — a keyboard command, a Tab, a pointer — because a box's way
   out is the thread it belongs to whichever of them put the user in it. A page-owned
   first-message seat has no current location of its own; a widget control that explicitly
   enters its box supplies the caller-owned return target through `landInThread`.
   A reply's box keeps the caret through its send (replies.js); a first message, or a
   rewrite, whose box goes with the send leaves focus on its thread's card or title
   (`landSent`). Returning to the page is a separate navigation gesture. */
import { alreadyShown, fitsWhole, scrollIntoView } from "../landing-scroll.js";
import { seenRect } from "../geometry.js";
import {
  focusDestination,
  focused,
  takesLetters,
  whenLeft,
  blurFocused,
} from "../focus.js";
import { bringBackSurfaceOf } from "../off-flow.js";
import { closestAcross } from "../passages.js";
import { SAYS_IN, THREAD, threadPart, wholeThread } from "./selectors.js";
import { pageScope } from "../keyboard/register.js";
import { TEXT_ENTRY } from "../keyboard/text-entry.js";
import { dismissReplyAt, replyDraftContext } from "./replies.js";
import { copyTrigger } from "../copy-control.js";
import { threadList } from "./state.js";
import { focusedThreadTarget, focusThread, threadReplyInput } from "./focus.js";

export { scrollThreadIntoView } from "./reply-landing.js";
/** @typedef {{target: Element, line: string}} ReturnRoute */
/** @typedef {{held?: Element | null, box: Element | null, route?: ReturnRoute | null}} ThreadLanding */
/** @type {WeakMap<Element, ReturnRoute>} */
const threadReturns = new WeakMap();

/** @param {Element | null} node */
export function threadInput(node) {
  const held = node && closestAcross(node, SAYS_IN);
  return threadReplyInput(held);
}

const heldThreadOrSeat = () => focused() && closestAcross(focused(), SAYS_IN);
// The thread the user writes in from where they are, whole where it is drawn in
// pieces (selectors.js, `wholeThread`), and its box.
export const currentLocationThread = () => {
  const held = heldThreadOrSeat();
  const box = threadReplyInput(held);
  return held && box ? { held: wholeThread(held), box } : null;
};
/** @param {Element | null} box */
const backFromThread = (box) => (box ? (threadReturns.get(box) ?? null) : null);

// Where a box hands the user back, however they reached it. The climb is
// `heldThreadOrSeat`'s, the same relation contextual `c` uses when it names a thread.
//
// A seat holding no thread yet has no current location of its own. A widget control that
// explicitly sends the user into that box can supply its own return through
// `landInThread`; a visit reached by Tab still falls through to the page's "let go".
// Otherwise the question is "can the user be put here", rather than a list of which two
// containers happen to be focusable — which is also why a seat that `reachScrollers` makes
// focusable, having grown a scrollbar and no focusable child, becomes a rung without anyone
// editing this: the question is the same one, and the answer moved.
function backFromBox() {
  const held = heldThreadOrSeat();
  if (held?.matches(THREAD))
    return { target: wholeThread(held), line: "back to thread" };
  const route = backFromThread(focused());
  return route?.target?.isConnected ? route : null;
}
// Whether the box the user is typing in has somewhere to hand them back: the
// thread it belongs to.
const boxHandsBack = () => Boolean(backFromBox());
// The box, or the reply's composition row around it, which takes its Send control too.
const inBox = () => takesLetters(focused()) || replyDraftContext(focused()) !== null;
// Whether Escape here leaves a box for the place it hands back to. The page's let-go
// defers to it from the box and from every control in its row; a box with nowhere to
// hand back to is a control the user is on, theirs to let go of.
export const leavesBox = () => inBox() && boxHandsBack();

// A box words are typed into takes character keys and the keys that edit it: Enter,
// deletion, caret movement, Home/End, and page movement, including their modified forms.
// Escape leaves the reply's whole composition row, including its Send control, through
// this declared command, after any nearer interaction has had its own Escape. It is
// the way back out to the thread a reply belongs to, so Esc then Enter round-navigation steps.
// Drafts are kept at every rung.
//
// A control the user is on rather than writing in keeps that rung without this
// scope carrying a second branch for it: the scope claims the keys a box takes and leaves
// every other press — c, the walks, the versions, the reference — to the scopes behind it.
pageScope("text entry", {
  title: "In a text box",
  root: focused,
  at: inBox,
  claims: (binding) => takesLetters(focused()) && TEXT_ENTRY(binding),
  rows: [
    {
      id: "text.leave",
      touch: false,
      keys: ["Escape"],
      description: "Keeps what is typed",
      title: () => backFromBox()?.line ?? "back",
      // The thread the box belongs to. A page text box that is not in one leaves the
      // row dead and the page's rung in place, which is the honest answer: nothing
      // there to go back to.
      when: leavesBox,
      run: () => {
        const back = backFromBox();
        dismissReplyAt(focused());
        blurFocused();
        const target = back?.target;
        if (!target) return;
        if (!target.matches?.(THREAD)) {
          focusDestination(target, "return");
          scrollIntoView(target, { block: "nearest" });
          return;
        }
        returnToThread(target);
      },
    },
  ],
});

// Coming back out of a thread's box onto the thread, by Escape or by a send, is no
// arrival. A thread too tall to show whole and already shown stands around the box, and
// landing its title would take the user away from the turn they were answering, so it
// is a `return` that leaves it where it is. One that fits, or one the user has
// scrolled out of view since, is a `move`, brought into view. While the box the user
// left still stands in front of them, nothing scrolls: it stands beside the gesture,
// and a landing would carry it, by the room the thread's focus ring asks at its foot or
// by bringing back a head they scrolled above the window. A box the send gave up, as a
// seat's does to the thread it starts, leaves nothing there to carry.
/** @param {Element} thread */
function returnToThread(thread) {
  const shown = alreadyShown(thread);
  if (!fitsWhole(thread) && shown) {
    focusThread(thread, "return");
    return;
  }
  focusThread(thread, "move");
  const box = threadReplyInput(thread);
  if (!shown && !(box && seenRect(box, new Map())))
    scrollIntoView(thread, { block: "nearest" });
}

// The thread whose card the user is on.
const cardThread = () => focusedThreadTarget();
// Settlement belongs to the thread, wherever its view places that control.
/** @param {Element | null} thread */
const resolutionControl = (thread) =>
  thread ? threadPart(thread, "settlement") : null;

// The Copy of the message the user is in, by focus or by the caret a click on its words
// leaves, else of the thread's latest message.
/** @param {Node | null} node */
const messageAt = (node) =>
  (node instanceof Element ? node : node?.parentElement)?.closest(".lf-msg") ?? null;
/** @param {Element | null} thread */
function messageCopy(thread) {
  if (!thread) return null;
  const caret = getSelection()?.anchorNode ?? null;
  const message =
    messageAt(focused()) ??
    (thread.contains(caret) ? messageAt(caret) : null) ??
    [...thread.querySelectorAll(".lf-msg")].at(-1);
  /** @type {HTMLElementTagNameMap["wa-copy-button"] | null | undefined} */
  const copy = message?.querySelector(":scope > .lf-msg-head .lf-msg-copy");
  return copyTrigger(copy);
}

// A box a presentation declares as its thread's reply may stand outside the thread
// (selectors.js, `threadPart`), so landing in one asks for the box alone.
/** @param {ThreadLanding} destination */
function prepareLanding({ held = null, box, route = null }) {
  if (!box) return false;
  held ??= closestAcross(box, SAYS_IN);
  if (route && held && !held.hasAttribute("tabindex")) {
    threadReturns.set(box, route);
    whenLeft(box, () => threadReturns.delete(box));
  }
  return { held, box };
}

export function createThreadLanding() {
  /** @param {ThreadLanding} destination */
  const landIn = (destination) => {
    const prepared = prepareLanding(destination);
    if (!prepared) return false;
    const { box } = prepared;
    // Entering a reply is a focus move, not a navigation step to its thread or passage.
    // Reveal only the writing area: a box already shown (landing-scroll.js,
    // `alreadyShown`) leaves every scroller where the reader put it, including the
    // transcript inside a margin card, however tall the box.
    bringBackSurfaceOf(box);
    focusDestination(box, "move");
    if (!alreadyShown(box))
      scrollIntoView(box, {
        block: "nearest",
        behavior: "instant",
      });
    return true;
  };
  /** @param {Element} box @param {ReturnRoute | null} route */
  const landInThread = (box, route = null) => landIn({ box, route });
  // A send whose box goes, a first message's or a rewrite's, ends text entry while
  // keeping the user in the conversation, on its thread's focus stop; leaving the card
  // belongs to navigation, not Send.
  const landSent = returnToThread;
  return { landIn, landInThread, landSent };
}

/** Declare a thread's own keys against the landing the page is using, and the reading
 * of the thread the user is at (destination.js, `threadHere`).
 *
 * Separate from constructing that landing, because they are separate acts: a second
 * landing owner — one a test builds to hold a reveal open — is another way of landing,
 * not another set of keys, and declaring from the constructor would let it quietly take
 * the page's.
 *
 * The keys are live wherever the user is at a thread: in it, on the card, the message a
 * click on its words focuses, the quote, a link in a reply; and on the element whose
 * thread a card shows beside it, which is one place with it, as `c` there continues that
 * thread. `r` settles the thread from any of them, since a control, a widget, or a text
 * box that owns a letter is walked first. Enter replies only from the card, where no
 * control inside has an Enter of its own to lose; where a resolved thread draws no reply
 * box, as a resolved card doesn't, it reopens the thread into the box instead. The
 * platform's copy key with nothing selected presses Copy on the message the user is in,
 * else on the thread's latest, the keyboard's route to what Copy gives a pointer; with
 * words selected it keeps the browser's copy. Absent a thread, the reference describes
 * the open state users first meet. */
/** @param {ReturnType<typeof createThreadLanding>["landIn"]} landIn
 * @param {() => Element | null} threadHere */
export function declareThreadKeys(landIn, threadHere) {
  pageScope("thread", {
    title: "In a thread",
    root: focused,
    when: () => threadList().length > 0,
    at: () => Boolean(threadHere()),
    rows: [
      {
        id: "thread.primary",
        touch: false,
        keys: ["Enter"],
        title: () =>
          !threadInput(cardThread()) &&
          resolutionControl(cardThread())?.matches(".lf-reopen")
            ? "reopen"
            : "reply",
        // Find the thread's own compose row rather than a widget editor inside it.
        get run() {
          const thread = cardThread();
          const box = threadInput(thread);
          if (box) return () => landIn({ held: thread, box });
          const control = resolutionControl(thread);
          return control?.matches('.lf-reopen:not(:disabled, [aria-disabled="true"])')
            ? () => control.click()
            : undefined;
        },
      },
      {
        id: "thread.resolution.toggle",
        touch: false,
        keys: ["r"],
        title: () =>
          resolutionControl(threadHere())?.matches(".lf-reopen") ? "reopen" : "resolve",
        get run() {
          const control = resolutionControl(threadHere());
          return control?.matches(':not(:disabled, [aria-disabled="true"])')
            ? () => control.click()
            : undefined;
        },
      },
      {
        id: "message.copy",
        touch: false,
        keys: ["Mod+c"],
        title: "copy message as Markdown",
        get run() {
          const trigger = messageCopy(threadHere());
          return trigger && getSelection()?.isCollapsed
            ? () => trigger.click()
            : undefined;
        },
      },
    ],
  });
}
