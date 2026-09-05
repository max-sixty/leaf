/* The chrome a widget injects, the words it labels, and the room it measures.

   A behavior module builds injected controls with `offer`, and uses `relabel` when a
   control's label is also one of the page's words. It reserves a control's room from
   inside `measure`: a widget upgrades wherever the runtime connects it, and a shut
   panel is `display: none`, where every word measures zero and the floor the press
   needs is nothing at all. It calls `layoutChanged(el)` after view state rearranges
   descendants without resizing its outer box — `ResizeObserver` already covers size
   changes, and geometry consumers listen to this signal instead of watching every DOM
   mutation.

   A control is built by `offer` as the corresponding native element, so activation,
   disabled state, focus, and accessibility stay the browser's. The explicit
   `selectableOffer` exception is for a page word whose text must remain selectable,
   such as a tab name or chosen option; its widget owns the complete keyboard pattern.
   Both constructors mark generated chrome consistently. The shared drag guard
   (`reachedForWords`) distinguishes a click from the mouseup ending an active text
   selection by comparing the selection's focus end with the release. It does not
   suppress a press merely because an older selection contains the control or because
   the pointer landed beside selected text.

   Paint that promises a gesture — the pointer hand above all — hangs on how a press is
   spelled, never on a control class alone. Export takes the role off and leaves the
   class, so a hand hung on the class is a hand a file cannot answer. The layer's own
   spelling is the value `offer` writes into `data-lf-offer`: the tag or role for a
   press it built, the empty string for the rest of the chrome a widget makes. The
   theme's one pressable rule reads that value, and the marker outlives the role — a
   press carrying page words becomes a span in a copy and keeps its words — so the copy
   clears the value where it strips the role, and the promise leaves with the thing
   that could have answered it. A guard in the theme would not do: it would have to be
   written twice, once for the document and once for the slice a declared shadow tree
   renders under, where `html:not(.lf-copy)` matches nothing at all.

   A control that keeps its shape in a copy keeps its name too, and the name needs a
   role that admits one: a glyph whose word is collapsed away is an `img` with a text
   alternative, not a bare span wearing `aria-label`.

   `worksInside` decides whether a container gesture may take a click. It treats
   platform interactive elements as their own controls and uses `x-parent` to
   distinguish a container's declared member widgets from nested widgets that own their
   own interaction. Containers may name their own generated apparatus as an exception.
   The general answer fails closed: declining one ambiguous container gesture is safer
   than recording a choice while the reader operates nested evidence. */
import { tagsDeclaring } from "./registry.js";
import { paintKeys } from "./keyboard/scopes.js";
import { shownBox } from "./geometry.js";
import { iconElement } from "./icons.js";

// A scroll target can sit inside a collapsed container — a closed <details>, an
// inactive tab. Opening what the platform owns (details) and letting a container
// widget open what it owns (the lf-reveal event; lf-tabs listens) gives the
// target geometry before the scroll. Called before every scroll-to-content.
export function reveal(el) {
  const chain = [];
  for (let a = el; a; a = a.parentElement ?? a.getRootNode()?.host ?? null)
    chain.push(a);
  // Reveal outside-in so an inner widget has geometry when it handles the signal.
  for (const a of chain.reverse()) {
    if (a.tagName === "DETAILS" && !a.open) a.open = true;
    a.dispatchEvent(new CustomEvent("lf-reveal", { detail: { target: el } }));
  }
}

// The one way the layer makes an element: a tag, its classes, and the words it starts
// with.
export function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

// How a widget collapses content it may need to show again (lf-tabs' inactive
// panels, a settled lf-options' cards): hidden="until-found", so find-in-page
// and fragment navigation still reach it — `beforematch` fires and the widget
// reopens what it owns. It is only a hide where the UA supports it (it rides
// content-visibility, and the theme's display:block outranks the boolean
// [hidden] rule) — without beforematch, fall back to plain boolean hidden,
// which the theme hides itself; the widget still collapses and reopens, ⌘F
// just can't see in.
export const HIDDEN = "onbeforematch" in document.body ? "until-found" : "";

// A render bound to the `lf-actions` heartbeat runs every two seconds on a page nobody
// has touched, so a write that restates what the node already says restates it at that
// rate: the mutation stream a screen reader rebuilds its buffer from, a fresh dirty box
// for whatever reads next, and — for the attributes the document's disclosure watch
// reads — a repaint of every key on the page. `toggleAttribute` keeps that rule for the
// flags by construction; these two are the same rule for the names, states, and words
// that have no such door.
// The comparison is against what the attribute would read back as, not what the caller
// held: `getAttribute` answers with a string and `setAttribute` stringifies, so a
// boolean or a count compared raw is never equal to the attribute already standing and
// rewrites on every pass — the defect this closes, wearing the shape of the guard.
export function keeps(node, name, value) {
  const said = String(value);
  if (node && node.getAttribute(name) !== said) node.setAttribute(name, said);
}

export function keepsHidden(node, hidden) {
  if (node && node.hidden !== hidden) node.hidden = hidden;
}

// The reader's hand on a widget, in the layer's own word: a drag the log has not taken
// yet. The class is half of keyboard/page.js's `unaccountedGesture`, so taking it up or
// putting it down moves core's `z` row — a row no widget declares, and therefore the one
// no widget would think to repaint. So the paint is owed here, where the class is
// written, rather than by whoever remembers. Coalesced to a frame like every paint, which
// is what lets it stand for everything else the same gesture moved: the widget's own
// rows where the grab is a press on an already-focused grip and no focus event fires,
// and a send the drop states after this returns.
export const dragging = (el, on) => {
  el.classList.toggle("lf-dragging", on);
  paintKeys();
};

// ResizeObserver covers size changes. A view swap can instead keep its outer box while
// rearranging descendants, so the widget states that geometry change explicitly.
export const LAYOUT = "lf-layout";
export const layoutChanged = (el) =>
  el.dispatchEvent(new CustomEvent(LAYOUT, { bubbles: true, composed: true }));

// A number a widget can only read off a box the browser has laid out. Three ship: the
// room a pick mark's word will need, the room a card keeps clear of its grip, the width
// of a roster's state column. Every one is measured rather than stated for the same
// reason — the face this page is actually set in, which no constant names across two
// platforms — and every one reads 0 where there is no box to read.
//
// A widget upgrades wherever the runtime connects it, and not every one of those places
// is drawn. A message body is built for every comment the log carries and connected
// whether or not the reader has opened the panel, and a shut panel is `display: none`:
// every box beneath it is zero. `once` then refuses the second upgrade that would put
// it right, and the body is cached for the life of the tab and never rebuilt — so a
// zero taken there is indistinguishable from a measurement and stands for good. A pick
// column collapsed to nothing, a grip drawn over the card's own title.
//
// So the module states the measurement and the runtime takes it: now, where there is
// something to read, and otherwise the first time there is. ResizeObserver is the
// browser's own answer to "this has a box now", and the one that answers it wherever
// the element sits — a message scrolled past the panel's own fold has been laid out
// just the same, which is the question an IntersectionObserver would get wrong.
//
// The observation ends at the reading it was waiting for, so what a measurement writes
// cannot return through what triggered it: after the unobserve there is no second
// delivery to the element that was just written.
const measurements = new WeakMap();
const drawn = (el) => {
  const box = shownBox(el);
  return Boolean(box.width || box.height);
};
const unmeasured = new ResizeObserver((entries) => {
  const taking = [];
  for (const { target } of entries) {
    if (!drawn(target)) continue;
    unmeasured.unobserve(target);
    taking.push(measurements.get(target));
    measurements.delete(target);
  }
  // Every one released before any of them is taken: a measurement writes room its own
  // widget spends, which resizes it, and a widget still observed when that happens is a
  // second delivery inside the round that wrote it.
  for (const take of taking) take();
});
export function measure(el, take) {
  // `shownBox`, not this element's own rect: a `display: contents` wrapper draws no box
  // of its own and never will, and its contents are what the measurement is about. Asked
  // the narrow way it would wait forever, holding the take and the observation with it.
  if (drawn(el)) {
    // A wait already standing for this element is over: it was waiting for the box
    // this reading just found. Left standing it would deliver a second reading of
    // the same number, which is harmless and still a claim that nothing was read.
    if (measurements.delete(el)) unmeasured.unobserve(el);
    return take();
  }
  measurements.set(el, take);
  unmeasured.observe(el);
}

// Mention, not use: a widget inside one the registry marks x-exhibit is quoted
// material. An interactive widget consults this before wiring anything that would carry
// input back (a choose path, a drag grip), so an exhibit never takes the user's edits.
// Presentational upgrades and view state run regardless — a quoted diagram still
// renders, a quoted settled group still collapses.
export function quoted(el) {
  const exhibits = tagsDeclaring((entry) => entry["x-exhibit"]);
  return exhibits.length > 0 && el.closest(exhibits.join(",")) !== null;
}

// What a page's own markup works: a link to follow, a control to set, a disclosure to
// open, a player to start. Browser-native interactive content, the ARIA widget roles,
// and the platform's explicit focus/edit/drag markers are one boundary shared by every
// gesture owner. `summary` stands for `details`, because only the summary is the press and
// the body under it is prose the reader may point at like any other. Nothing embedded
// (`iframe`, `embed`, `object`): a click inside one never crosses into this document, so
// listing them would guard a gesture no listener out here can see.
// Anchors distinguishes an authored tab stop from one reachScrollers added to expose
// overflow. Both readings come from this one control vocabulary.
const TAB_STOP = "[tabindex]:not([tabindex='-1'])";
const WORK_SELECTORS = [
  "a",
  "audio[controls]",
  "button",
  "img[usemap]",
  "input:not([type='hidden'])",
  "label",
  "select",
  "summary",
  "textarea",
  "video[controls]",
  "[contenteditable]:not([contenteditable='false'])",
  "[draggable='true']",
  TAB_STOP,
  "[role='application']",
  "[role='button']",
  "[role='checkbox']",
  "[role='combobox']",
  "[role='grid']",
  "[role='gridcell']",
  "[role='link']",
  "[role='listbox']",
  "[role='menu']",
  "[role='menubar']",
  "[role='menuitem']",
  "[role='menuitemcheckbox']",
  "[role='menuitemradio']",
  "[role='option']",
  "[role='radio']",
  "[role='radiogroup']",
  "[role='scrollbar']",
  "[role='searchbox']",
  "[role='separator'][tabindex]",
  "[role='slider']",
  "[role='spinbutton']",
  "[role='switch']",
  "[role='tab']",
  "[role='tablist']",
  "[role='textbox']",
  "[role='tree']",
  "[role='treegrid']",
  "[role='treeitem']",
];
export const WORKS = WORK_SELECTORS.join(",");
export const WORKS_WITHOUT_TAB_STOP = WORK_SELECTORS.filter(
  (selector) => selector !== TAB_STOP,
).join(",");

// A container that takes a gesture on its whole box has to tell one aimed at itself from
// one aimed at what it holds. This is the second: the nearest thing between `node` and
// `container` that has a use for the gesture, or null where the container is the aim.
//
// It exists because an option's case is now argued inside the option — a screenshot pair
// to flip, a disclosure to open, tabs to walk — while the whole card is what takes the
// pick. Reading the evidence then cast a vote: a click on a tab chose that option, and one
// on a shot's `after` radio chose it and cleared it again, two decisions the reader never
// made and only the log to show for them. Fail closed, because a pick is sent the moment
// it is made: a gesture nobody can prove was a choice is not one.
//
// Two vocabularies, because a container holds two kinds of thing. A widget it merely
// contains is its own world, and that is every lf-* tag bar the parts the registry says
// this container is made of (x-parent) — declared rather than listed, so the twelfth
// widget is covered by its entry and a widget whose gesture lands on its own words rather
// than on chrome (a press on lf-draft's own box) is covered with the rest. Inert ones go
// in with them: a diagram is evidence the reader studies with the pointer on it, and which
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
      (entry["x-parent"] ?? []).some((parent) => parts.has(parent)),
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
  // A local receipt is runtime apparatus too. It may deliberately sit in one of
  // this container's declared parts, where the part is otherwise the gesture target;
  // reading or selecting the status must not cast that gesture on its way through.
  const inner = node.closest(
    [...held, WORKS, "[data-lf-offer]", ".lf-receipt"].join(","),
  );
  return inner && inner !== container && container.contains(inner) ? inner : null;
}

// The chrome a widget injects: a control, or the box that holds controls. Three
// markers, one per question asked of it — `lf-ui` for the runtime's look, which
// anchoring reads where no label speaks nearer; `data-lf-gen` so the diff looks away; `data-lf-offer`
// for a thing to work, which paper drops because there is nothing there to press.
// A widget writes none of the three by hand: they are what make an element chrome,
// and one of them going missing is invisible until something breaks.
//
// Native controls are the ordinary case. A widget gets their activation, disabled state,
// focus behavior, and platform accessibility contract without Leaf recreating any of it:
// ordinary buttons and links need no Leaf activation binding, and a `selectableOffer`
// registers its widget-specific keys.
export function offer(tag, cls, label) {
  const node = document.createElement(tag);
  if (node instanceof HTMLButtonElement) node.type = "button";
  node.className = cls ? `${cls} lf-ui` : "lf-ui";
  node.dataset.lfGen = "1";
  node.dataset.lfOffer = tag === "button" ? "button" : "";
  if (label !== undefined) node.textContent = label;
  return node;
}

// Put the reader on an element that may not be a tab stop: focus it, and where it will
// not take focus, lend it the tab stop a control has for exactly as long as it holds it —
// the lend leaves with the first blur, so a paragraph the address chord landed on is a
// paragraph again once the reader moves off it, and `tabindex` never becomes a thing the
// runtime leaves behind on an author's element. An element that already declares a stop
// keeps its own. Four arrivals want this and none owns the element: a numbered address
// completing on a fold, a heading or a link's fragment; a document swap handing back the
// place the reader stood in; the reference handing a reader back to the block they were
// reading; and the skip link landing on the banner when none of its controls will take
// them. Each is "the reader is now here", and each needs the browser's sequential focus
// navigation starting point to move with them, which is what `focus()` does and what
// nothing else does.
export function focusDestination(destination) {
  destination.focus({ preventScroll: true });
  if (destination.matches(":focus")) return;
  if (destination.hasAttribute("tabindex")) return;
  destination.tabIndex = -1;
  destination.focus({ preventScroll: true });
  if (!destination.matches(":focus")) {
    destination.removeAttribute("tabindex");
    return;
  }
  destination.addEventListener("blur", () => destination.removeAttribute("tabindex"), {
    once: true,
  });
}

// Some page words also act as controls: a tab name, a chosen mark, or the title of a
// settled decision. Chromium does not begin text selection inside a form control, so those
// few controls deliberately remain spans and their owning widget supplies the complete
// key contract. Keeping this constructor separate makes selectable control text a visible
// design decision instead of the behavior of every injected control.
export function selectableOffer(role, cls, label) {
  const node = document.createElement("span");
  node.setAttribute("role", role);
  node.tabIndex = 0;
  node.className = cls ? `${cls} lf-ui` : "lf-ui";
  node.dataset.lfGen = "1";
  node.dataset.lfOffer = role;
  node.dataset.lfSelectableOffer = "";
  if (label !== undefined) node.textContent = label;
  return node;
}

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
// the same complaint in its own place — the reader drew across the words to take them
// and the page went somewhere.
// It asks only where the selection stopped, and not whether a press happened at all:
// which presses can be a drag is each caller's own question. A click carries the answer
// in `detail`, and a `pointerup` is a pointer by construction and carries no detail to
// read.
export function reachedForWords(el) {
  const sel = getSelection();
  return !!sel && !sel.isCollapsed && el.contains(sel.focusNode);
}

document.addEventListener(
  "click",
  (ev) => {
    if (ev.detail === 0) return;
    const control = ev.target.closest?.("[data-lf-offer]");
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
// data-lf-gen goes on either way, because the diff parses the base version
// unupgraded and would read any label as text that version lacked.
//
// Those are two questions with one answer until a label is a copy of words the page
// says somewhere else — a roster row naming a worker, a generated index entry, any
// route built out of its target's own words. Such a label must not anchor, because two
// passages carrying the same text and the same empty context cannot be told apart and
// both detach; and it must still print, because it is the only thing naming the row it
// stands in. `says: "echo"` is that third answer, and it writes data-lf-echo: no
// passage, and the same bargain on paper that data-lf-said strikes — the press goes,
// the words stay. Paper is the medium that bargain holds in. A copy divides on the
// marker's *value* instead, which is a fact about the tag and not about this
// declaration: bake removes a press by the value `offer` wrote, so an echoed route is
// empty-valued, slips that pass and stays a real fragment link — while an echo on an
// `offer("button", …)` would go out of the copy with its words inside it, and nothing
// would report the loss, because the static-ising pass that would have kept them reads
// data-lf-said alone. Unreachable while `button()` is the only caller and builds an `a`.
// The second widget to echo a label off a real press is what makes it reachable, and
// what has to teach standalone.js's two passes the third answer; it does not belong
// here, where the label is only being worded.
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
export function relabel(node, label, { says } = {}) {
  if (typeof says !== "boolean" && says !== "echo")
    throw new TypeError(
      `relabel(${label}): say whether this label is the page speaking — ` +
        `true, false, or "echo" for a copy of words it says elsewhere`,
    );
  node.textContent = label;
  node.dataset.lfGen = "1";
  node.toggleAttribute("data-lf-said", says === true);
  node.toggleAttribute("data-lf-echo", says === "echo");
}

// Room for a word not yet said, taken from the words themselves. A control that will
// rewrite its own label ("✓ Accept" to "✓ Accepted", a count gaining a digit) must
// hold the widest word's room from the start, or the press rewrites the one line a
// press may not move. Stating that room as a number is a measurement that stops
// being true silently when the words or the font change, so the control measures the
// words instead — in its own box and its own computed face, at load — and floors
// itself there. The two sweeps (a press, and the poll) stay the check that the words
// listed here are the words the writers actually write.
//
// Measured in place: text-only controls, swapped and restored synchronously, so no
// frame paints mid-swap. Stood out of flow for the moment — absolute, hidden — so a
// control whose news hasn't arrived yet (display: none) measures all the same and
// its neighbours don't feel the fitting. Sized by its words alone while it stands
// there, its own width cleared along with its place: a stated width can mean "and grow
// past this" in flow — a table cell laid out at `width: 0` takes what its content
// needs — where out of flow it is simply obeyed, and the widest word then measures as
// whatever padding the control has.
//
// What it cannot stand out of is an ancestor that isn't drawn: display: none upward is
// nobody's box, and every word measures zero there. A control whose ancestors may be
// undrawn — anything a widget builds, since a widget upgrades wherever the runtime
// connects it and a shut panel is display: none — reserves from inside `measure`, which
// asks again the first time there is a box. A floor of zero is not a missing
// measurement to look at; it is the control holding no room at all.
export function reserve(control, labels) {
  // Standing the control out of flow hides it, and hiding a focused element takes the
  // focus off it — onto body, silently, a frame after the reader put it here. The
  // fitting is synchronous and invisible, and losing the reader's place is not part of
  // what it was asked to do. Renewing the banner's reservations across a breakpoint is
  // where this shows: a reader holding one address crosses 900px and is standing on
  // nothing.
  const held = document.activeElement === control;
  const stood = { nodes: [...control.childNodes], css: control.style.cssText };
  Object.assign(control.style, {
    minWidth: "0",
    width: "auto",
    display: "inline-block",
    position: "absolute",
    visibility: "hidden",
  });
  let widest = 0;
  for (const label of labels) {
    control.textContent = label;
    widest = Math.max(widest, control.getBoundingClientRect().width);
  }
  control.replaceChildren(...stood.nodes);
  control.style.cssText = stood.css;
  control.style.minWidth = Math.ceil(widest) + "px";
  if (held && document.activeElement !== control)
    control.focus({ preventScroll: true });
}

// The anchored response bar has one control grammar of its own. Its buttons share the
// field's type, border, height, and floating elevation without claiming to be target-
// margin Buttons. The repeated anatomy lets Comment, Suggest, and package reactions
// change vocabulary without each inventing a button shape.
export function responseAction(
  control,
  { glyph = null, icon = null, label, behavior = "action", collapse = false },
) {
  if (Boolean(String(glyph ?? "").trim()) === Boolean(icon))
    throw new TypeError("A response action needs exactly one glyph or icon");
  control.classList.add("lf-response-control", "lf-response-action");
  control.dataset.lfBehavior = behavior;
  control.toggleAttribute("data-lf-collapse", collapse);
  if (behavior !== "action" && !control.hasAttribute("aria-expanded"))
    control.setAttribute("aria-expanded", "false");
  if (behavior === "action") control.removeAttribute("aria-expanded");
  const glyphNode = icon ? iconElement(icon) : document.createElement("span");
  if (!icon) {
    glyphNode.className = "lf-response-action-glyph";
    glyphNode.setAttribute("aria-hidden", "true");
    glyphNode.textContent = glyph;
  }
  const spaceNode = document.createElement("span");
  spaceNode.className = "lf-response-action-space";
  spaceNode.setAttribute("aria-hidden", "true");
  spaceNode.textContent = " ";
  const labelNode = document.createElement("span");
  labelNode.className = "lf-response-action-label";
  labelNode.textContent = label;
  control.replaceChildren(glyphNode, spaceNode, labelNode);
  if (!control.hasAttribute("aria-label")) control.setAttribute("aria-label", label);
  return control;
}
