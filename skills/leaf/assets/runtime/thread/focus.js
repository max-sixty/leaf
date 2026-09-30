/* Focus readings shared by thread paint and commands. */
import { holdStanding } from "../focus.js";
import { focused } from "../keyboard/scopes.js";
import { closestAcross } from "../passages.js";
import { nextRender } from "../rendering.js";
import { repaint } from "../repaint.js";
import { SAY_BOX, THREAD } from "./selectors.js";
import { allThreads } from "./state.js";

// Native disclosure owns the panel thread's focus stop. Inline divs have no summary,
// so their established root remains the destination.
export function focusThread(thread, options) {
  (thread.querySelector(":scope > summary:not([hidden])") ?? thread).focus(options);
}

// An inline thread root may itself hold focus. A control inside it keeps its own
// command scope, while panel summaries are mapped by focusedThreadTarget below.
export function focusedThread() {
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

// Its logged id: a list thread carries it as `data-id`, a card or seat as `data-thread`.
export function heldThreadId() {
  const thread = heldThread();
  return thread?.dataset.id ?? thread?.dataset.thread ?? null;
}

// The thread every painter of standing draws — the page's contour and wash, the margin
// entry's selection — which is the held thread except across a pointer press. A press
// moves focus to the page at mousedown, and only the gesture as a whole says where it
// leaves the user: a press on the thread's own mark lands them back in it at its click.
// Read from focus alone, standing blinked off under the hand for the length of every
// such press. So the thread held at pointerdown stays the standing until the frame after
// the press ends, when the standing repaint reads focus again. This is standing as drawn,
// which lags focus across a press; a command acts on the held thread (`heldThreadId`).
let pressed = null;
let release = 0;
document.addEventListener(
  "pointerdown",
  (ev) => {
    if (ev.isPrimary && ev.button === 0) pressed = heldThreadId();
  },
  { capture: true },
);
// Every way a press can end: its release, the browser taking the pointer, a native menu
// the press opened, which swallows the release, or the window losing it altogether.
function releasePress() {
  if (!pressed || release) return;
  release = nextRender(() => {
    release = 0;
    pressed = null;
    repaint();
  });
}
for (const type of ["pointerup", "pointercancel", "contextmenu"])
  document.addEventListener(type, releasePress, { capture: true });
window.addEventListener("blur", releasePress);

export const standingThreadId = () => heldThreadId() ?? pressed;

// A pass that redraws threads hands the user writing a reply across itself, under the
// thread's identity. A surface that stops drawing a thread takes its box with it: a
// widget rebuilding its tree, or a thread leaving a widget for the margin because its
// anchor no longer lands there. The thread still stands somewhere, and the user goes on
// in its box there, with the draft every view of it shares and the caret where it was.
//
// Read before the pass: the reply box the user stands in, or the one a change took out
// from under them before the pass began (focus.js, `holdStanding`). The step it returns
// runs once the pass has drawn every surface, and lands the user through `open`, which
// puts the thread up where it stands. Typing on in the box during the pass keeps them
// in it; standing anywhere else, a press on the page included, is a newer word, and so
// is a surface that landed them itself, as a resolved thread lands them on its card. A
// box is carried once, and only to a thread with a reply box to carry it to: one the
// reading still holds, open. Nothing is put up for a thread that has none, and one that
// comes back later does not pull the user to it.
const carried = new WeakSet();
export function holdReply(open) {
  const held = holdStanding();
  const box = held?.node;
  const thread = box && closestAcross(box, THREAD);
  if (!thread || thread.querySelector(SAY_BOX) !== box || carried.has(box)) return null;
  const id = thread.dataset.id ?? thread.dataset.thread;
  return () =>
    held.restore(() => {
      carried.add(box);
      const standing = allThreads().find((candidate) => candidate.id === id);
      if (!standing || standing.resolved) return null;
      const shown = open(id);
      return shown instanceof Element
        ? closestAcross(shown, THREAD)?.querySelector(SAY_BOX)
        : null;
    });
}
