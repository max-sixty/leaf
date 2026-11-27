/* Leaf's search field, and which kind of word a label is. Leaf reads their generated
   word markers; an ordinary host needs no page services to build them. */
import { offer } from "../lib/controls.js";
import { keepFieldKeys } from "../base/field-keys.js";

// Runtime searches share the vendor's native editor, frame and focus band. Callers
// own their query and results; an auxiliary reading, such as a match count, belongs
// in the control's `end` slot so it stays inside that same frame. Keys typed into it
// stop at it (base/field-keys.js). Its prompt is Leaf's words, as an empty comment box's
// are, so it wears Leaf's face (base/voice.js).
export function searchField(
  cls: string,
  {
    name,
    label,
    placeholder = label,
  }: { name: string; label: string; placeholder?: string },
) {
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
  field.setAttribute("data-lf-voice", "leaf");
  field.autocomplete = "off";
  field.spellcheck = false;
  keepFieldKeys(field);
  return field;
}

// A label a widget writes, and which kind of word it is. Most are things to do — "Save",
// "choose", a grip — and go with the rest of the UI on paper, out of reach of a
// quote. Some are the page speaking: a pick mark reading "selected" is the only place
// the page says which option it carries, and a tab's name is the panel's only name
// once the strip exists. One element wears both over its life, so its writer restates
// the kind on every write rather than settling it at birth.
//
// The page-speaking marker is data-lf-said. Anchoring takes it over the `.lf-ui` box
// around it — that box is a look, the chrome face, and would be standing in for a
// permission the user has no category for — and paper reads it beside data-lf-offer
// to keep a control whose label is one of the page's own words. data-lf-gen goes on
// either way, because no label is words the author wrote, which is what the `wrote`
// reading keeps (readings/passages.js).
//
// Those are two questions with one answer until a label is a copy of words the page
// says somewhere else — a roster row naming a worker, a generated index entry, any
// route built out of its target's own words. Such a label must not anchor, because two
// passages carrying the same text and the same empty context cannot be told apart and
// both detach; and it must still print, because it is the only thing naming the row it
// stands in. data-lf-echo is that third answer: the label stays chrome, so no passage,
// and paper strikes the same bargain with it as with data-lf-said — the press goes,
// the words stay. Paper is the medium that bargain holds in.
//
// Neither marker touches data-lf-offer. That attribute is what `offer` made: this is a
// control a widget injected, true for the mark's whole life however it is worded, and
// four passes ask it (print, the drag guard above, the render gate, and the theme's
// one pressable rule, which reads the value to tell a press from the rest of what a
// widget builds). Clearing it with the label's kind would make "paper drops this" the
// meaning and leave the others unable to see a control — a drag across a picked card's
// mark would be a press again, and only lf-options' own guard on the card would stand
// between that and clearing the pick.
//
// A module writes these markers on its own nodes (module-plain-elements.md, "Words it
// writes"), and the runtime marks a box whose contents it writes with
// `generatedElement` (base/element-markers.js). Words a module writes unmarked are the
// page's: the version comparison reads sources (`features/version.js`), so they never read as
// a change, but `wrote` keeps them and a quote can run across them. Three of the
// runtime's writers write the attributes themselves: the datum projection
// (records/projection/data.js) marks and unmarks authored nodes as their data comes and goes,
// records/page-markdown.js serializes its media button as HTML, and revision_delivery.py writes
// prepaint faces on the server.
