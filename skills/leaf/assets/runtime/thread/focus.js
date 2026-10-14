/* Focus readings shared by thread paint and commands. */
import {
  focusDestination,
  holdStanding,
  forwardFocus,
  focused,
  onPress,
} from "../focus.js";
import { shownBox } from "../geometry.js";
import { restrictUserIntent, retainUserIntent } from "../user-intent.js";
import { closestAcross } from "../passages.js";
import { upFrom } from "../shadow.js";
import { nextRender } from "../rendering.js";
import { repaint } from "../repaint.js";
import { SAY_BOX, THREAD } from "./selectors.js";
import { allThreads } from "./state.js";
import { replyAvailable, replyControlDestination } from "./replies.js";

// Native disclosure owns the panel thread's focus stop. Inline divs have no summary,
// so their established root remains the destination.
export const threadFocusStop = (thread) =>
  thread.querySelector(":scope > summary:not([hidden])") ?? thread;
export function focusThread(thread, cause) {
  focusDestination(threadFocusStop(thread), cause);
}
// The Threads list handing the focus it is gaining on to the open thread's title.
export function forwardToThread(thread) {
  forwardFocus(threadFocusStop(thread));
}

// A drawn thread's own parts: the box its reply is written in, and the control that
// settles it, whose `lf-resolve` or `lf-reopen` says which way. A card draws both inside
// itself. A presentation that draws one elsewhere, as the floating panel draws the reply
// as its field and Resolve in its view's head, declares on the thread element where each
// stands (`declareThreadParts`): `reply` and `settlement`, each a function of that
// element answering the part, or null while the thread has none there. Every reading
// of a thread's reply or settlement goes through here (`threadPart`), so Enter, `r` and
// `c` answer alike whichever chrome draws the thread. A thread drawn in pieces within
// one that declares, as a reader's message parts in the panel's view, has the
// enclosing drawing's parts where it holds none (`drawingsOf`).
//
// Such a presentation also declares `whole`, the element standing for the thread as a
// whole where its pieces stand apart, as the panel's view does for its head and its
// field (`wholeThread`).
const declaredParts = new WeakMap();
export const declareThreadParts = (thread, parts) => declaredParts.set(thread, parts);
const ownParts = {
  reply: (thread) => thread.querySelector(SAY_BOX),
  settlement: (thread) =>
    [...thread.querySelectorAll(".lf-resolve, .lf-reopen")].find(
      (control) => control.closest(THREAD) === thread,
    ) ?? null,
};
// A drawn thread's logged id: a list thread carries it as `data-id`, a card, seat or
// chrome's view as `data-thread`.
const threadIdOf = (thread) => thread.dataset.id ?? thread.dataset.thread;
// The drawings of one thread from `thread` outward: itself, then each drawing of the
// same thread around it.
function* drawingsOf(thread) {
  const id = threadIdOf(thread);
  for (
    let at = thread;
    at === thread || (at && id && threadIdOf(at) === id);
    at = closestAcross(upFrom(at), THREAD)
  )
    yield at;
}
// The whole of the thread drawn at `thread`: its outermost drawing, or the element that
// drawing declares as the whole. It holds the thread's messages, so a reading of them
// searches it, and it is the thread a keyboard stands on, as a reply box's way back.
export function wholeThread(thread) {
  const outer = [...drawingsOf(thread)].at(-1);
  return declaredParts.get(outer)?.whole(outer) ?? outer;
}
export function threadPart(thread, name) {
  for (const at of drawingsOf(thread)) {
    const part = (declaredParts.get(at) ?? ownParts)[name](at);
    if (part) return part;
  }
  return null;
}

export const threadReplyInput = (thread) => {
  const input = thread && threadPart(thread, "reply");
  return input && (shownBox(input).height || input.lfRevealReply) ? input : null;
};

// A closed native disclosure is its own first stop. An explicit reply can name a
// compact editor before it has height: the editor's reveal owns opening it on focus.
export function threadFocusDestination(thread, { part = "reply" } = {}) {
  const summary = thread?.querySelector(":scope > summary");
  return (
    (part === "thread" ? threadFocusStop(thread) : null) ??
    (summary && !thread.hasAttribute("open") ? summary : null) ??
    threadReplyInput(thread) ??
    threadFocusStop(thread)
  );
}

// An inline thread root may itself hold focus. A control inside it keeps its own
// command scope, while panel summaries are mapped by focusedThreadTarget below.
function focusedThread() {
  const active = focused();
  return active?.matches?.(THREAD) ? active : null;
}

// A native panel summary stands for its details in commands that move the whole
// thread. Controls deeper in the thread keep their own command scope.
export function focusedThreadTarget() {
  const active = focused();
  return active?.matches?.(".lf-thread-summary")
    ? active.closest(".lf-thread")
    : focusedThread();
}

// The thread the user is in, wherever it is drawn — the Threads list, the margin card, a
// seat on the page — with a control inside one standing in it too. Climbing from the
// inner focus reaches a seat a widget stages in its shadow tree. The box's way out climbs
// further, to a seat holding no thread yet (landing.js, `heldThreadOrSeat`).
export const heldThread = () => closestAcross(focused(), THREAD);

// Its logged id (`threadIdOf`).
export function heldThreadId() {
  const thread = heldThread();
  return (thread && threadIdOf(thread)) ?? null;
}

// The thread every painter of standing draws — the page's contour and wash, the margin
// entry's selection — which is the held thread except across a pointer press. A press
// moves focus to the page at mousedown, and only the gesture as a whole says where it
// leaves the user: a press on the thread's own mark lands them back in it at its click.
// Read from focus alone, standing blinked off under the hand for the length of every
// such press. So the thread held at pointerdown stays the standing until the frame after
// the press ends, when the standing repaint reads focus again. This is standing as drawn,
// which lags focus across a press; a command acts on the held thread (`heldThreadId`).
// The press is focus.js's (`onPress`), which ends it every way it can end.
let pressed = null;
let release = 0;
function releasePress() {
  if (!pressed || release) return;
  release = nextRender(() => {
    release = 0;
    pressed = null;
    repaint();
  });
}
onPress((start) => {
  if (start.button !== 0) return null;
  pressed = heldThreadId();
  return releasePress;
});

export const standingThreadId = () => heldThreadId() ?? pressed;

// The intent restricted to the thread `id` still present with a reply to write.
const mayReplyTo = (id, intent) =>
  restrictUserIntent(intent, () => {
    const thread = allThreads().find((candidate) => candidate.id === id);
    return Boolean(thread && replyAvailable(thread));
  });

// A pass that redraws threads hands the user writing a reply across itself, under the
// thread's identity. A surface that stops drawing a thread takes its box with it: a
// widget rebuilding its tree, or a thread leaving a widget for the margin because its
// anchor no longer lands there. The thread still stands somewhere, and the user goes on
// in its box there: the same editor, carried with its caret and undo history, or where
// the view there cannot take it, that view's own box with the draft and the caret.
//
// Read before the pass: the reply box the user stands in, or the one a change took out
// from under them before the pass began (focus.js, `holdStanding`). The step it returns
// runs once the pass has drawn every surface, and lands the user through `open`, which
// puts the thread up where it stands. Typing on in the box during the pass keeps them
// in it; standing anywhere else, a press on the page included, is a newer word, and so
// is a surface that landed them itself. A box left behind is carried once, to a thread
// the reading still holds and whose editor lifetime continues: an open conversation, or a resolved
// one with a reply still being edited. Nothing is put up for a thread that has none, and one that
// comes back later does not pull the user to it.
// Replacement resolves through the current route, never another visible mirror of
// the same draft. Both in-document paint and executable replacement use this admission.
// `scroll: false` lands the user back in a box they had scrolled away from, moving no
// scroller to show it.
//
// From the pass's start until that step has run, the box is being carried
// (`carryingReply`): a surface closing under the user meanwhile, as the margin card does
// when its thread goes back to a widget, places no one, and the step decides.
export async function replyDestination(
  id,
  open,
  intent,
  { destination = (thread) => threadPart(thread, "reply"), scroll = true } = {},
) {
  const mayReply = mayReplyTo(id, intent);
  if (!mayReply()) return null;
  const shown = await open(id, { part: "reply", scroll, intent: mayReply });
  const thread = shown instanceof Element ? closestAcross(shown, THREAD) : null;
  if (!thread || focused() !== shown || !mayReply()) return null;
  // The destination may put the user's own row in place of the one `open` landed on
  // (replies.js, `carry`), and they go on in it.
  const control = destination(thread);
  if (!control) return null;
  if (control !== focused()) mayReply.handoff(() => focusDestination(control, "move"));
  return focused() === control && mayReply() ? control : null;
}

const carried = new WeakSet();
let carrying = null;
export const carryingReply = (node) =>
  Boolean(node) && carrying?.box === node && carrying.mayReply();
export function holdReply(open) {
  carrying = null;
  const held = holdStanding();
  const box = held?.node;
  const thread = box && closestAcross(box, THREAD);
  const destination = replyControlDestination(box);
  if (!thread || !destination || carried.has(box)) return null;
  const id = thread.dataset.id ?? thread.dataset.thread;
  const intent = retainUserIntent({ source: box });
  const carry = { box, mayReply: mayReplyTo(id, intent) };
  carrying = carry;
  return async () => {
    try {
      return await held.restore(async () => {
        carried.add(box);
        const control = await replyDestination(id, open, intent, { destination });
        // The row itself came along (replies.js, `carry`), so it is the user's box still.
        if (control === box) carried.delete(box);
        return control;
      });
    } finally {
      if (carrying === carry) carrying = null;
    }
  };
}
