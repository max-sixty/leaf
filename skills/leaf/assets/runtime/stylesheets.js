/* The layer's constructed stylesheets: the comment chrome's (chrome.css) and the marks'
   (marks.css), which the document and every shadow stage adopt. An adopted sheet stands
   in no element's markup, so a copy of the page drops it with the rest of the live layer.

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

function construct(text, name) {
  // An empty sheet is a page with no chrome and no marks, and nothing about it looks
  // wrong, so a block that is not the text it claims fails here rather than painting.
  if (typeof text !== "string")
    throw new TypeError(`leaf: the document's ${name} stylesheet is not text`);
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(text);
  return sheet;
}

export const chromeSheet = construct(sheets.chrome, "chrome");
export const marksSheet = construct(sheets.marks, "marks");
