/* Landing the user in a thread: which box a reply lands in, and where focus goes
   coming back out of one.

   `backFromBox` and `standingThread` climb the same thread relation, so
   “comment on the thread” going in and “back to thread” coming out name one element. It
   answers for every arrival — a keyboard command, a Tab, a pointer — because a box's way
   out is the thread it belongs to whichever of them put the user in it. A page-owned
   first-message seat has no standing place of its own; a widget control that explicitly
   enters its box supplies the caller-owned return target through `landInThread`.
   Sending from a conversation's own box leaves focus on its card (`landSent`); the
   floating panel's field, which stands for the thread open above it, keeps focus for
   the next turn. Returning to the page is a separate navigation gesture. */
import { alreadyShown, fitsWhole, scrollIntoView } from "../landing-scroll.js";
import {
  focusDestination,
  focused,
  takesLetters,
  whenLeft,
  deepFocus,
} from "../focus.js";
import { bringBackSurfaceOf } from "../off-flow.js";
import { closestAcross } from "../passages.js";
import { SAYS_IN, THREAD } from "./selectors.js";
import { pageScope } from "../keyboard/register.js";
import { TEXT_ENTRY } from "../keyboard/text-entry.js";
import { dismissReplyAt, replyDraftContext } from "./replies.js";
import { threadList } from "./state.js";
import {
  focusedThreadTarget,
  focusThread,
  heldThread,
  threadReplyInput,
  threadPart,
  wholeThread,
} from "./focus.js";

export { scrollThreadIntoView } from "./reply-landing.js";
const threadReturns = new WeakMap();

export function threadInput(node) {
  const held = node && closestAcross(node, SAYS_IN);
  return threadReplyInput(held);
}

const heldThreadOrSeat = () => focused() && closestAcross(focused(), SAYS_IN);
// The thread the user writes in from where they stand, whole where it is drawn in
// pieces (focus.js, `wholeThread`), and its box.
export const standingThread = () => {
  const held = heldThreadOrSeat();
  const box = threadReplyInput(held);
  return box ? { held: wholeThread(held), box } : null;
};
const backFromThread = (box) => threadReturns.get(box) ?? null;

// Where a box hands the user back, however they reached it. The climb is
// `heldThreadOrSeat`'s, the same relation contextual `c` uses when it names a thread.
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
// hand back to is a control the user stands on, theirs to let go of.
export const leavesBox = () => inBox() && boxHandsBack();

// A box words are typed into takes character keys and the keys that edit it: Enter,
// deletion, caret movement, Home/End, and page movement, including their modified forms.
// Escape leaves the reply's whole composition row, including its Send control, through
// this declared command, after any nearer interaction has had its own Escape. It is
// the way back out to the thread a reply belongs to, so Esc then Enter round-trips.
// Drafts are kept at every rung.
//
// A control the user is standing on rather than writing in keeps that rung without this
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
      description: "Leave the box, keeping what is typed",
      title: () => backFromBox()?.line ?? "back",
      // The thread the box belongs to. A page text box that is not in one leaves the
      // row dead and the page's rung in place, which is the honest answer: nothing
      // there to go back to.
      when: leavesBox,
      run: () => {
        const back = backFromBox();
        dismissReplyAt(focused());
        /** @type {HTMLElement | null} */ (deepFocus())?.blur();
        const target = back?.target;
        if (!target) return;
        if (!target.matches?.(THREAD)) {
          focusDestination(target, "return");
          scrollIntoView(target, { block: "nearest" });
          return;
        }
        standOnThread(target);
      },
    },
  ],
});

// Coming back out of a thread's box onto the thread, by Escape or by a send, is no
// arrival. A thread too tall to show whole and already shown stands around the box, and
// landing its title would take the user away from the turn they were answering, so it
// is a `return` that leaves it where it is. One that fits, or one the user has
// scrolled out of view since, is a `move`, brought into view. One the user already
// sees stays where it is: the box they left stands beside the gesture, and a landing
// would carry it by the room the thread's focus ring asks at its foot.
function standOnThread(thread) {
  const shown = alreadyShown(thread);
  if (!fitsWhole(thread) && shown) {
    focusThread(thread, "return");
    return;
  }
  focusThread(thread, "move");
  if (!shown) scrollIntoView(thread, { block: "nearest" });
}

// A thread's own keys, live wherever the user stands in one: the card, the message a
// click on its words focuses, the quote, a link in a reply. `r` settles the thread from any
// of them, since a control, a widget, or a text box that owns a letter is walked first.
// Enter replies or reopens only from the card, where no control inside has an Enter of its
// own to lose. The reopen button tells the two states apart; absent a thread, the reference
// describes the open state users first meet.
// The thread whose card the user stands on.
const cardThread = () => focusedThreadTarget();
// Settlement belongs to the thread, wherever its view places that control.
const resolutionControl = (thread) =>
  thread ? threadPart(thread, "settlement") : null;

// A box a presentation declares as its thread's reply may stand outside the thread
// (focus.js, `threadPart`), so landing in one asks for the box alone.
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
  const landIn = (destination) => {
    const prepared = prepareLanding(destination);
    if (!prepared) return false;
    const { box } = prepared;
    // Entering a reply is a focus move, not a trip to its thread or passage.
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
  const landInThread = (box, route = null) => landIn({ box, route });
  // Sending ends text entry while keeping the user in the conversation. Every surface
  // uses its thread's focus stop; leaving the card belongs to navigation, not Send.
  const landSent = standOnThread;
  return { landIn, landInThread, landSent };
}

/** Declare a thread's own keys against the landing the page is using.
 *
 * Separate from constructing that landing, because they are separate acts: a second
 * landing owner — one a test builds to hold a reveal open — is another way of landing,
 * not another set of keys, and declaring from the constructor would let it quietly take
 * the page's. */
export function declareThreadKeys(landIn) {
  pageScope("thread", {
    title: "In a thread",
    root: focused,
    when: () => threadList().length > 0,
    at: () => Boolean(heldThread()),
    rows: [
      {
        id: "thread.primary",
        touch: false,
        keys: ["Enter"],
        description: () =>
          resolutionControl(cardThread())?.matches(".lf-reopen")
            ? "Reopen it"
            : "Write a reply",
        title: () =>
          resolutionControl(cardThread())?.matches(".lf-reopen") ? "reopen" : "reply",
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
        touch: false,
        keys: ["r"],
        description: () =>
          resolutionControl(heldThread())?.matches(".lf-reopen")
            ? "Reopen it"
            : "Resolve it",
        title: () =>
          resolutionControl(heldThread())?.matches(".lf-reopen") ? "reopen" : "resolve",
        when: () =>
          resolutionControl(heldThread())?.matches(
            ':not(:disabled, [aria-disabled="true"])',
          ),
        run: () => resolutionControl(heldThread()).click(),
      },
    ],
  });
}
