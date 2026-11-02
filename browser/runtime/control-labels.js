/* Control construction and labels are document-local. Leaf reads their generated
   word and action markers; an ordinary host needs no page services to build them. */
import { offer, generatedElement, elementDirective } from "./element-markers.js";
import { actionName, showAction } from "./icon-paths.js";
import { keeps, keepsText } from "./keeps.js";

// Runtime searches share the vendor's native editor, frame and focus band. Callers
// own their query and results; an auxiliary reading, such as a match count, belongs
// in the control's `end` slot so it stays inside that same frame.
/** @param {string} cls @param {{name: string, label: string, placeholder?: string}} options */
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

/** @overload @param {Element} node @param {string} label @param {{says: boolean | "echo"}} options @returns {void} */
/** @param {Element} node @param {string} label @param {{says?: boolean | "echo"}} [options] */
export function relabel(node, label, options = {}) {
  generatedElement(node, options);
  keepsText(node, label);
}
