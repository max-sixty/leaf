/* Author styles stop at Leaf's chrome and generated controls through native CSS scope.

   Unscoped page and theme-package style rules are placed inside a scope rooted at the
   document and ending at .lf-chrome and .lf-ui. The browser decides which elements lie
   inside that boundary; Leaf neither parses selectors nor infers their intent. An
   authored @scope is explicit authority to style its region, including Leaf controls,
   and stands as written. A nested scope cannot escape its enclosing scope's limit.

   The CSSOM integration remains because authored sheets can arrive through @import,
   a linked sheet, a revision, or a framework rewriting a style element after boot.
   Replacing rules in their original sheet preserves relative URL resolution. Scoping
   each style rule in place preserves grouping rules, layer order, and the positions of
   explicit scopes. Keyframes and non-selector rules have no element boundary to add.
   Cross-origin sheets without CSSOM access and module-owned adopted sheets remain
   under their author's control, as before. */

const narrowed = new WeakSet();

function narrowRules(group) {
  // Each replacement occupies the same position in its group.
  for (let at = 0; at < group.cssRules.length; at++) {
    const rule = group.cssRules[at];
    if (rule instanceof CSSScopeRule || rule instanceof CSSKeyframesRule) continue;
    if (rule instanceof CSSStyleRule) {
      group.insertRule(
        `@scope (:root) to (.lf-chrome, .lf-ui) { ${rule.cssText} }`,
        at,
      );
      group.deleteRule(at + 1);
    } else if (rule.cssRules) narrowRules(rule);
  }
}

// A sheet's own rules are narrowed once; the sheets it imports are asked after every
// pass, since an import can still be loading when its parent is first read. Of a
// runtime sheet, only the theme packages' tier is the author's (layer.py, `lf-theme`).
function narrowSheet(sheet, runtime) {
  const owner = sheet.ownerNode;
  if (
    sheet.href &&
    new URL(sheet.href).origin !== window.origin &&
    !owner?.hasAttribute?.("crossorigin")
  )
    return;
  if (!narrowed.has(sheet)) {
    narrowed.add(sheet);
    if (!runtime) narrowRules(sheet);
    else
      for (const rule of sheet.cssRules)
        if (rule instanceof CSSLayerBlockRule && rule.name === "lf-theme")
          narrowRules(rule);
  }
  for (const rule of sheet.cssRules)
    if (rule instanceof CSSImportRule && rule.styleSheet)
      narrowSheet(rule.styleSheet, runtime);
}

// Every sheet the page states that has not been narrowed yet. Boot calls this before the
// first widget builds a control, and a revision activation after it brings the next
// revision's head and body in; a linked or importing sheet is complete only once its
// element has loaded. From boot on, a change in the head calls it too, and a link added
// there calls it again once it loads.
let watching = false;
export function keepPageRulesOffLayer() {
  for (const sheet of document.styleSheets)
    narrowSheet(
      sheet,
      /** @type {Element | null} */ (sheet.ownerNode)?.hasAttribute("data-lf-runtime"),
    );
  if (watching) return;
  watching = true;
  new MutationObserver((records) => {
    for (const record of records)
      for (const node of record.addedNodes)
        if (node instanceof HTMLLinkElement)
          node.addEventListener("load", keepPageRulesOffLayer, { once: true });
    keepPageRulesOffLayer();
  }).observe(document.head, {
    childList: true,
    subtree: true,
    characterData: true,
  });
}
