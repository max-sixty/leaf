/* Focus readings shared by thread paint and commands. */
import {
  drawn,
  focusDestination,
  holdCurrentLocation,
  focused,
  onPress,
} from "../focus.js";
import { shownBox } from "../geometry.js";
import { restrictUserIntent, retainUserIntent } from "../user-intent.js";
import { closestAcross } from "../passages.js";
import { nextRender } from "../rendering.js";
import { repaint } from "../repaint.js";
import { drawnThreadId, threadPart, THREAD } from "./selectors.js";
import { allThreads } from "./state.js";
import { replyControlDestination, replyThreadKey } from "./replies.js";
import { threadKey } from "./model.js";

// A drawn thread's root is where the user is on it.
export function focusThread(thread, cause) {
  focusDestination(thread, cause);
}

export const threadReplyInput = (thread) => {
  const input = thread && threadPart(thread, "reply");
  return input && shownBox(input).height ? input : null;
};

// Where in a drawing of a thread a route lands: the thread, its reply box (else the
// thread), or the message `message` names.
export function threadFocusDestination(
  thread,
  { part = "reply", message = null } = {},
) {
  if (part === "message")
    return thread.querySelector(`.lf-msg[data-event="${CSS.escape(message)}"]`);
  return (part === "thread" ? thread : null) ?? threadReplyInput(thread) ?? thread;
}

// The thread whose root holds focus. A control inside it keeps its own command scope.
export function focusedThreadTarget() {
  const active = focused();
  return active?.matches?.(THREAD) ? active : null;
}

// The thread the user is in, wherever it is drawn — the Threads list, the margin card, a
// seat on the page — with a control inside one standing in it too. Climbing from the
// inner focus reaches a seat a widget stages in its shadow tree. The box's way out climbs
// further, to a seat holding no thread yet (landing.js, `heldThreadOrSeat`). A walk asks
// the same of the node its origin was read from (`threadIn`).
export const threadIn = (node) => closestAcross(node, THREAD);
export const heldThread = () => threadIn(focused());

// Its logged id.
export const heldThreadId = () => drawnThreadId(heldThread());

// The thread every painter of current location draws — the page's contour and wash, the margin
// entry's selection — which is the held thread except across a pointer press. A press
// moves focus to the page at mousedown, and only the gesture as a whole says where it
// leaves the user: a press on the thread's own mark lands them back in it at its click.
// Read from focus alone, the current location blinked off under the hand for the length of every
// such press. So the thread held at pointerdown stays the current location until the frame after
// the press ends, when the current location repaint reads focus again. This is current location as drawn,
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

export const currentLocationThreadId = () => heldThreadId() ?? pressed;

// The intent restricted to the thread `id` still present: every thread takes a reply,
// a resolved one too, which the reply reopens.
const mayReplyTo = (id, intent) =>
  restrictUserIntent(intent, () =>
    allThreads().some((candidate) => candidate.id === id),
  );

// A pass that redraws threads hands the user on a thread across itself, under
// the thread's identity. A surface that stops drawing a thread takes what the user was
// on with it: a widget rebuilding its tree, a thread leaving a widget for the margin
// because its anchor no longer lands there, or coming back, which closes its margin card
// and takes its marker away. The thread still stands somewhere, and the user goes on
// with it there. From its reply box they go on in that box wherever the thread stands,
// its margin card or Threads put up for it: the same editor, carried with its caret and
// undo history (replies.js), or where the view there cannot take it, that view's own box
// with the draft and the caret. From anywhere else on the thread or its marker, holding
// no words to put up, they go on with it only to a seat the pass drew it in, on the
// thread itself, since the node they had focused has no like there; otherwise the surface
// that closed lands them, as it would any user.
//
// Read before the pass (`holdThreadPlace`): the node the user is on in a drawn thread,
// or on a node standing for one, as a margin marker does (`threadAt`), or the one a
// change took out from under them before the pass began (focus.js, `holdCurrentLocation`). The
// step it returns runs once the pass has drawn every surface. Where the node is still
// drawn, they stay on it. Otherwise it lands them through `open`, which puts the thread
// up where it stands. Typing on in the box during the pass keeps them in it; standing
// anywhere else, a press on the page included, is a newer word, and so is a surface
// that landed them itself, as a list carrying its own row does. A node left behind is
// carried once, to an open thread the reading still holds, and for a reply box also a
// resolved one with a reply still being edited. Nothing is put up for a thread that is
// gone, and one that comes back later does not pull the user to it.
// Replacement resolves through the current route, never another visible mirror of
// the same draft. Both in-document paint and executable replacement use this admission.
// `scroll: false` lands the user back in a box they had scrolled away from, moving no
// scroller to show it.
//
// From the pass's start until that step has run, the node is being carried
// (`carryingThreadPlace`): a surface closing under the user meanwhile, as the margin card
// does when its thread goes back to a widget, places no one, and the step decides.
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

// The thread itself, for a user whose node has no like where it now stands. Another
// owner that put them on a drawn node meanwhile, as a list keeping its rows does, has
// placed them already.
async function threadDestination(id, open, may) {
  const at = focused();
  if (at && at !== document.body && drawn(at)) return null;
  const shown = await open(id, { part: "thread", intent: may });
  return shown instanceof Element && focused() === shown && may() ? shown : null;
}

const carried = new WeakSet();
let carrying = null;
// A seat can appear later in the pass, after its former margin card closes. The
// close must defer its landing while the thread and the user's intent still stand;
// `may` checks for the new seat only when the pass chooses its destination. A reply
// goes on in any thread still present, a resolved one included.
export const carryingThreadPlace = (node) =>
  Boolean(node) &&
  carrying?.node === node &&
  (carrying.reply
    ? carrying.may()
    : carrying.intent() &&
      allThreads().some((thread) => thread.id === carrying.id && !thread.resolved));
export function holdThreadPlace(open, { threadAt, seated }) {
  carrying = null;
  const held = holdCurrentLocation();
  const node = held?.node;
  if (!node || carried.has(node)) return null;
  const destination = replyControlDestination(node);
  // A reply box in any view of its thread, or parked between two (replies.js), names
  // its thread itself; anything else on a thread the page draws, its margin card or a
  // seat, or on its margin entry. Threads keeps its own cards' places.
  const key = destination && replyThreadKey(node);
  const thread = !destination && closestAcross(node, ".lf-page-thread");
  const id = key
    ? allThreads().find((each) => threadKey(each) === key)?.id
    : thread
      ? drawnThreadId(thread)
      : threadAt(node);
  if (!id) return null;
  const intent = retainUserIntent({ source: node });
  // Away from its reply box, where no words of theirs have to be put up, the user goes
  // on with an open thread only to a seat the pass drew it in (`seated`): the pass opens
  // no card or panel for them.
  const may = destination
    ? mayReplyTo(id, intent)
    : restrictUserIntent(
        intent,
        () =>
          allThreads().some((each) => each.id === id && !each.resolved) && seated(id),
      );
  const carry = { node, id, intent, may, reply: Boolean(destination) };
  carrying = carry;
  return async () => {
    try {
      return await held.restore(async () => {
        carried.add(node);
        const control = destination
          ? await replyDestination(id, open, intent, { destination })
          : await threadDestination(id, open, may);
        // The row itself came along (replies.js), so it is the user's box still.
        if (control === node) carried.delete(node);
        return control;
      });
    } finally {
      if (carrying === carry) carrying = null;
    }
  };
}
