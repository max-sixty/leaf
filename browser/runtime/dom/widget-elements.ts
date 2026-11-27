export { searchField } from "./control-labels.js";
import { offerAction } from "../lib/controls.js";
export { generatedElement } from "../base/element-markers.js";
/* The chrome a widget injects and the words it labels, as the runtime reads them.

   A module builds the chrome it injects with the library's control constructors
   (lib/controls.js), which write the marks read here, and marks words it writes apart
   from the author's with `data-lf-gen` (the runtime's own with `generatedElement`). A
   behavior module reads a box from inside `measure` (lib/shown-box.js). A label whose
   words change holds one room for all of them with `data-lf-room`, which the theme
   sizes without script and which cuts words past it (controls.css). A module that
   rearranges what it holds inside an unchanged box says so with `lf-layout`
   (lib/widget-events.js).

   The shared drag guard (`reachedForWords`) distinguishes a click from the mouseup
   ending an active text selection by comparing the selection's focus end with the
   release. It does not suppress a press merely because an older selection contains the
   control or because the pointer landed beside selected text.

   Paint that promises a gesture — the pointer hand above all — hangs on how a press is
   spelled, the value the constructors write into `data-lf-offer`, never on a control
   class alone. The theme's one pressable rule reads that value, and `PRESSABLE` reads
   it for the passes written in JavaScript.

   `aimedAt` answers what a click on a container that takes a gesture on its whole box
   was for: the container, something working inside it or pressed around it, or the
   selection of words the click ended. It treats platform interactive elements, inside
   the container or pressed around it, as their own controls and uses `owners` to
   distinguish a container's declared member widgets from nested widgets that own their
   own interaction (`worksInside`). What it cannot know is which of the controls it
   finds the container's own module put there — an option's pick mark, a gloss's own
   mark — so the caller names that apparatus, which is the container's to press. The
   answer otherwise fails closed: declining one ambiguous container gesture is safer
   than recording a choice while the user operates nested evidence. */
import {
  pageCaretAt,
  pageRange,
  selectionBackward,
  selectionEnds,
} from "./native-selection.js";
import { overCharacter } from "./geometry.js";

import { CONTROLS, PRESSES, WORKS } from "./control-selectors.js";
import { bodyIsData, registry, tagsDeclaring } from "../state/registry.js";
import { paintKeysWithin } from "./keyboard/scopes.js";
import { HOLD } from "../lib/widget-events.js";
import { showNativeLayer } from "./keyboard/layer-stack.js";
import { pressIsKeyboardActivation } from "../base/pointer.js";
import { onPress, pressRecords } from "./focus.js";
import { actionTemplate } from "../lib/icons.js";
import {
  closestAcross,
  isElement,
  isNativeLayer,
  renderedUnder,
  renderedParent,
  untilFound,
} from "../lib/shadow-tree.js";

import { keeps } from "../lib/keeps.js";
import { html, render } from "/vendor/lit.js";
import { signal } from "/vendor/signals-core.js";
import type { Signal } from "@preact/signals-core";
import type { WidgetDeclaration } from "../../types/contract.js";
import type { PressRecords } from "./focus.js";

// A scroll target can sit inside a collapsed container: a closed <details> or popover,
// an inactive tab. Leaf reveals it as the browser's find-in-page and fragment
// navigation do (the HTML standard's ancestor revealing algorithm): it opens a closed
// <details>, and at an element `hidden="until-found"` it fires `beforematch` and
// removes the attribute, so a widget that folds content that way opens for Leaf's travel
// and the browser's find alike, and imports nothing from Leaf to do it, as the runtime's
// own folds do too (records/thread/transcript.js). Leaf also opens a closed popover, which the
// browser's find leaves shut. It walks outside-in, unlike the standard, so an inner
// widget has geometry when its own content is revealed.
// The caller passes the intent its gesture retained (user-intent.js). There is no
// default: one taken here would be taken after whatever the caller awaited, which is
// the late capture that lets stale work move a user who has since moved on.
// Exposure is synchronous. A widget that sets `hidden` on a sibling of the element it
// reveals before its listener returns, as a tab set hides the panel it leaves, replaced
// the view that stood there, so travel can place the target before waiting on ready,
// which joins the `updateComplete` of each element holding what was revealed that has
// one: a Lit widget whose view switch finishes after its listener extends its own
// `updateComplete`, as Lit elements do.
export function reveal(el: Element | null, mayReveal: () => boolean) {
  const chain = [];
  const settling = new Set();
  let replacedView = false;
  for (let a = el; a; a = renderedParent(a)) chain.push(a);
  chain.reverse();
  for (const [at, a] of chain.entries()) {
    if (!mayReveal()) break;
    if (a instanceof HTMLDetailsElement && !a.open) a.open = true;
    if (a instanceof HTMLElement && a.hasAttribute("popover") && !isNativeLayer(a))
      showNativeLayer(a, { modal: false });
    if (!untilFound(a)) continue;
    const shown = [...(a.parentNode?.children ?? [])].filter(
      (s) => !("hidden" in s && s.hidden),
    );
    a.dispatchEvent(new Event("beforematch", { bubbles: true }));
    a.removeAttribute("hidden");
    if (shown.some((sibling) => "hidden" in sibling && sibling.hidden))
      replacedView = true;
    for (const owner of chain.slice(0, at + 1))
      if (owner.updateComplete?.then) settling.add(owner.updateComplete);
  }
  const ready = Promise.all(settling);
  // Most reveal callers need only synchronous native/widget disclosure. A surface that
  // registers asynchronous presentation is already its error owner; observe this joined
  // promise so callers may ignore it without creating a duplicate page rejection.
  void ready.catch(() => {});
  return { ready, replacedView };
}

// The user's hand on a widget, in the layer's own word: a drag, a keyboard grab or a
// scrub the log has not taken yet. The element says it with an `lf-hold` event whose
// promise settles as the hand comes off (`HOLD`, lib/widget-events.js), and settles it
// as the element leaves the page too, since one that left with the hand up would hold
// every waiter for the rest of the page's life. This module holds each one, and
// everything that has to wait for the hand asks here: `dragHeld` is whether any stands.
// The hand holds back what would replace or take back the nodes under it, a new
// revision and an undo (`unaccountedGesture`, annotations/composing/engagement.js, and the undo of
// an action still in the ledger, records/undo.js's `travelling`). What the element draws
// meanwhile is its own to hold (`lf-defer`, which `LeafElement.defer()` says), and
// every other widget goes on drawing. An element that holds only its own drawing, as
// while an editor stands in place of its words, says no `lf-hold`: what a revision
// waits for under a text field in use is another rule (annotations/composing/engagement.js).
//
// Holding while a pointer is down anywhere would need no declaration, and is not done.
// A grab by keyboard has no pointer; a press whose release the window never hears
// stays down until the next press (focus.js, `pressing`), which would hold every
// revision on a page the user is only reading; and Undo's availability follows these
// hands as a signal, so a pointer's would drop its chip at every press.
//
// Held is half of annotations/composing/engagement.js's `unaccountedGesture`, so taking it up or
// putting it down moves core's ⌘Z row — a row no widget declares. The hands are a
// signal, so that row's reflection, which reads them, hears them move (keyboard/scopes.js,
// `reflectKeys`). The widget's own rows move with the grab too, even where it is a press
// on an already-focused grip and no focus event fires, so its keys are painted here.
const hands: Signal<Set<Event>> = signal(new Set());

export const dragHeld = () => hands.value.size > 0;

document.addEventListener(HOLD, (event) => {
  const [origin] = event.composedPath();
  const move = (on: boolean) => {
    const held = new Set(hands.peek());
    if (on) held.add(event);
    else held.delete(event);
    hands.value = held;
    if (origin instanceof Element) paintKeysWithin(origin);
  };
  move(true);
  const ended = () => move(false);
  Promise.resolve(event.complete).then(ended, ended);
});

// A container that takes a gesture on its whole box has to tell one aimed at itself from
// one aimed at what it holds or what holds it. This is the second: the nearest thing
// between `node` and `container` that has a use for the gesture, else a press around the
// container, or null where the container is the aim. A press around it, as a link or a
// label around a gloss, has the container's words for its face, and its activation is
// the click's meaning, which a container taking the click would cancel.
//
// It exists because an option's case is argued inside the option — a screenshot pair
// to flip, a disclosure to open, tabs to walk — while the whole card is what takes the
// pick. Without it, reading the evidence would cast a vote: a click on a tab would choose
// that option, and one on a shot's `after` radio would choose it and clear it again, two
// decisions the user never made and only the log to show for them. Fail closed, because
// a pick is sent the moment it is made: a gesture nobody can prove was a choice is not
// one.
//
// Two vocabularies, because a container holds two kinds of thing. A widget it merely
// contains is its own world, and that is every lf-* tag bar the parts the registry says
// this container is made of (`owners`) — declared rather than listed, so the
// twelfth widget is covered by its entry and a widget whose gesture lands on its own
// words rather than on chrome (a press on lf-draft's own box) is covered with the rest.
// Inert ones go in with them: a diagram is evidence the user studies with the pointer
// on it, and which evidence happens to carry a control is nothing they can see.
//
// `data-lf-offer` then catches the controls that belong to no widget — the runtime's own
// hidden line saying how many comments a block holds, which a screen reader reaches by
// Tab and which would otherwise cast a vote on the way into the thread. It catches the container's
// own apparatus too, which no rule here could tell from the rest; a container excludes
// its own, being the only thing that can name them.
export function worksInside(node: Element, container: Element) {
  // The closure, not one level: "what this container is made of" includes a
  // part's own parts — a column's cards are the board's, and one level deep a
  // grandchild part would land in `held` and swallow the gesture.
  const parts = new Set([container.localName]);
  for (let grew = true; grew;) {
    grew = false;
    for (const tag of tagsDeclaring((entry) =>
      (entry.owners ?? []).some((owner) => parts.has(owner)),
    ))
      if (!parts.has(tag)) {
        parts.add(tag);
        grew = true;
      }
  }
  const held = tagsDeclaring(() => true).filter((tag) => !parts.has(tag));
  // `closest` walks past the container to the root, so a match has to be read back
  // against it: an ordinary pick on an option's prose finds the enclosing group, which
  // is a widget the option does not hold but is above it rather than inside it. And
  // `contains` counts an element as containing itself, so the container is ruled out by
  // name — the question is what stands between the two, and a container that is itself
  // a thing to work would otherwise answer with itself and never take a gesture again.
  // A message workflow line is runtime apparatus too. It may sit in one of
  // this container's declared parts, where the part is otherwise the gesture target;
  // reading or selecting the status must not cast that gesture on its way through.
  const inner = node.closest(
    [...held, WORKS, "[data-lf-offer]", ".lf-msg-sending"].join(","),
  );
  if (inner && inner !== container && container.contains(inner)) return inner;
  return closestAcross(container.parentNode, PRESSES);
}

// What a click on such a container was for, asked once so that no caller holds two
// checks and their order. A click that landed on something working inside or around
// the container is that thing's (`worksInside`); where that is a control, the click
// guard below has already asked whether the click ended a selection. A click elsewhere
// in the container that ended a selection of its words is the selection's, and the
// answer is null (`reachedForWords`); a click made with Enter or Space never ends one.
// Any other click is the container's. Asking about the selection first would deaden an
// option's own pick mark whenever words in the option were selected.
export function aimedAt(event: MouseEvent, container: Element): Element | null {
  const { target } = event;
  if (!isElement(target)) return null;
  const inner = worksInside(target, container);
  if (inner) return inner;
  if (!pressIsKeyboardActivation(event) && reachedForWords(container)) return null;
  return container;
}

/** What else the user could aim at, at `node`, at any point on the page, marked words
 * or not: the nearest element around it, as the page renders it (`renderedParent`, so
 * through the slot that draws it), that takes the pointer itself, or null where nothing
 * does. One takes it where it is:
 * - a control, native or ARIA (`CONTROLS`), or an element with a title the browser
 *   shows, as a link, a titled button or an option's mark;
 * - an element that declares its own preview (`lfPreview`), as a card that says what
 *   it holds, or a gloss;
 * - a registered widget that draws its content itself (`content` `data`, `markdown`
 *   or `empty`), as code, a diff or a draft does, with all it draws.
 * A plain tab stop or scrolling box takes nothing, and neither does what a widget
 * holds of the author's markup, as a pane's words, an option's beside its mark, a
 * suggestion's old and new words or a playground's preview: the verbs a widget
 * declares (`verbs`) say what it records, not that a press on its content acts.
 * A thread's words preview the thread only where nothing does, on every route that
 * reads a point (annotations/preview.js, `readingAt`); presses don't ask, so a press on a
 * thread's words acts as it always has. */
export function aimableAt(node: Node | null): Element | null {
  for (
    let at = isElement(node) ? node : renderedParent(node);
    at;
    at = renderedParent(at)
  )
    if (
      at.matches(CONTROLS) ||
      (at.localName !== "iframe" && Boolean(at.getAttribute("title"))) ||
      typeof at.lfPreview === "function" ||
      drawsItsContent(registry[at.localName])
    )
      return at;
  return null;
}
// Whether a registered widget draws its content itself, by its entry.
const drawsItsContent = (entry: WidgetDeclaration | undefined) =>
  bodyIsData(entry) || entry?.content === "empty";
// Whether a widget drew `node`: a registered widget that draws its content itself
// stands round it as the page renders it, as an activity list does round its rows.
// What a widget holds of the author's markup, as a pane's words, it didn't draw.
export const drawnByWidget = (node: Node) => {
  for (let at = renderedParent(node); at; at = renderedParent(at))
    if (drawsItsContent(registry[at.localName])) return true;
  return false;
};

// The chrome a widget injects: a control, or the box that holds controls. Three
// markers, one per question asked of it — `lf-ui` for apparatus identity, which
// anchoring reads where no label speaks nearer; `data-lf-gen` for words the author
// didn't write; `data-lf-offer` for a thing to work, which paper drops because there is
// nothing there to press.
// DOM writers and template directives share these markers through lib/controls.js.
//
// What the value above names as a press: the tag for a button, the type for a native
// choice, or the role for a selectable offer, against the empty string the rest of a
// widget's chrome takes. The theme states
// the same reading in CSS for the hand and the focus ring; this is it for the passes
// written in JavaScript.
export const PRESSABLE = '[data-lf-offer]:not([data-lf-offer=""])';

// A drag that ends on a control is that selection's mouseup, not a press: the
// user was reaching for the words, and a control whose label is one of the
// page's own words is exactly where they reach. Here rather than in each widget,
// because `offer` is what made the thing pressable — the same reason the markers
// live there. A keyboard activation (detail 0) is never a drag.
//
// The question is whether *this* click's mouseup is where the selection stopped, so
// it reads the selection's focus end — the character the pointer was on when the
// button came up. Asking instead whether the selection contains the control is a
// question about the DOM, and it answers yes for any selection running over the
// control: a suggestion's row is the column's own child, in flow between the block
// holding the change and the next one, so a user who reads across the change and
// then reaches for Accept would press a control that has gone dead — and stays dead,
// because a press that refuses a drag (`user-select: none`) never collapses the
// selection that deadened it either.
// Which is a reading rather than this listener's own business, because a container that
// takes a click on its whole box asks it of its words too (`aimedAt`).
// It asks only where the selection stopped, and not whether a press happened at all:
// which presses can be a drag is each caller's own question, which both ask of the
// click's `detail` (`pressIsKeyboardActivation`).
//
// It reads the selection as the press's `mouseup` arrives, not as its click does. A
// mouse press on words already selected leaves them selected until its `mouseup` in
// every engine; Firefox collapses them before the click and Chromium only after it.
// Read at the click, the same press would be the selection's in Chromium and the
// container's in Firefox, where a press on a comment's mark inside an option's
// selected words would pick the option rather than open the thread. Not as early as
// `pointerup`: a tap's `mousedown`, which collapses the selection it landed beside,
// comes after its `pointerup`. A click that no pointer press began, such as one a
// script dispatches with a click count, reads the selection as it stands.
//
// A selection the press found standing and left as it was is the press's only where
// the press came down on its words. Chromium also keeps a selection through a press
// beside it, before the first line the selection reaches or after the last, though
// the press reached for nothing the selection holds, and Firefox collapses it there.
// So a selection the press made or moved, as a drag or a double-click does, is always
// the press's, and one it found is the press's where the release stands over one of
// its characters.
const releases: PressRecords<{ before: unknown[]; focus?: Node | null }> =
  pressRecords();
onPress((start) => {
  const sel = getSelection();
  releases.keep(start, { before: sel ? selectionEnds(sel) : [] });
});
addEventListener(
  "mouseup",
  (event) => {
    const release = releases.kept();
    if (!release) return;
    const focus = selectionFocus();
    const sel = getSelection();
    release.focus =
      focus !== null &&
      sel !== null &&
      selectionEnds(sel).every((end, i) => end === release.before[i]) &&
      !onSelectedWords(pageRange(sel), event.clientX, event.clientY)
        ? null
        : focus;
  },
  { capture: true, passive: true },
);

// Whether a point lies over a character `range` holds.
function onSelectedWords(range: Range, x: number, y: number) {
  const caret = pageCaretAt(x, y);
  const node = caret?.offsetNode;
  if (!caret || !(node instanceof Text)) return false;
  return [caret.offset, caret.offset - 1].some(
    (at) =>
      at >= 0 &&
      at < node.length &&
      range.isPointInRange(node, at) &&
      range.isPointInRange(node, at + 1) &&
      overCharacter(node, at, x, y),
  );
}

// The node the selection's focus end stands in, or null where no words are selected.
// It reads the selected words as the page's reading does (`pageRange`), since the
// question is whether a press reached for words, not where the caret is drawn
// (`userCaret`).
function selectionFocus() {
  const sel = getSelection();
  if (!sel?.rangeCount) return null;
  const range = pageRange(sel);
  if (range.collapsed) return null;
  return selectionBackward(sel, range) ? range.startContainer : range.endContainer;
}

function reachedForWords(el: Element) {
  const released = releases.kept()?.focus;
  const focus = released === undefined ? selectionFocus() : released;
  return focus !== null && renderedUnder(focus, el);
}

document.addEventListener(
  "click",
  (ev) => {
    // A drag is a pointer's; the keyboard's own activation of the control is not one and
    // is read the one way every press claim reads it (base/pointer.js).
    if (pressIsKeyboardActivation(ev)) return;
    // The question goes to the innermost control the press landed on. A native control
    // inside chrome a widget made, such as a fold's toggle in a thread card that wears
    // `data-lf-offer`, is its own press: asked of the card, a selection anywhere in the
    // card's words deadened every button in it.
    const control = ev
      .composedPath()
      .find(
        (node): node is Element =>
          node instanceof Element && node.matches(`${PRESSES},[data-lf-offer]`),
      );
    if (control && reachedForWords(control)) {
      ev.stopPropagation();
      ev.preventDefault();
    }
  },
  true,
);

// Every surface that closes wears one control for it: the cross, named for what it
// closes, since the glyph alone says only "close". `name` is the accessible name, such
// as "Close threads", which its preview says with the keys the register gives it.
export const closeControl = ({
  name,
  className = "",
}: {
  name: string;
  className?: string;
}) => offerAction("symbol", className, name, { action: "close" });

// The anchored response bar has one control grammar of its own. Its buttons share the
// field's type, border, height, and floating elevation without claiming to be target-
// margin entries. The repeated anatomy lets Comment, Suggest, and package reactions
// change vocabulary without each inventing a button shape. A reaction shows its emoji,
// and Leaf's own actions their symbol (icon-paths.js, `ACTIONS`). Restating the anatomy
// a control already wears writes nothing (lib/keeps.js).
export function responseAction<T extends HTMLElement>(
  control: T,
  {
    glyph = null,
    action = null,
    label,
    behavior = "action",
    collapse = false,
  }: {
    glyph?: string | null;
    action?: string | null;
    label: string;
    behavior?: string;
    collapse?: boolean;
  },
): T {
  if (Boolean(String(glyph ?? "").trim()) === Boolean(action))
    throw new TypeError("A response action needs exactly one glyph or action");
  control.classList.toggle("lf-response-action", true);
  keeps(control, "data-lf-behavior", behavior);
  control.toggleAttribute("data-lf-collapse", collapse);
  if (behavior !== "action" && !control.hasAttribute("aria-expanded"))
    control.setAttribute("aria-expanded", "false");
  if (behavior === "action") control.removeAttribute("aria-expanded");
  if (!control.hasAttribute("aria-label")) control.setAttribute("aria-label", label);
  render(
    html`${
        action
          ? actionTemplate(action)
          : html`<span class="lf-response-action-glyph" aria-hidden="true"
              >${glyph}</span
            >`
      }<span class="lf-response-action-space" aria-hidden="true"> </span
      ><span class="lf-response-action-label">${label}</span>`,
    control,
  );
  return control;
}
