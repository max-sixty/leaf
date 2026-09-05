/* This module owns modifier aim and captured presses: the Alt chord's state, the target
 * it promises under the pointer, and the click it claims. */
import { el } from "../widget-elements.js";
import { designOn, designPress, designTarget, openOnDesign } from "../design.js";
import { spell } from "../keyboard/bindings.js";
import { pointerAt } from "../pointer.js";
import { elementFromPointAcross, inChrome } from "../passages.js";
import { aimTargetAt, refreshAim } from "../anchors.js";
import { commentOnTarget, standDown } from "./surface.js";

// The aim's paint host (see its rule above). Pointer-inert and carrying only aria-hidden
// drawing geometry, it says nothing to a screen reader and takes nothing from the press
// it promises; refreshAim is its one writer, and data-for is the aimed id stated where a
// test can read the promise.
export const aimBox = el("div", "lf-ui lf-aim lf-target-paint");

// While ⌥ is held the page shows what a click would take — the item under
// the pointer wears the aim's box (refreshAim), so the chord
// answers "which" before the click rather than asking the user to press and find out.
// `aiming` is the state and the class is a rendering of it; nothing reads the class back.
//
// It comes off on blur as well as on keyup, because the chord that switches windows takes
// the keyup with it, and a page left armed under nobody's hand is a claim the user
// cannot dismiss.
let aiming = false;
// Design is the active input mode, so the chord is unavailable while it stands. Keep
// that priority in the aim's one public reading as well as its press claim: the promise
// painted under the pointer and the gesture that follows must have the same owner.
const aimIsAvailable = () => !designOn;
export const aimIsOn = () => aiming && aimIsAvailable();
// The aim chord, declared once: the key listeners, the press guard (claimPress) and the
// reference's row all read this object. It is the register's one row that is not a key —
// a modifier held while the pointer clicks — so it binds nothing and carries no press, and
// the rule that keeps it off the key line is the same one that keeps F7 off it. The label
// is spelled from the modifier through the register's own table rather than written out
// twice in two platforms' glyphs.
export const AIM = {
  id: "aim.comment",
  modifier: "Alt",
  keys: [],
  label: `${spell("Alt")} click`,
  does: "Comment on the item under the pointer",
  when: aimIsAvailable,
};
// What the pointer is over, asked of the page rather than of an event, so pressing the key
// without moving the mouse answers too — the user holds ⌥ to find out what they would
// get, and the answer cannot wait for them to jiggle the mouse first. An open composer
// is no reason to say nothing: the press still acts (it moves the draft onto another
// target), so the promise still paints — what stood down here left that one press made
// blind.
export function aimedTarget() {
  const pointer = pointerAt();
  if (pointer.x < 0) return null;
  const at = elementFromPointAcross(pointer.x, pointer.y);
  if (!at || inChrome(at)) return null;
  return aimTargetAt(at);
}
function setAiming(on) {
  aiming = on;
  document.body.classList.toggle("lf-aiming", on);
  refreshAim();
}
addEventListener("keydown", (ev) => ev.key === AIM.modifier && setAiming(true));
addEventListener("keyup", (ev) => ev.key === AIM.modifier && setAiming(false));
addEventListener("blur", () => setAiming(false));
// The keydown above can go unheard: a page reloaded under a held key — the poll following
// a new version — never hears it, and claimPress reads live modifier state, so every
// press on the new page was claimed while nothing could paint the promise. Mouse events
// carry that same live state, so the move re-derives the arm from the freshest carrier,
// through the one setter, rather than trusting the latch.
document.addEventListener("pointermove", (ev) => {
  // The shared recorder was installed before this listener, so aimedTarget reads this
  // event's unrounded point when setAiming or refreshAim asks for it below.
  const held = ev.getModifierState(AIM.modifier);
  if (held !== aiming) setAiming(held);
  else refreshAim();
});

// ⌥-click means the item under the pointer, whatever it holds. It costs the page no
// chrome and the user no selection, and it reaches an item whose words are all
// inside a control. What it costs is discoverability, which the cursor answers as far as
// a modifier can: while the key is down the pointer says a click will aim.
//
// The press it aims with is the aim's alone, so it is taken at capture — ahead of every
// handler out on the page, and of the browser's own defaults. Read on the way back up
// instead, it was a press the page had already had: ⌥-clicking an option card opened the
// composer *and* picked the option, sending Claude a decision the user never made,
// and ⌥-clicking a tab's name aimed at the widget while switching the panel under it.
// Every widget that takes a press had it, because none of them was ever told. The box
// is the promise, and a press keeps it by being the only thing the press does.
//
// Claimed at the press rather than judged at the click, because the press is where ⌥
// states what the user meant. A key released before the button comes back up would
// otherwise leave a press already taken from the page doing nothing at all.
//
// What is armed is the page rather than the items on it: an armed press aims where there
// is an item under it, and acts on nothing where there isn't. That is what the cursor is
// already saying, over everything the chrome doesn't hold out of it. Falling through to
// the page instead would leave the user reading the box to find out which of the
// two a press is about to be — and a suggestion's ✓ Accept hangs in the page's own
// column, outside the element it decides, so there is nothing above it to aim at and
// getting that wrong sends Claude a decision.
//
// A press is its down, its up and the click they make, a double press one event more, and
// the aim takes every one of them: which a widget listens on is not something the runtime
// can know, and lf-draft opens its editor on the click rather than on either mousedown,
// for reasons of its own.
const PRESS_EVENTS = [
  "pointerdown",
  "mousedown",
  "pointerup",
  "mouseup",
  "click",
  "dblclick",
];
// The press Design mode or the aim has taken until the next one starts. Design is the
// input mode and therefore stands first while active; the modifier is an aim only when
// the page is not in that mode. A Design press remains claimed when target resolution
// finds nothing: that gap cannot turn back into an activation underneath the mode.
let claimedPress = null;
function claimPress(ev) {
  // Made and dropped at the same moment, which is the start of a press: a drag already
  // under way when the key goes down keeps the events it is waiting for, and one that
  // ends after the aim's own press can still be ended.
  if (ev.type === "pointerdown") {
    const design = designPress(ev.target);
    const aim =
      aimIsAvailable() && ev.getModifierState(AIM.modifier) && !inChrome(ev.target);
    // The item the outline is naming, through the reading that named it (aimedTarget,
    // which aimTarget and so the box itself go through) rather than through this event's own
    // target. Both are hit tests at the one place the pointer is, and asking twice is what
    // let them differ: the browser resolves a press from its own dispatch, elementFromPoint
    // builds its own, and where two boxes share an edge — every cell of a joined group,
    // which butt with no gap between them — nothing makes the two tie-break the same way.
    // A reader ⌥-pressing on that seam was outlined one option and commented on the next.
    claimedPress = design
      ? { design: designTarget(ev.target) }
      : aim
        ? { aim: aimedTarget() }
        : null;
    if (claimedPress) standDown(ev.target);
  }
  if (!claimedPress) return;
  // A click carrying no pointer press is keyboard activation and belongs to the control
  // it is on; the user's Enter must reach that control whatever the last pointer did.
  if (ev.type === "click" && !ev.detail) return;
  // Not on pointerdown, whose cancellation takes the mouse events with it — the click this
  // aim ends on included. On mousedown, which is where the selection, the focus and a
  // native drag would start, and on the click, since ⌥ on a link is a download.
  if (ev.type === "mousedown" || ev.type === "click") ev.preventDefault();
  ev.stopPropagation();
  if (ev.type !== "click") return;
  if (claimedPress.aim) commentOnTarget(claimedPress.aim);
  else if (claimedPress.design) openOnDesign(claimedPress.design);
}
for (const type of PRESS_EVENTS) document.addEventListener(type, claimPress, true);
