/* This module owns captured presses for modifier aim, Design mode, and the target
 * picker. Each claims a complete press before authored controls can act on it. */
import { spell } from "../../dom/keyboard/bindings.js";
import { pageCommand } from "../../dom/keyboard/register.js";
import {
  coarsePointer,
  pointerAt,
  pressIsKeyboardActivation,
  eventSource,
} from "../../base/pointer.js";
import { elementFromPointAcross } from "../../readings/passages.js";
import { aimTargetAt, captured } from "../../readings/anchor-resolution.js";
import { legendRoot } from "../design.js";
import { pointInto } from "../../readings/pointed-place.js";
import { inChrome } from "../../base/ui-marks.js";
import type { createDesignMode } from "../design.js";
import type { Command } from "../../dom/keyboard/bindings.js";

type AimTarget = NonNullable<ReturnType<typeof aimTargetAt>>;
type ClaimedPress =
  | { designMode: AimTarget | null; aim?: never; choosing?: never; continuing?: never }
  | { aim: AimTarget | null; choosing: boolean; designMode?: never; continuing?: never }
  | { continuing: ClaimedPress; designMode?: never; aim?: never; choosing?: never };

// While ⌥ is held the page shows what a click would take — the item under
// the pointer wears the aim's box (refreshAim), so the sequence
// answers "which" before the click rather than asking the user to press and find out.
// `aiming` is the modifier's state. The page shows it only where the pointer is: the
// aim's box, and the hand over an item a press takes (refreshAim). A mark of it on
// `body` that the cursor rules read made Firefox visit every element of the page each
// time ⌥ went down or came up, about 55 ms each way on #4781's 1.5 million elements.
//
// The target picker (`s`) arms the page the same way for as long as it stands: its hints
// name targets for the keyboard, and the pointer takes any of them, or one between them,
// as ⌥-click would. A click in the picker otherwise went to the page under the hints, a
// link or a control, so the user's evident attempt to point became an activation.
//
// It comes off on blur as well as on keyup, because the sequence that switches windows takes
// the keyup with it, and a page left armed under nobody's hand is a claim the user
// cannot dismiss.
export function createAim({
  marginTargetAt,
  refreshAim,
  commentOnTarget,
  drawModeActive,
  designMode,
  targetPicker,
}: {
  marginTargetAt: (node: Element) => Element | null;
  refreshAim: () => void;
  commentOnTarget: (target: AimTarget) => unknown;
  drawModeActive: () => boolean;
  designMode: ReturnType<typeof createDesignMode>;
  targetPicker: { active: () => boolean; choose: (target: AimTarget) => unknown };
}) {
  let aiming = false;
  // The explicit target picker selects inside Design mode too: its shared target map
  // owns the pointer until a choice opens a comment in the current mode. Without that
  // map, Design owns its own presses. Draw keeps the page for ink in either case.
  const aimIsAvailable = () =>
    !drawModeActive() && (!designMode.active() || targetPicker.active());
  // Whether the page is armed, given whether the modifier is held: the one reading the
  // box and the press claim both derive from, so the box cannot promise what the press
  // does not do.
  const armedBy = (held: boolean) =>
    aimIsAvailable() && (held || targetPicker.active());
  // The picker's promise under the pointer waits for a pointer that hovers: a finger's
  // last tap, on the menu entry that opened the picker, is not where it stands.
  const aimIsOn = () => armedBy(aiming) && (aiming || !coarsePointer.matches);
  // Modifier aim, declared once: the key listeners, the press guard (claimPress) and the
  // reference's row all read this object. It is the register's one row that is not a key —
  // a modifier held while the pointer clicks — so it binds nothing and carries no press, and
  // the rule that keeps it off the touch controls is the same one that keeps F7 off them. The label
  // is spelled from the modifier through the register's own table rather than written out
  // twice in two platforms' glyphs.
  const AIM: Command & { modifier: string } = {
    id: "aim.comment",
    touch: false,
    modifier: "Alt",
    keys: [],
    label: `${spell("Alt")} click`,
    title: "Comment under the pointer",
    when: aimIsAvailable,
  };
  // What the pointer is over, asked of the page rather than of an event, so pressing the key
  // without moving the mouse answers too — the user holds ⌥ to find out what they would
  // get, and the answer cannot wait for them to jiggle the mouse first. An open composer
  // is no reason to say nothing: the press still acts (it opens another target's own
  // draft), so the promise still paints — what stood down here left that one press made
  // blind.
  //
  // The margin layer is chrome that stands over the page, and a row there is about the
  // page element it stands by, so over a row the aim is at that element: the row is the
  // page's corner the user is pointing at, as it is in Design mode.
  function onPage(node: Element | null) {
    const over = node && inChrome(node) ? marginTargetAt(node) : node;
    return over && !inChrome(over) ? over : null;
  }
  function aimedTarget() {
    const pointer = pointerAt();
    if (pointer.x < 0) return null;
    const at = elementFromPointAcross(pointer.x, pointer.y);
    return pointedTarget(designMode.active() ? at : onPage(at));
  }
  // The target a press names, with the row inside it the press landed on: a comment on a
  // target taller than the window stands where the user pointed (readings/pointed-place.js).
  function pointedTarget(at: Element | null) {
    const target =
      at && (designMode.active() ? designMode.target(at) : aimTargetAt(at));
    // A drawing's part already names where on the picture it is.
    const point = target?.anchor.visual ? null : pointInto(target?.element, at);
    return target && { ...target, point };
  }
  // Called when either source of the arm changes.
  function armChanged() {
    // Picker keys name the Design legend's corners while the picker owns the choice, so
    // the legend's tags step aside (chrome.css). The mark stands on the legend, which
    // holds every box and tag, since a custom property changing on the root restyles
    // every element of the page (state/root-state.js).
    legendRoot.classList.toggle("lf-picking", targetPicker.active());
    refreshAim();
  }
  function setAiming(on: boolean) {
    aiming = on;
    armChanged();
  }
  const keyDown = (ev: KeyboardEvent) => ev.key === AIM.modifier && setAiming(true);
  const keyUp = (ev: KeyboardEvent) => ev.key === AIM.modifier && setAiming(false);
  const blur = () => setAiming(false);
  // The keydown above can go unheard: a page reloaded under a held key — the poll following
  // a new version — never hears it, and claimPress reads live modifier state, so every
  // press on the new page was claimed while nothing could paint the promise. Mouse events
  // carry that same live state, so the move re-derives the arm from the freshest carrier,
  // through the one setter, rather than trusting the latch.
  const pointerMove = (ev: PointerEvent) => {
    // The shared recorder was installed before this listener, so aimedTarget reads this
    // event's unrounded point when setAiming or refreshAim asks for it below.
    const held = ev.getModifierState(AIM.modifier);
    if (held !== aiming) setAiming(held);
    else refreshAim();
  };
  // A mouse that leaves the window stands over nothing a press could take, so the hand and
  // the box come off while the page stays armed. The shared recorder hears the same
  // event first and forgets the position (base/pointer.js).
  const pointerOut = (ev: PointerEvent) => {
    if (ev.pointerType === "mouse" && !ev.relatedTarget) refreshAim();
  };

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
  // is an item under it, and acts on nothing where there isn't. The hand says which over
  // an item; elsewhere the page keeps its own cursor, the I-beam over words no item holds
  // and over content the user edits (chrome.css). Falling through to the page instead
  // would leave the user reading the box to find out which of the two a press is about
  // to be — and a suggestion's ✓ Accept stands in the margin layer over the page, so a
  // press let through there sends Claude a decision. The aim takes it as a press on the
  // change it stands by.
  //
  // A press is its down, its up and the click they make, a double press one event more, and
  // the aim takes every one of them: which a widget listens on is not something the runtime
  // can know, and lf-draft opens its editor on the click rather than on either mousedown,
  // for reasons of its own. A press of another button ends in auxclick rather than click,
  // and a link opens its new tab there, so the claim takes that too and acts on nothing.
  const PRESS_EVENTS: readonly (
    | "pointerdown"
    | "mousedown"
    | "pointerup"
    | "mouseup"
    | "click"
    | "auxclick"
    | "dblclick"
  )[] = [
    "pointerdown",
    "mousedown",
    "pointerup",
    "mouseup",
    "click",
    "auxclick",
    "dblclick",
  ];
  // The press Design mode or the armed page has taken until the next one starts. An open
  // picker owns the choice inside the current mode; otherwise Design owns its presses.
  // A claimed press stays claimed when target resolution finds
  // nothing: that gap cannot turn back into an activation underneath the mode, and the
  // picker stays open for the next press.
  //
  // `previousPress` is the claim of the press before, kept for the rest of a multi-click:
  // a claimed press extends to its continuation, which is the same gesture. The picker's
  // first click chooses and closes it, and ⌥ can come up between the two presses, so the
  // second press finds nothing armed and would reach the page as a link followed or a word
  // selected. Chromium counts clicks on mousedown but not on pointerdown, so that is where
  // the continuation is recognised.
  let claimedPress: ClaimedPress | null = null;
  let previousPress: ClaimedPress | null = null;
  function claimPress(ev: MouseEvent) {
    // Made and dropped at the same moment, which is the start of a press: a drag already
    // under way when the key goes down keeps the events it is waiting for, and one that
    // ends after the aim's own press can still be ended.
    if (ev.type === "pointerdown") {
      previousPress = claimedPress;
      // The node pressed, not the widget host a shadow tree retargets it to: a Leaf
      // surface a widget seats in its own shadow tree is only visible from inside.
      const pressed = eventSource(ev);
      const designTarget = !targetPicker.active() && designMode.press(pressed);
      const armed =
        armedBy(ev.getModifierState(AIM.modifier)) &&
        (designMode.active()
          ? designMode.target(pressed)
          : onPage(ev.target instanceof Element ? ev.target : null));
      // The item the outline is naming, through the reading that named it (aimedTarget,
      // which aimTarget and so the box itself go through) rather than through this event's own
      // target. Both are hit tests at the one place the pointer is, and asking twice is what
      // let them differ: the browser resolves a press from its own dispatch, elementFromPoint
      // builds its own, and where two boxes share an edge — every cell of a joined group,
      // which butt with no gap between them — nothing makes the two tie-break the same way.
      // A user ⌥-pressing on that seam was outlined one option and commented on the next.
      //
      // Under the picker the press chooses, which closes the picker, rather than comments.
      // Either way the press commits its target, so it captures it here, once for the
      // press and any continuation (readings/anchor-resolution.js, `captured`).
      claimedPress = designTarget
        ? { designMode: captured(designMode.target(pressed)) }
        : armed
          ? { aim: captured(aimedTarget()), choosing: targetPicker.active() }
          : null;
    }
    if (!claimedPress && ev.type === "mousedown" && ev.detail > 1 && previousPress)
      claimedPress = { continuing: previousPress.continuing ?? previousPress };
    if (!claimedPress) return;
    // Keyboard activation belongs to the control it is on, whatever the last pointer
    // did, and every captured press mode reads that the one way (base/pointer.js).
    if (pressIsKeyboardActivation(ev)) return;
    // Not on pointerdown, whose cancellation takes the mouse events with it — the click this
    // aim ends on included. On mousedown, which is where the selection, the focus and a
    // native drag would start, and on the click, since ⌥ on a link is a download.
    if (["mousedown", "click", "auxclick"].includes(ev.type)) ev.preventDefault();
    ev.stopPropagation();
    if (ev.type !== "click") return;
    if (claimedPress.continuing?.aim && claimedPress.continuing.choosing)
      // The continuation is a new pointer input to the focus handoff, though it
      // belongs to the choice already made. Renew that choice's field landing.
      commentOnTarget(claimedPress.continuing.aim);
    else if (claimedPress.aim && claimedPress.choosing)
      targetPicker.choose(claimedPress.aim);
    else if (claimedPress.aim) commentOnTarget(claimedPress.aim);
    else if (claimedPress.designMode) designMode.open(claimedPress.designMode);
  }
  function mount() {
    // In capture, since ⌥ pressed while writing stops at the field (base/field-keys.js).
    addEventListener("keydown", keyDown, true);
    addEventListener("keyup", keyUp, true);
    addEventListener("blur", blur);
    document.addEventListener("pointermove", pointerMove);
    document.addEventListener("pointerout", pointerOut);
    for (const type of PRESS_EVENTS) document.addEventListener(type, claimPress, true);
  }
  pageCommand(AIM);
  return { aimIsOn, aimedTarget, armChanged, mount };
}
