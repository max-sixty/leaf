import { tagsDeclaring } from "./registry.js";

// How a widget collapses content it may need to show again (lf-tabs' inactive
// panels, a settled lf-options' cards): hidden="until-found", so find-in-page
// and fragment navigation still reach it — `beforematch` fires and the widget
// reopens what it owns. It is only a hide where the UA supports it (it rides
// content-visibility, and the theme's display:block outranks the boolean
// [hidden] rule) — without beforematch, fall back to plain boolean hidden,
// which the theme hides itself; the widget still collapses and reopens, ⌘F
// just can't see in.
export const HIDDEN = "onbeforematch" in document.body ? "until-found" : "";

let publishedMeasure;
export { publishedMeasure as measure };

export function createMeasurements({ shownBox }) {
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
  // cannot return through what triggered it. The loop the page's other geometry writer
  // guards against (syncLayout, and the rule stated with it) needs a second delivery to
  // the element that was just written, and after the unobserve there is none.
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
  function measure(el, take) {
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

  publishedMeasure = measure;
  return { measure };
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
// open, a player to start. HTML's interactive content is where this comes from rather
// than a list anyone here may add to, and it differs in two places, both about whether a
// click can arrive. `summary` stands for `details`, because only the summary is the press
// and the body under it is prose the reader may point at like any other. And nothing
// embedded (`iframe`, `embed`, `object`): a click inside one never crosses into this
// document, so listing them would guard a gesture no listener out here can see.
const WORKS = "a, audio, button, input, label, select, summary, textarea, video";

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
// than on chrome (lf-draft's double-click) is covered with the rest. Inert ones go in with
// them: a diagram is evidence the reader studies with the pointer on it, and which
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
  // A local work line is runtime apparatus too. It may deliberately sit in one of
  // this container's declared parts, where the part is otherwise the gesture target;
  // reading or selecting the status must not cast that gesture on its way through.
  const inner = node.closest(
    [...held, WORKS, "[data-lf-offer]", ".lf-work-line"].join(","),
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
// "button" names a thing to press, not the element. A real <button> is a wall a
// pointer's selection cannot cross — Chrome starts no selection inside a form
// control and `user-select: text` does not move it — so any word inside one is
// unreachable to a user whatever it is marked, and a control's label turns out
// to be one of the page's own words often enough (a tab's name, the card a settled
// group carries, the mark on a chosen option) that a widget cannot be trusted to
// have picked the element with that in mind. So a press is a span wearing the role,
// and the keys the UA would have supplied are wired once below. Nothing these controls
// do needed the element: no forms, no submit, and no `disabled` — which a widget's press
// therefore cannot have (the .lf-btn:disabled rule is the runtime's own buttons').
export function offer(tag, cls, label) {
  const press = tag === "button";
  const node = document.createElement(press ? "span" : tag);
  if (press) {
    node.setAttribute("role", "button");
    node.tabIndex = 0;
  }
  node.className = cls ? `${cls} lf-ui` : "lf-ui";
  node.dataset.lfGen = "1";
  // Whether this is a press, said in the one marker a widget has no reason to touch. The
  // tabindex cannot say it — every focus target wears one, and a conversation thread wears
  // one so j/k can land on it, which had the key line leading with "press it" over an
  // element that answers nothing. Nor can the role: `offer` writes `button` and a widget is
  // free to specialise it, which `lf-tabs` does (`role="tab"`), and reading the role took
  // Enter and Space off every tab — Space then scrolling the page out from under the
  // reader, which is the platform default this scope exists to consume.
  //
  // Every other consumer asks for the bare attribute, and `[data-lf-offer]` matches a
  // valued one, so this narrows what a press is without touching what chrome is.
  node.dataset.lfOffer = press ? "button" : "";
  if (label !== undefined) node.textContent = label;
  return node;
}

// The keys a <button> came with and a span does not — Enter and Space activate — are the
// CONTROL scope in the keyboard section below, one declaration covering every press any
// widget builds. It was a listener of its own, and the surfaces had no channel to it: the
// largest hole a survey of this runtime found was that Space activates nine classes of
// control across core and five widgets and only one of them ever said so. As a scope it is
// named once in the reference, and named on the line exactly while the reader stands on
// one — which is where the walk through the page's asks puts them.

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

export function installReachedForWordsGuard() {
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
}

// A control's label, and which kind of word it is. Most are things to do — "Save",
// "choose", a grip — and go with the rest of the UI on paper, out of reach of a
// quote. Some are the page speaking: a pick mark reading "chosen" is the only place
// the page says which option it carries, and a tab's name is the panel's only name
// once the strip exists. One element wears both over its life, so the kind is
// restated on every write rather than settled at birth.
//
// This writes one marker and one only: data-lf-said, the page speaking. Anchoring
// takes it over the `.lf-ui` box around it — that box is a look, the chrome face, and
// it was standing in for a permission the user has no category for — and paper
// reads it beside data-lf-offer to keep a control whose label is one of the page's own
// words. data-lf-gen goes on either way, because the diff parses the base version
// unupgraded and would read any label as text that version lacked.
//
// It leaves data-lf-offer alone, which it used to clear. That attribute is what `offer`
// made: this is a control a widget injected, true for the mark's whole life however it
// is worded, and three passes ask it (print, the drag guard above, the render gate).
// Clearing it here made "paper drops this" the meaning and left the other two unable to
// see a control — a drag across a picked card's mark was a press again, and only
// lf-options' own guard on the card stood between that and clearing the pick.
//
// `says` has no default, because the answer a caller doesn't give is the one that
// costs a printed page its words, and silently. Refusing throws where the widget
// upgrades, which the console reports and the render gate reads back as a finding
// — the loud direction, in front of whoever wrote the label.
export function relabel(node, label, { says } = {}) {
  if (typeof says !== "boolean")
    throw new TypeError(
      `relabel(${label}): say whether this label is the page speaking`,
    );
  node.textContent = label;
  node.dataset.lfGen = "1";
  node.toggleAttribute("data-lf-said", says);
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
  const stood = { text: control.textContent, css: control.style.cssText };
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
  control.textContent = stood.text;
  control.style.cssText = stood.css;
  control.style.minWidth = Math.ceil(widest) + "px";
}
