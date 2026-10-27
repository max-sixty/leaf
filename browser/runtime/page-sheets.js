/* Page CSS keeps off Leaf controls unless its stylesheet declares access.

   Browser-parsed selectors receive a weightless exclusion on their subject. This keeps
   their root/ancestor conditions, pseudo-elements, specificity, scope proximity and
   cross-sheet order intact. An outer native @scope would change root-selector matching
   and cascade proximity. The small scanner below separates CSSOM's canonical
   selector-list members and their pseudo-element suffixes; the browser owns selector
   grammar and matching. No selector spelling grants access to Leaf controls.

   A style or link element marked data-controls stands as written, together with
   its imports. Declare the marker before attaching the sheet. Theme packages put
   deliberate control styling in controls.css, whose lf-controls tier is not filtered;
   their ordinary lf-theme rules are. Widget packages already style their controls inside their declared region.
   Authored @scope blocks keep their native meaning, with their rules filtered normally.

   CSSOM integration handles revisions, imported sheets and frameworks rewriting style
   elements. Unreadable cross-origin sheets and module-owned adopted sheets remain under
   their author's control. Inheritance remains CSS inheritance: chrome and generated
   controls restate the native face they would otherwise inherit from authored content. */

const APPARATUS = ":not(:where(.lf-chrome, .lf-chrome *, .lf-ui, .lf-ui *))";
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

function narrowRules(rules) {
  for (const rule of rules) {
    if (rule instanceof CSSKeyframesRule || rule instanceof CSSImportRule) continue;
    if (rule instanceof CSSStyleRule) {
      const next = members(rule.selectorText)
        .map(([member, pseudo]) => narrow(member, pseudo))
        .join(", ");
      if (next !== rule.selectorText) rule.selectorText = next;
    }
    if (rule.cssRules) narrowRules(rule.cssRules);
  }
}

function narrowSheet(sheet, runtime) {
  const owner = sheet.ownerNode;
  if (owner?.hasAttribute?.("data-controls")) return;
  if (
    sheet.href &&
    new URL(sheet.href).origin !== window.origin &&
    !owner?.hasAttribute?.("crossorigin")
  )
    return;
  if (!narrowed.has(sheet)) {
    narrowed.add(sheet);
    if (!runtime) narrowRules(sheet.cssRules);
    else
      for (const rule of sheet.cssRules)
        if (rule instanceof CSSLayerBlockRule && rule.name === "lf-theme")
          narrowRules(rule.cssRules);
  }
  for (const rule of sheet.cssRules)
    if (rule instanceof CSSImportRule && rule.styleSheet)
      narrowSheet(rule.styleSheet, runtime);
}

// Boot and revision activation call this before controls are built. From boot on,
// a framework rewrite or a completed linked/imported sheet gets the same treatment.
let watching = false;
export function keepPageRulesOffLayer() {
  // A sheet with no owner element is adopted, which iOS WebKit (26.1) lists in
  // `document.styleSheets` and Chromium, Gecko and desktop WebKit leave out. The
  // runtime's own chrome sheets are adopted, so narrowing them there unstyled the chrome.
  for (const sheet of document.styleSheets) {
    const owner = /** @type {Element | null} */ (sheet.ownerNode);
    if (owner) narrowSheet(sheet, owner.hasAttribute("data-lf-runtime"));
  }
  if (watching) return;
  watching = true;
  document.addEventListener(
    "load",
    (event) => {
      if (
        event.target instanceof Element &&
        event.target.matches('link[rel~="stylesheet" i], style')
      )
        keepPageRulesOffLayer();
    },
    true,
  );
  new MutationObserver(keepPageRulesOffLayer).observe(document.head, {
    childList: true,
    subtree: true,
    characterData: true,
  });
}
