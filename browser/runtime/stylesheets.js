/* The layer's constructed stylesheets: shared chrome and marks, with actual annotation
   sheets only when delivery selected the overlay renderer. The document adopts the
   chrome; the document and every shadow stage adopt the marks.

   Every delivery carries their text in the document (`delivery_sheets` in
   revision_delivery.py), so they are constructed while this module evaluates, with no
   request and no await. A CSS module import read the same way and WebKit has none; a
   fetch awaited here would work everywhere and make every page module that imports the
   widget API evaluate after DOMContentLoaded instead. */
const delivery = document.querySelector(
  'script[type="application/json"][data-lf-runtime][data-lf-sheets]',
);
if (!delivery) throw new Error("The document has no runtime stylesheets");
/** @type {{chrome: string, marks: string, annotations?: {chrome: string, marks: string}}} */
const sheets = JSON.parse(delivery.textContent);

/** @param {string} text */
function constructSheet(text) {
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(text);
  return sheet;
}

export const chromeSheet = constructSheet(sheets.chrome);

// The chrome sheet's shared vocabulary: every class a rule outside its `@scope (.lf-chrome)`
// block names, and so every class with which that sheet reaches an element in the page.
// Every other class it names is private to the chrome (chrome.css's header), so a name a
// widget or page coins cannot meet a private rule. Writing a rule outside the block
// widens the widget contract; this list is where that is decided, and the render suite
// (test_a_coined_class_cannot_reach_the_chromes_rules) holds the sheet to it both ways.
export const chromeSharedClasses = Object.freeze(["lf-ui"]);
export const marksSheet = constructSheet(sheets.marks);

// The comment marks' rules style each highlight on the root and on each shadow host
// (annotation-marks.css), and every element inherits that style. Firefox has no
// highlight inheritance: it styles a highlight only from the rules that match the
// element its text sits in (notes/browser-support.md, "Highlight style inheritance").
// Where prepaint.js found that a root highlight style doesn't reach the head, the rules
// are widened to every element.
/** @param {string} text */
function markSheet(text) {
  const sheet = constructSheet(text);
  if (!window.lfHighlightsInherit)
    for (const rule of sheet.cssRules)
      if (rule instanceof CSSStyleRule)
        rule.selectorText = rule.selectorText.replace(/:root|:host/g, "*");
  return sheet;
}
export const annotationMarkSheets = sheets.annotations
  ? [markSheet(sheets.annotations.marks)]
  : [];
export const annotationSheets = sheets.annotations
  ? [constructSheet(sheets.annotations.chrome), ...annotationMarkSheets]
  : [];
