/* The layer's constructed stylesheets: shared chrome and marks, with actual annotation
   sheets only when delivery selected the overlay renderer. The document adopts the
   chrome; the document and every shadow stage adopt the marks.

   Every delivery carries their text in the document (`delivery_sheets` in
   revision_delivery.py), so they are constructed while this module evaluates, with no
   request and no await. A CSS module import read the same way and WebKit has none; a
   fetch awaited here would work everywhere and make every page module that imports the
   widget API evaluate after DOMContentLoaded instead. */
const carrier = document.querySelector(
  'script[type="application/json"][data-lf-runtime][data-lf-sheets]',
);
if (!carrier) throw new Error("leaf: the document carries no runtime stylesheets");
const sheets = JSON.parse(carrier.textContent);

// A widget module's own rules join the theme's cascade layer (layer.py, CASCADE_LAYERS), so
// specificity, scope proximity, then order rank their rules, below Layouts, semantic
// state and the page's own stylesheet. Shared shadow rules use `lf-shadow` above
// these adopted defaults and below semantic state.
// The chrome and marks sheets stay unlayered: their paint
// lies over the page and must beat page and widget alike (chrome.css).
export const inBaseLayer = (text) => `@layer lf-base {\n${text}\n}`;

export function constructSheet(text, name) {
  // An empty sheet is a page with no chrome and no marks, and nothing about it looks
  // wrong, so a block that is not the text it claims fails here rather than painting.
  if (typeof text !== "string")
    throw new TypeError(`leaf: the document's ${name} stylesheet is not text`);
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(text);
  return sheet;
}

export const chromeSheet = constructSheet(sheets.chrome, "chrome");

// The chrome sheet's shared vocabulary: every class a rule outside its `@scope (.lf-chrome)`
// block names, and so every class with which that sheet reaches an element in the page.
// Every other class it names is private to the chrome (chrome.css's header), so a name a
// widget or page coins cannot meet a private rule. Writing a rule outside the block
// widens the widget contract; this list is where that is decided, and the render suite
// (test_a_coined_class_cannot_reach_the_chromes_rules) holds the sheet to it both ways.
export const chromeSharedClasses = Object.freeze([
  "lf-aiming",
  "lf-btn",
  "lf-composer-drawing",
  "lf-composer-media",
  "lf-composer-media-item",
  "lf-composer-media-open",
  "lf-composer-media-remove",
  "lf-focus-visible",
  "lf-general",
  "lf-ins-block",
  "lf-media-open",
  "lf-message-media",
  "lf-over-item",
  "lf-react-mark",
  "lf-say",
  "lf-skip",
  "lf-thread-reply",
  "lf-ui",
  "lf-version-inline",
  "lf-version-inline-deletion",
]);
export const marksSheet = constructSheet(sheets.marks, "marks");
export const annotationMarkSheets = sheets.annotations
  ? [constructSheet(sheets.annotations.marks, "annotation marks")]
  : [];
export const annotationSheets = sheets.annotations
  ? [
      constructSheet(sheets.annotations.chrome, "annotation chrome"),
      ...annotationMarkSheets,
    ]
  : [];
