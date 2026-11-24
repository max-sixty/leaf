export { searchField } from "./control-labels.js";
import { offerAction } from "./lib/controls.js";
export { generatedElement } from "./element-markers.js";
/* The chrome a widget injects and the words it labels, as the runtime reads them.

   A module builds the chrome it injects with the library's control constructors
   (lib/controls.js), which write the marks read here, and marks words it writes apart
   from the author's with `data-lf-gen` (the runtime's own with `generatedElement`). A
   behavior module reads a box from inside `measure` (lib/shown-box.js). A label whose
   words change holds one room for all of them with `data-lf-room`, which the theme
   sizes without script and which cuts words past it (controls.css). A module that
   rearranges what it holds inside an unchanged box says so with `lf-layout`
   (widget-upgrade.js).

   The shared drag guard (`reachedForWords`) distinguishes a click from the mouseup
   ending an active text selection by comparing the selection's focus end with the
   release. It does not suppress a press merely because an older selection contains the
   control or because the pointer landed beside selected text.

   Paint that promises a gesture — the pointer hand above all — hangs on how a press is
   spelled, the value the constructors write into `data-lf-offer`, never on a control
   class alone. The theme's one pressable rule reads that value, and `PRESSABLE` reads
   it for the passes written in JavaScript.

   `worksInside` decides whether a container gesture may take a click. It treats
   platform interactive elements, inside the container or pressed around it, as their
   own controls and uses `owners` to distinguish a container's declared member widgets
   from nested widgets that own their own interaction. What it cannot know is which of the controls it finds the
   container's own module put there — an option's pick mark, a gloss's own mark — so the
   caller names that apparatus, which is the container's to press. The answer otherwise
   fails closed: declining one ambiguous container gesture is safer than recording a
   choice while the user operates nested evidence. */
import { pageRange, selectionBackward } from "./native-selection.js";

import { CONTROLS, PRESSES, WORKS } from "./control-selectors.js";
import { bodyIsData, registry, tagsDeclaring } from "./registry.js";
import { paintKeysWithin } from "./keyboard/scopes.js";
import { HOLD } from "./widget-upgrade.js";
import { showNativeLayer } from "./keyboard/layer-stack.js";
import { pressIsKeyboardActivation } from "./pointer.js";
import { actionTemplate } from "./lib/icons.js";
import {
  closestAcross,
  isElement,
  isNativeLayer,
  renderedUnder,
  renderedParent,
  untilFound,
} from "./lib/shadow-tree.js";

import { keeps } from "./lib/keeps.js";
import { html, render, signal } from "/runtime/framework.js";

// A scroll target can sit inside a collapsed container: a closed <details> or popover,
// an inactive tab. Leaf reveals it as the browser's find-in-page and fragment
// navigation do (the HTML standard's ancestor revealing algorithm): it opens a closed
// <details>, and at an element `hidden="until-found"` it fires `beforematch` and
// removes the attribute, so a widget that folds content that way opens for Leaf's travel
// and the browser's find alike, and imports nothing from Leaf to do it, as the runtime's
// own folds do too (thread/transcript.js). Leaf also opens a closed popover, which the
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
/** @param {Element | null} el @param {() => boolean} mayReveal */
export function reveal(el, mayReveal) {
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

// The one way the layer makes an element: a tag, its classes, and the words it starts
// with.
/** @template {keyof HTMLElementTagNameMap} K
 * @overload @param {K} tag @param {string} [cls] @param {string | null} [text]
 * @returns {HTMLElementTagNameMap[K]} */
/** @overload @param {string} tag @param {string} [cls] @param {string | null} [text]
 * @returns {HTMLElement} */
/** @param {string} tag @param {string} [cls] @param {string | null} [text] */
export function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

// The user's hand on a widget, in the layer's own word: a drag, a keyboard grab or a
// scrub the log has not taken yet. The element says it with an `lf-hold` event whose
// promise settles as the hand comes off (`HOLD`, widget-upgrade.js), and settles it
// as the element leaves the page too, since one that left with the hand up would hold
// every waiter for the rest of the page's life. This module holds each one, and
// everything that has to wait for the hand asks here: `dragHeld` is whether any stands.
// The hand holds back what would replace or take back the nodes under it, a new
// revision and an undo (`unaccountedGesture`, composing/engagement.js, and the undo of
// an action still in the ledger, undo.js's `travelling`). What the element draws
// meanwhile is its own to hold (`lf-defer`, which `LeafElement.defer()` says), and
// every other widget goes on drawing. An element that holds only its own drawing, as
// while an editor stands in place of its words, says no `lf-hold`, and revisions and
// Undo go on.
//
// Holding while a pointer is down anywhere would need no declaration, and is not done.
// A grab by keyboard has no pointer; a press whose release the window never hears
// stays down until the next press (focus.js, `pressing`), which would hold every
// revision on a page the user is only reading; and Undo's availability follows these
// hands as a signal, so a pointer's would drop its chip at every press.
//
// Held is half of composing/engagement.js's `unaccountedGesture`, so taking it up or
// putting it down moves core's ⌘Z row — a row no widget declares. The hands are a
// signal, so that row's reflection, which reads them, hears them move (keyboard/scopes.js,
// `reflectKeys`). The widget's own rows move with the grab too, even where it is a press
// on an already-focused grip and no focus event fires, so its keys are painted here.
/** @type {import("@preact/signals-core").Signal<Set<Event>>} */
const hands = signal(new Set());

export const dragHeld = () => hands.value.size > 0;

document.addEventListener(HOLD, (event) => {
  const [origin] = event.composedPath();
  /** @param {boolean} on */
  const move = (on) => {
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
/** @param {Element} node @param {Element} container */
export function worksInside(node, container) {
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
 * reads a point (preview.js, `readingAt`); presses don't ask, so a press on a
 * thread's words acts as it always has.
 * @param {Node | null} node @returns {Element | null} */
export function aimableAt(node) {
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
/** @param {import("../types/contract.js").WidgetDeclaration | undefined} entry */
const drawsItsContent = (entry) => bodyIsData(entry) || entry?.content === "empty";

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
// Which is a reading rather than this listener's own business, because the same press
// reaches things `offer` never made: the panel's quote, whose press travels the page to
// the passage, and the list's landing, which moves the card the words are on. Each is
// the same complaint in its own place — the user draws across the words to take them
// and the page goes somewhere.
// It asks only where the selection stopped, and not whether a press happened at all:
// which presses can be a drag is each caller's own question. A click carries the answer
// in `detail`, and a `pointerup` is a pointer by construction and carries no detail to
// read.
/** @param {Element} el */
export function reachedForWords(el) {
  const sel = getSelection();
  if (!sel?.rangeCount) return false;
  const range = pageRange(sel);
  const focus = selectionBackward(sel, range)
    ? range.startContainer
    : range.endContainer;
  return !range.collapsed && renderedUnder(focus, el);
}

document.addEventListener(
  "click",
  (ev) => {
    // A drag is a pointer's; the keyboard's own activation of the control is not one and
    // is read the one way every press claim reads it (pointer.js).
    if (pressIsKeyboardActivation(ev)) return;
    // The question goes to the innermost control the press landed on. A native control
    // inside chrome a widget made, such as a fold's toggle in a thread card that wears
    // `data-lf-offer`, is its own press: asked of the card, a selection anywhere in the
    // card's words deadened every button in it.
    const control = ev
      .composedPath()
      .find(
        /** @returns {node is Element} */ (node) =>
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
/** @param {{name: string, className?: string}} options */
export const closeControl = ({ name, className = "" }) =>
  offerAction("symbol", className, name, { action: "close" });

// The anchored response bar has one control grammar of its own. Its buttons share the
// field's type, border, height, and floating elevation without claiming to be target-
// margin entries. The repeated anatomy lets Comment, Suggest, and package reactions
// change vocabulary without each inventing a button shape. A reaction shows its glyph,
// and Leaf's own actions their symbol (icon-paths.js, `ACTIONS`). Restating the anatomy
// a control already wears writes nothing (lib/keeps.js).
/** @template {HTMLElement} T @param {T} control
 * @param {{glyph?: string | null, action?: string | null, label: string, behavior?: string, collapse?: boolean}} options @returns {T} */
export function responseAction(
  control,
  { glyph = null, action = null, label, behavior = "action", collapse = false },
) {
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
