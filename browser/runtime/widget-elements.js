import {
  offer,
  offerAction,
  generatedElement,
  elementDirective,
} from "./element-markers.js";
export {
  offerElement,
  generatedElement,
  offer,
  offerAction,
  offerActionElement,
  selectableOfferElement,
  selectableOffer,
  elementDirective,
  offered,
  offeredAction,
  selectableOffered,
  generated,
} from "./element-markers.js";
/* The chrome a widget injects and the words it labels.

   A behavior module builds injected controls with `offer`, a press wearing one of
   Leaf's control faces with `offerAction` by its role, marks words it writes that
   should stand apart from the author's with `generatedElement`, and uses `relabel`
   when a control's label is also one of the page's words. A Lit template reaches the
   same writers through element directives built by `elementDirective`. A behavior module
   reads a box from inside `measure` (shown-box.js). A label
   whose words change holds one room for all of them with `data-room`, which the
   theme sizes without script and which cuts words past it (controls.css). A module that
   rearranges what it holds inside an unchanged box says so with `layoutChanged`
   (widget-upgrade.js).

   A control is built so the browser does as much of it as it can. `offer` builds the
   corresponding native element, so activation, disabled state, focus, and
   accessibility stay the browser's. A page word that is also a control — a tab name, a
   chosen option — has to stay selectable, so `selectableOffer` builds it as a span with
   the role. One with a button's role takes a button's Enter and Space from
   selectable-press.js, on any page; for another role its widget supplies the keyboard
   pattern the native element would have. A `<button>` would not do:
   Chromium and Firefox begin a selection inside one styled `user-select: text`, but
   WebKit, so Safari and every iOS browser, begins none inside a form control whatever
   its style (notes/browser-support.md, "Selecting words inside a button in WebKit").
   Both constructors mark generated chrome consistently. The shared drag guard
   (`reachedForWords`) distinguishes a click from the mouseup ending an active text
   selection by comparing the selection's focus end with the release. It does not
   suppress a press merely because an older selection contains the control or because
   the pointer landed beside selected text.

   Paint that promises a gesture — the pointer hand above all — hangs on how a press is
   spelled, never on a control class alone. The layer's own
   spelling is the value `offer` writes into `data-lf-offer`: the tag or input type for
   a native press, the tag for a custom host that opts into its own press contract, the
   role for a selectable one, and the empty string for the rest of the chrome a widget
   makes. The theme's one pressable rule reads that value.

   `worksInside` decides whether a container gesture may take a click. It treats
   platform interactive elements as their own controls and uses `x-owners` to
   distinguish a container's declared member widgets from nested widgets that own their
   own interaction. What it cannot know is which of the controls it finds the
   container's own module put there — an option's pick mark, a gloss's own mark — so the
   caller names that apparatus, which is the container's to press. The answer otherwise
   fails closed: declining one ambiguous container gesture is safer than recording a
   choice while the user operates nested evidence. */
import { pageRange, selectionBackward } from "./native-selection.js";
import { move } from "./dom-move.js";

import { PRESSES, WORKS } from "./control-selectors.js";
import { tagsDeclaring } from "./registry.js";
import { paintKeysWithin } from "./keyboard/scopes.js";
import { showNativeLayer } from "./keyboard/layer-stack.js";
import { pressIsKeyboardActivation } from "./pointer.js";
import { actionName, showAction } from "./icon-paths.js";
import { actionTemplate } from "./icons.js";
import { renderedParent } from "./shadow.js";
import { isNativeLayer, renderedUnder } from "./shadow-tree.js";

import { keeps, keepsText } from "./keeps.js";
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
export function reveal(el, mayReveal) {
  const chain = [];
  const settling = new Set();
  let replacedView = false;
  for (let a = el; a; a = renderedParent(a)) chain.push(a);
  chain.reverse();
  for (const [at, a] of chain.entries()) {
    if (!mayReveal()) break;
    if (a.tagName === "DETAILS" && !a.open) a.open = true;
    if (a.hasAttribute?.("popover") && !isNativeLayer(a))
      showNativeLayer(a, { modal: false });
    if (a.getAttribute?.("hidden") !== "until-found") continue;
    const shown = [...(a.parentNode?.children ?? [])].filter((s) => !s.hidden);
    a.dispatchEvent(new Event("beforematch", { bubbles: true }));
    a.removeAttribute("hidden");
    if (shown.some((sibling) => sibling.hidden)) replacedView = true;
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
export function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

// The user's hand on a widget, in the layer's own word: a drag the log has not taken
// yet. This module holds it, and everything that has to wait for the hand asks here:
// `dragHeld` is whether any widget holds one. The widget calls `dragging` as it takes
// the hand up and puts it down, and puts it down in `disconnectedCallback` too, since a
// widget that leaves with the hand up would hold every waiter for the rest of the
// page's life. The hand holds back what would replace or take back the nodes under it,
// a new revision and an undo (`unaccountedGesture`, composing/engagement.js); the
// widget holds its own drawing through its controller's `defer()`, and every other
// widget goes on drawing.
//
// Held is half of composing/engagement.js's `unaccountedGesture`, so taking it up or
// putting it down moves core's `z` row — a row no widget declares. The hands are a
// signal, so that row's reflection, which reads them, hears them move (keyboard/scopes.js,
// `reflectKeys`). The widget's own rows move with the grab too, even where it is a press
// on an already-focused grip and no focus event fires, so its keys are painted here.
const hands = signal(new Set());

export const dragHeld = () => hands.value.size > 0;

export const dragging = (el, on) => {
  const held = new Set(hands.peek());
  if (on) held.add(el);
  else held.delete(el);
  hands.value = held;
  paintKeysWithin(el);
};

// A container that takes a gesture on its whole box has to tell one aimed at itself from
// one aimed at what it holds. This is the second: the nearest thing between `node` and
// `container` that has a use for the gesture, or null where the container is the aim.
//
// It exists because an option's case is now argued inside the option — a screenshot pair
// to flip, a disclosure to open, tabs to walk — while the whole card is what takes the
// pick. Reading the evidence then cast a vote: a click on a tab chose that option, and one
// on a shot's `after` radio chose it and cleared it again, two decisions the user never
// made and only the log to show for them. Fail closed, because a pick is sent the moment
// it is made: a gesture nobody can prove was a choice is not one.
//
// Two vocabularies, because a container holds two kinds of thing. A widget it merely
// contains is its own world, and that is every lf-* tag bar the parts the registry says
// this container is made of (x-owners) — declared rather than listed, so the twelfth
// widget is covered by its entry and a widget whose gesture lands on its own words rather
// than on chrome (a press on lf-draft's own box) is covered with the rest. Inert ones go
// in with them: a diagram is evidence the user studies with the pointer on it, and which
// evidence happens to carry a control is nothing they can see.
//
// `data-lf-offer` then catches the controls that belong to no widget — the runtime's own
// hidden line saying how many comments a block holds, which a screen reader reaches by
// Tab and which used to cast a vote on the way into the thread. It catches the container's
// own apparatus too, which no rule here could tell from the rest; a container excludes
// its own, being the only thing that can name them.
export function worksInside(node, container) {
  // The closure, not one level: "what this container is made of" includes a
  // part's own parts — a column's cards are the board's, and one level deep a
  // grandchild part would land in `held` and swallow the gesture.
  const parts = new Set([container.localName]);
  for (let grew = true; grew;) {
    grew = false;
    for (const tag of tagsDeclaring((entry) =>
      (entry["x-owners"] ?? []).some((owner) => parts.has(owner)),
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
  return inner && inner !== container && container.contains(inner) ? inner : null;
}

// The chrome a widget injects: a control, or the box that holds controls. Three
// markers, one per question asked of it — `lf-ui` for apparatus identity, which
// anchoring reads where no label speaks nearer; `data-lf-gen` for words the author
// didn't write; `data-lf-offer` for a thing to work, which paper drops because there is
// nothing there to press.
// DOM writers and template directives share these markers through element-markers.js.
//
// Runtime searches share the vendor's native editor, frame and focus band. Callers
// own their query and results; an auxiliary reading, such as a match count, belongs
// in the control's `end` slot so it stays inside that same frame.
export function searchField(cls, { name, label, placeholder = label }) {
  const field = offer("wa-input", `lf-search-field lf-label-hidden ${cls}`);
  field.type = "search";
  field.value = "";
  field.size = "s";
  field.withClear = true;
  // delegatesFocus keeps one native stop; the host declaration also lets modal
  // traversal discover that stop without reaching into the component's shadow DOM.
  field.tabIndex = 0;
  field.name = name;
  field.label = label;
  field.placeholder = placeholder;
  field.autocomplete = "off";
  field.spellcheck = false;
  return field;
}

// A press whose face its surface draws rather than a role, such as the floating
// panel's or a message's controls, still takes its symbol and name from its action:
// `nameAction(button, action, {label, title, className})`, or in a template
// `<button class="…" ${namedAction(action)}></button>`. It shows `action`'s symbol
// first and says the action's name as tooltip and accessible name unless `label` says
// more, as a symbol role does, so the name and the symbol can't drift apart.
/**
 * @param {Element} control @param {string} action
 * @param {{label?: string, title?: string, className?: string}} [options]
 */
export function nameAction(control, action, { label, title, className } = {}) {
  const name = label ?? actionName(action);
  keeps(control, "aria-label", name);
  keeps(control, "title", title ?? name);
  showAction(control, action, className);
}
export const namedAction = elementDirective("namedAction", nameAction);

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
// holding the change and the next one, so a user who read across the change and
// then reached for Accept pressed a control that had gone dead — and stayed dead,
// because a press that refuses a drag (`user-select: none`) never collapses the
// selection that deadened it either.
// Which is a reading rather than this listener's own business, because the same press
// reaches things `offer` never made: the panel's quote, whose press travels the page to
// the passage, and the list's landing, which moves the card the words are on. Each was
// the same complaint in its own place — the user drew across the words to take them
// and the page went somewhere.
// It asks only where the selection stopped, and not whether a press happened at all:
// which presses can be a drag is each caller's own question. A click carries the answer
// in `detail`, and a `pointerup` is a pointer by construction and carries no detail to
// read.
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
    const control = /** @type {Element | undefined} */ (
      ev
        .composedPath()
        .find(
          (node) =>
            node instanceof Element && node.matches(`${PRESSES},[data-lf-offer]`),
        )
    );
    if (control && reachedForWords(control)) {
      ev.stopPropagation();
      ev.preventDefault();
    }
  },
  true,
);

// A control's label, and which kind of word it is. Most are things to do — "Save",
// "choose", a grip — and go with the rest of the UI on paper, out of reach of a
// quote. Some are the page speaking: a pick mark reading "chosen" is the only place
// the page says which option it carries, and a tab's name is the panel's only name
// once the strip exists. One element wears both over its life, so the kind is
// restated on every write rather than settled at birth.
//
// This writes the page-speaking marker, data-lf-said. Anchoring takes it over the
// `.lf-ui` box around it — that box is a look, the chrome face, and it was standing
// in for a permission the user has no category for — and paper reads it beside
// data-lf-offer to keep a control whose label is one of the page's own words.
// data-lf-gen goes on either way, because no label is words the author wrote, which
// is what the `wrote` reading keeps (passages.js).
//
// Those are two questions with one answer until a label is a copy of words the page
// says somewhere else — a roster row naming a worker, a generated index entry, any
// route built out of its target's own words. Such a label must not anchor, because two
// passages carrying the same text and the same empty context cannot be told apart and
// both detach; and it must still print, because it is the only thing naming the row it
// stands in. `says: "echo"` is that third answer, and it writes data-lf-echo: no
// passage, and the same bargain on paper that data-lf-said strikes — the press goes,
// the words stay. Paper is the medium that bargain holds in.
//
// It leaves data-lf-offer alone, which it used to clear. That attribute is what `offer`
// made: this is a control a widget injected, true for the mark's whole life however it
// is worded, and four passes ask it (print, the drag guard above, the render gate, and
// the theme's one pressable rule, which reads the value to tell a press from the rest of
// what a widget builds).
// Clearing it here made "paper drops this" the meaning and left the others unable to
// see a control — a drag across a picked card's mark was a press again, and only
// lf-options' own guard on the card stood between that and clearing the pick.
//
// `says` has no default, because the answer a caller doesn't give is the one that
// costs a printed page its words, and silently. Refusing throws where the widget
// upgrades, which the console reports and the render gate reads back as a finding
// — the loud direction, in front of whoever wrote the label.
//
// `generatedElement(node, {says})` writes those markers without the words: for a box
// whose contents the widget writes, or words it fills in some other way.
// Widgets write the markers only through it, `relabel` and the offers, so the three
// stay consistent. Words a module writes unmarked are the page's: the version
// comparison reads sources (`version.js`), so they never read as a change, but `wrote`
// keeps them and a quote can run across them. `generated({says})` is its template form:
// `<h2 ${generated({ says: true })}>${title}</h2>`. Three writers stand apart because
// they do something it doesn't: the datum projection (projection/data.js) marks and
// unmarks authored nodes as their data comes and goes, markdown.js serializes its
// media button as HTML, and revision_delivery.py writes prepaint faces on the server.

/** @param {Element} node @param {string} label @param {{says?: boolean | "echo"}} [options] */
export function relabel(node, label, { says } = {}) {
  generatedElement(node, { says });
  keepsText(node, label);
}

// Every surface that closes wears one control for it: the cross, named for what it
// closes, since the glyph alone says only "close". `name` is the accessible name, such
// as "Close threads"; `title` is the hover's, which says the key where one closes it too.
export const closeControl = ({ name, title = name, className = "" }) =>
  offerAction("symbol", className, name, { title, action: "close" });

// The anchored response bar has one control grammar of its own. Its buttons share the
// field's type, border, height, and floating elevation without claiming to be target-
// margin entries. The repeated anatomy lets Comment, Suggest, and package reactions
// change vocabulary without each inventing a button shape. A reaction shows its glyph,
// and Leaf's own actions their symbol (icon-paths.js, `ACTIONS`). Restating the anatomy
// a control already wears writes nothing (keeps.js).
export function responseAction(
  control,
  { glyph = null, action = null, label, behavior = "action", collapse = false },
) {
  if (Boolean(String(glyph ?? "").trim()) === Boolean(action))
    throw new TypeError("A response action needs exactly one glyph or action");
  control.classList.toggle("lf-response-control", true);
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

// Motion carries the card's label, never a second live widget tree. Native chrome
// avoids copied form groups, widget lifetimes and iframe browsing contexts.
export function motionPreview(label) {
  const preview = offer("div", "lf-motion-preview", label);
  preview.inert = true;
  preview.setAttribute("aria-hidden", "true");
  return preview;
}

// A widget's generated wrapper holding the children the page authored. Revision
// member patching edits this body, while the widget keeps the wrapper itself.
const authoredBodies = new WeakMap();
export const authoredBody = (host) => authoredBodies.get(host) ?? null;
export function holdAuthoredBody(host, body) {
  for (const node of [...host.childNodes]) move(body, node, null);
  authoredBodies.set(host, body);
  return body;
}
