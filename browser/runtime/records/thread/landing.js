/* Landing the user in a thread: which box a reply lands in, and where focus goes
   coming back out of one.

   `backFrom` and `currentLocationThread` climb the same thread relation, so
   “comment on the thread” going in and “back to thread” coming out name one element. It
   answers for every arrival — a keyboard command, a Tab, a pointer — because a box's way
   out is the thread it belongs to whichever of them put the user in it. A box standing
   in no drawn thread has none to hand back to; a widget control that explicitly enters
   it supplies the caller-owned return target through `landInThread`.

   Send leaves the box by that same way out, onto its thread (`landSent`), whichever
   box sent and whichever control sent it: a reply's box in a margin card, a seat or
   the floating panel's field, a first comment's box, the panel's, a seat's or a
   passage's, which the send gives up for the thread it starts, and a rewrite's, by
   Save (message-edit.js). The user stands on the thread's card or seat, which wears
   the focus ring, or the panel's view, which wears none (floating-panel.css), never in
   the box and never on the page, so their next key acts there: Escape closes a card,
   `t`, `m`, `j` and `d` walk, `r` resolves, and `c` or Enter opens the box again for a
   follow-up. The user chose this over keeping the caret in the box for a quick
   follow-up: a walk key pressed just after Send is far more common than words typed
   on, and in the box it types a letter instead. Returning to the page is a separate
   navigation gesture. */
import { fitsWhole, scrollIntoView } from "../../readings/landing-scroll.js";
import { seenRect } from "../../dom/geometry.js";
import {
  focusDestination,
  focused,
  takesLetters,
  whenLeft,
  blurFocused,
} from "../../dom/focus.js";
import { bringBackSurfaceOf } from "../../readings/off-flow.js";
import { THREAD, drawnThreadId, threadPart, wholeThread } from "./selectors.js";
import { pageScope } from "../../dom/keyboard/register.js";
import { TEXT_ENTRY } from "../../dom/keyboard/text-entry.js";
import { beginReplyAt, dismissReplyAt, replyDraftContext } from "./replies.js";
import { copyTrigger } from "../../transport/copy-control.js";
import { closestAcross, under } from "../../lib/shadow-tree.js";
import { userCaret } from "../../dom/native-selection.js";
import { threadList } from "./state.js";
import {
  focusedThreadTarget,
  focusThread,
  heldThread,
  threadIn,
  threadReplyInput,
} from "./focus.js";

export { scrollThreadIntoView } from "./reply-landing.js";
/** @typedef {{target: Element, line: string}} ReturnRoute */
/** @typedef {{held?: Element | null, box: Element | null, route?: ReturnRoute | null}} ThreadLanding */
/** @type {WeakMap<Element, ReturnRoute>} */
const threadReturns = new WeakMap();

/** @param {Element | null} node */
export const threadInput = (node) => threadReplyInput(threadIn(node));

// The thread the user writes in from where they are, whole where it is drawn in
// pieces (selectors.js, `wholeThread`), and its box.
export const currentLocationThread = () => {
  const held = heldThread();
  const box = threadReplyInput(held);
  return held && box ? { held: wholeThread(held), box } : null;
};
/** @param {Element | null} box */
const backFromThread = (box) => (box ? (threadReturns.get(box) ?? null) : null);

// Where a box hands the user back, however they reached it. The climb is
// `heldThread`'s, the same relation contextual `c` uses when it names a thread. A box
// standing outside any drawn thread hands back along the route the control that sent
// the user into it supplied (`landInThread`); a visit reached by Tab still falls
// through to the page's "let go".
/** @param {Element | null} box @returns {ReturnRoute | null} */
function backFrom(box) {
  const held = threadIn(box);
  if (held) return { target: wholeThread(held), line: "back to thread" };
  const route = backFromThread(box);
  return route?.target?.isConnected ? route : null;
}
const backFromBox = () => backFrom(focused());
// Put the user where a box hands them back: its thread, or the route's target.
/** @param {ReturnRoute} back */
function goBack({ target }) {
  if (!target.matches(THREAD)) {
    focusDestination(target, "return");
    scrollIntoView(target, { block: "nearest" });
    return;
  }
  returnToThread(target);
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
        if (back) goBack(back);
      },
    },
  ],
});

// Coming back out of a thread's box onto the thread, by Escape or by a send, is no
// arrival but a `return`, which previews nothing (annotations/preview.js). A thread too tall to show
// whole, some of which is in front of the user (dom/geometry.js, `seenRect`), stands around
// the box, and landing its title would take the user away from the turn they were
// answering, so it is left where it is. One that fits, or one the user has scrolled out
// of view since, is brought into view where it is not already shown. While the box the user left still
// stands in front of them, nothing scrolls: it stands beside the gesture, and a landing
// would carry it, by the room the thread's focus ring asks at its foot or by bringing
// back a head they scrolled above the window. A box the send gave up, as a seat's does
// to the thread it starts, leaves nothing there to carry.
/** @param {Element} thread */
function returnToThread(thread) {
  focusThread(thread, "return");
  if (!fitsWhole(thread) && seenRect(thread, new Map())) return;
  const box = threadReplyInput(thread);
  if (!(box && seenRect(box, new Map()))) scrollIntoView(thread, { block: "nearest" });
}

// Send ends text entry and keeps the user in the conversation (the header): from `node`,
// the box sent from or the thread a send started, it hands them back as Escape from the
// box does, keeping the draft's session, which the send's acceptance ends
// (replies.js). Leaving the card belongs to navigation, not Send.
/** @param {Element} node */
export function landSent(node) {
  const back = backFrom(node);
  if (back) goBack(back);
}

// The thread whose card the user is on.
const cardThread = () => focusedThreadTarget();
// Settlement belongs to the thread, wherever its view places that control.
/** @param {Element | null} thread */
const resolutionControl = (thread) =>
  thread ? threadPart(thread, "settlement") : null;
// So does the press that moves it between its card and the floating panel.
/** @param {Element | null} thread */
const movingControl = (thread) => (thread ? threadPart(thread, "move") : null);

// The message the user is in, by focus or by the caret a click on its words leaves
// (`userCaret`), else the one `otherwise` picks. The messages stand in the whole of
// the thread (selectors.js, `wholeThread`), apart from controls a view draws on its
// own lines, as the panel's view draws Resolve on its head.
/** @param {Element | null} node */
const messageAt = (node) => closestAcross(node, ".lf-msg");
/** @param {Element | null} thread
 * @param {(whole: Element) => Element | null | undefined} otherwise */
function messageIn(thread, otherwise) {
  if (!thread) return null;
  const whole = wholeThread(thread);
  const caret = userCaret()?.element ?? null;
  return (
    messageAt(focused()) ??
    (under(caret, whole) ? messageAt(caret) : null) ??
    otherwise(whole)
  );
}
// A message's copy control of `kind` (messages.js): `copy` or `link`.
/** @param {Element | null | undefined} message @param {"copy" | "link"} kind */
function messageControl(message, kind) {
  /** @type {HTMLElementTagNameMap["wa-copy-button"] | null | undefined} */
  const control = message?.querySelector(`:scope > .lf-msg-head .lf-msg-${kind}`);
  return copyTrigger(control);
}
// The Copy of the message the user is in, else of the thread's latest message.
/** @param {Element | null} thread */
const messageCopy = (thread) =>
  messageControl(
    messageIn(thread, (whole) => [...whole.querySelectorAll(".lf-msg")].at(-1)),
    "copy",
  );
// The Copy link of the message the user is in, else of the thread's opening message,
// whose link is the thread's.
/** @param {Element | null} thread */
const messageLinkCopy = (thread) =>
  messageControl(
    messageIn(thread, (whole) =>
      whole.querySelector(
        `.lf-msg[data-lf-event="${CSS.escape(drawnThreadId(whole) ?? "")}"]`,
      ),
    ),
    "link",
  );

// A box a presentation declares as its thread's reply may stand outside the thread
// (selectors.js, `threadPart`), so landing in one asks for the box alone.
/** @param {ThreadLanding} destination */
export function landIn({ held = null, box, route = null }) {
  if (!box) return false;
  held ??= threadIn(box);
  if (route && held && !held.hasAttribute("tabindex")) {
    threadReturns.set(box, route);
    whenLeft(box, () => threadReturns.delete(box));
  }
  // Entering a reply is a focus move, not a navigation step to its thread or passage.
  // Reveal only the writing area: a nearest landing leaves a box already shown where
  // the reader put it (readings/landing-scroll.js, `alreadyShown`), the transcript inside a
  // margin card included.
  bringBackSurfaceOf(box);
  focusDestination(box, "move");
  beginReplyAt(box);
  scrollIntoView(box, { block: "nearest", behavior: "instant" });
  return true;
}

/** @param {Element} box @param {ReturnRoute | null} route */
export const landInThread = (box, route = null) => landIn({ box, route });

/** Declare a thread's own keys, given the reading of the thread the user is at
 * (destination.js, `threadHere`).
 *
 * The keys are live wherever the user is at a thread: in it, on the card, the message a
 * click on its words focuses, the quote, a link in a reply; and on the element whose
 * thread a card shows beside it, which is one place with it, as `c` there continues that
 * thread. `r` settles the thread from any of them, and `p` moves it between its card
 * and the floating panel, since a control, a widget, or a text box that owns a letter
 * is walked first. Enter replies only from the card, where no
 * control inside has an Enter of its own to lose; where a resolved thread draws no reply
 * box, as a resolved card doesn't, it reopens the thread into the box instead. The
 * platform's copy key with nothing selected presses Copy on the message the user is in,
 * else on the thread's latest, the keyboard's route to what Copy gives a pointer; with
 * words selected it keeps the browser's copy. `y` presses Copy link on the message the
 * user is in, else on the thread's opening message, so on the thread it copies the
 * thread's link. Absent a thread, the reference describes the open state users first
 * meet. */
/** @param {() => Element | null} threadHere */
export function declareThreadKeys(threadHere) {
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
        when: () =>
          Boolean(threadInput(cardThread())) ||
          Boolean(
            resolutionControl(cardThread())?.matches(
              '.lf-reopen:not(:disabled, [aria-disabled="true"])',
            ),
          ),
        // Find the thread's own compose row rather than a widget editor inside it.
        run: () => {
          const thread = cardThread();
          const box = threadInput(thread);
          if (box) landIn({ held: thread, box });
          else resolutionControl(thread)?.click();
        },
      },
      // `r` presses the thread's own Resolve or Reopen, whose command answers it, so the
      // control's preview names `r` (control-keys.js).
      {
        id: "thread.resolution.toggle",
        touch: false,
        keys: ["r"],
        title: () =>
          resolutionControl(threadHere())?.matches(".lf-reopen") ? "reopen" : "resolve",
        control: () => resolutionControl(threadHere()),
      },
      // `p` presses the thread's press that moves it to Leaf's other place for it, a
      // card's Open in panel or the panel's Show on page, each of which also chooses
      // where the threads after it open (threads-in-panel.js), whose notice offers `p`
      // to take the choice back.
      {
        id: "thread.move",
        touch: false,
        keys: ["p"],
        travels: true,
        title: () =>
          (
            movingControl(threadHere())?.getAttribute("aria-label") ?? "Open in panel"
          ).toLowerCase(),
        control: () => movingControl(threadHere()),
      },
      {
        id: "message.copy",
        touch: false,
        keys: ["Mod+c"],
        title: "copy message as Markdown",
        when: () => Boolean(getSelection()?.isCollapsed),
        control: () => messageCopy(threadHere()),
      },
      {
        id: "message.link",
        touch: false,
        keys: ["y"],
        title: "copy link",
        control: () => messageLinkCopy(threadHere()),
      },
    ],
  });
}
