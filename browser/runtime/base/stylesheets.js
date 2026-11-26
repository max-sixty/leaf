/* The layer's constructed stylesheets: shared chrome and marks, with actual annotation
   sheets only when delivery selected the overlay renderer. The document adopts the
   chrome; the document and every shadow stage adopt the marks.

   Every delivery carries their text in the document (`delivery_sheets` in
   revision_delivery.py), and the prepaint builds them from it once, for whoever asks
   first (prepaint.js, `lfSheets`): a served page's bootstrap adopts the chrome's
   before the first paint, and this module takes the same instances as it evaluates,
   with no request and no await. A CSS module import read the same way and WebKit has
   none; a fetch awaited here would work everywhere and make every page module that
   imports the widget API evaluate after DOMContentLoaded instead. */
const sheets = window.lfSheets();

export const chromeSheet = sheets.chrome;

// The chrome sheet's shared vocabulary: every class a rule outside its `@scope (.lf-chrome)`
// block names, and so every class with which that sheet reaches an element in the page.
// Every other class it names is private to the chrome (chrome.css's header), so a name a
// widget or page coins cannot meet a private rule. Writing a rule outside the block
// widens the widget contract; this list is where that is decided, and the render suite
// (test_a_coined_class_cannot_reach_the_chromes_rules) holds the sheet to it both ways.
export const chromeSharedClasses = Object.freeze(["lf-ui"]);
export const marksSheet = sheets.marks;
export const annotationSheets = sheets.annotations;
