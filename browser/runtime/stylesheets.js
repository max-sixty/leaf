/* The layer's constructed stylesheets: shared chrome and marks, with actual annotation
   sheets only when delivery selected the overlay renderer. The document adopts the
   chrome; the document and every shadow stage adopt the marks.

   Every delivery carries their text in the document (`delivery_sheets` in
   revision_delivery.py), so they are constructed while this module evaluates, with no
   request and no await. A CSS module import read the same way and WebKit has none; a
   fetch awaited here would work everywhere and make every page module that imports the
   widget API evaluate after DOMContentLoaded instead. */
const sheets = JSON.parse(
  document.querySelector(
    'script[type="application/json"][data-lf-runtime][data-lf-sheets]',
  ).textContent,
);

// A widget module's own rules join the theme's cascade layer (layer.py, CASCADE_LAYERS), so
// specificity, scope proximity, then order rank their rules, below Layouts, theme
// packages, semantic state and the page's own stylesheet. Shared shadow rules use
// `lf-shadow` above these adopted defaults and below theme packages and semantic state.
// Chrome and apparatus marks stay unlayered so their paint beats page and widget
// alike.
export const inBaseLayer = (text) => `@layer lf-base {\n${text}\n}`;

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
export const chromeSharedClasses = Object.freeze([
  "lf-aiming",
  "lf-ins-block",
  "lf-over-item",
  "lf-react-mark",
  "lf-mark-note",
  "lf-ui",
  "lf-version-inline",
  "lf-version-inline-deletion",
  "lf-visual-action",
]);
export const marksSheet = constructSheet(sheets.marks);
export const annotationMarkSheets = sheets.annotations
  ? [constructSheet(sheets.annotations.marks)]
  : [];
export const annotationSheets = sheets.annotations
  ? [constructSheet(sheets.annotations.chrome), ...annotationMarkSheets]
  : [];
