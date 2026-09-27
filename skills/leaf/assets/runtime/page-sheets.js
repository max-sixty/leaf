/* The page's own rules keep off the layer's apparatus unless they name it.

   A page's stylesheet is unlayered, above every layer the kernel and the packages state
   their faces in (layer.py, CASCADE_LAYERS), so the page has the last word on its own
   document. At no specificity that also gave it the last word on the layer's: a page
   dressing its `button` and `a` is dressing its prose, and that rule took the family,
   ink, border and padding of every control a widget builds in the page (each wears
   .lf-ui) and of every button in the chrome.

   So each selector the page writes that names no widget and nothing of the layer's — no
   custom element, no `lf-` class or id, no `data-lf-` attribute, in itself or in a rule
   or scope it is nested in — is narrowed to leave that apparatus alone. The condition
   joins its subject inside :where(), weightless, so everywhere the rule still applies it
   ranks exactly as the page wrote it. A selector that names a widget is the page styling
   inside it on purpose and stands as written: Leaf's widgets, and the page's own, whose
   controls wear .lf-ui too when its module builds them with the widget API (`offer`) —
   rust-sort's `lf-sort-film button`, code-comparison's `code-reader-comparison
   .code-comparison-toolbar`. A token set on :root needs no naming, since the root is not
   apparatus. Inheritance is not a selector, so the chrome's root and .lf-ui restate the
   face they would otherwise inherit from the page (chrome.css, shadow.css).

   Rewritten through the CSSOM, not as text: the browser has parsed the sheet already,
   `selectorText` hands back its canonical serialization (a legacy `:before` comes back
   as `::before`), and an assignment it cannot parse leaves the rule as it was rather
   than dropping it. Each member of a selector list is its own question: `button,
   lf-board .grip` restyles the board's grip on purpose and every other button by
   accident, and only the second half is narrowed.

   The sheets read are the ones the delivered document states, and the next revision's
   when it activates, including sheets they import. A sheet from another origin the
   browser does not let a script read stays as written, and so does one a page module
   builds for itself after boot. */

const APPARATUS = ":not(:where(.lf-chrome, .lf-chrome *, .lf-ui, .lf-ui *))";

// A custom element's name, which has a hyphen, standing where a compound starts; an `lf-`
// class or id; or a `data-lf-` attribute. Strings and the arguments that are names rather
// than selectors (a language, a state, a part, a highlight) are read out first.
const NAMES_WIDGET = /(?:^|[\s>+~(,&|])[a-z][\w]*-|[.#]lf-|\[\s*data-lf-/i;
const NOT_SELECTORS =
  /"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|:{1,2}(?:lang|dir|state|part|highlight|nth-[a-z-]+)\([^)]*\)/gi;
const namesWidget = (text) => NAMES_WIDGET.test(text.replace(NOT_SELECTORS, ""));

const narrowed = new WeakSet();

// The top-level members of a selector list, and where in each the pseudo-element starts:
// outside every parenthesis, bracket and string.
function members(text) {
  const found = [];
  let depth = 0;
  let quote = null;
  let start = 0;
  let pseudo = -1;
  for (let at = 0; at < text.length; at++) {
    const ch = text[at];
    if (quote) {
      if (ch === "\\") at++;
      else if (ch === quote) quote = null;
    } else if (ch === '"' || ch === "'") quote = ch;
    else if (ch === "\\") at++;
    else if (ch === "(" || ch === "[") depth++;
    else if (ch === ")" || ch === "]") depth--;
    else if (depth === 0 && ch === ",") {
      found.push([text.slice(start, at), pseudo < 0 ? -1 : pseudo - start]);
      start = at + 1;
      pseudo = -1;
    } else if (depth === 0 && pseudo < 0 && ch === ":" && text[at + 1] === ":")
      pseudo = at;
  }
  found.push([text.slice(start), pseudo < 0 ? -1 : pseudo - start]);
  return found;
}

function narrow(member, pseudo) {
  const selector = pseudo < 0 ? member.trimEnd() : member.slice(0, pseudo);
  const rest = pseudo < 0 ? "" : member.slice(pseudo);
  return selector + APPARATUS + rest;
}

// `named` says an enclosing rule or scope names a widget. A nested rule extends every
// member of its parent's list, so the parent names one for it only if all of them do.
function narrowRules(rules, named) {
  for (const rule of rules) {
    if (rule instanceof CSSKeyframesRule || rule instanceof CSSImportRule) continue;
    let within = named;
    if (rule instanceof CSSScopeRule)
      within ||= namesWidget(rule.start ?? "") || namesWidget(rule.end ?? "");
    if (rule instanceof CSSStyleRule) {
      const list = members(rule.selectorText);
      if (!named) {
        const next = list
          .map(([member, pseudo]) =>
            namesWidget(member) ? member : narrow(member, pseudo),
          )
          .join(", ");
        if (next !== rule.selectorText) rule.selectorText = next;
      }
      within ||= list.every(([member]) => namesWidget(member));
    }
    if (rule.cssRules) narrowRules(rule.cssRules, within);
  }
}

// A sheet's own rules are narrowed once; the sheets it imports are asked after every
// pass, since an import can still be loading when its parent is first read.
function narrowSheet(sheet) {
  const owner = sheet.ownerNode;
  if (
    sheet.href &&
    new URL(sheet.href).origin !== location.origin &&
    !owner?.hasAttribute?.("crossorigin")
  )
    return;
  if (!narrowed.has(sheet)) {
    narrowed.add(sheet);
    narrowRules(sheet.cssRules, false);
  }
  for (const rule of sheet.cssRules)
    if (rule instanceof CSSImportRule && rule.styleSheet) narrowSheet(rule.styleSheet);
}

// Every sheet the page states that has not been narrowed yet. Boot calls this before the
// first widget builds a control, and a revision activation after it brings the next
// revision's head and body in; a linked or importing sheet is complete only once its
// element has loaded.
export function keepPageRulesOffLayer() {
  for (const sheet of document.styleSheets) {
    if (sheet.ownerNode?.hasAttribute("data-lf-runtime")) continue;
    narrowSheet(sheet);
  }
}
