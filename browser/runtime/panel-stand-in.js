/* A stand-in for the floating panel's row, which says the keys the bootstrap holds
   while the panel has not yet mounted (bootstrap.js, `holdEarlyKeys`). The panel exists
   only once the boot module's graph has loaded, which can take half a second on a
   loaded machine. This module imports only modules that import nothing, which that
   graph loads too, so it evaluates while the graph is still arriving and shares their
   instances with it. The compiled kernel keeps the faces and icons in the portable
   helpers' chunk, which imports Lit, so there it waits for that chunk too, though not
   for the rest of the graph. The bootstrap imports it only once the document is
   parsed, since stylesheets.js reads the sheets the document carries.

   It draws the row on the panel's own classes, from the panel's sheet (stylesheets.js),
   with each symbol's face (control-faces.js) and glyph (icon-paths.js), so its leaf,
   field and On Me mark stand where the panel's will and the panel takes the words over
   in place. Its structure follows the row floating-panel.js draws (`panelTemplate`),
   whose field the held-keys test in tests/browser/startup/test_keys.py holds still
   across the handover. It takes no press, since no runtime is there to answer one,
   and offers no control to the keyboard. */
import { actionClass } from "./control-faces.js";
import { showAction } from "./icon-paths.js";
import { chromeSheet } from "./stylesheets.js";

/** @param {string} className @param {string} [tag] */
const box = (className, tag = "div") => {
  const node = document.createElement(tag);
  node.className = className;
  return node;
};

/** A symbol's face showing `action`'s glyph, as the panel's press wears it.
 * @param {string} className @param {string} action */
const symbol = (className, action) => {
  const face = box(`${actionClass("symbol", className)} lf-ui lf-ui-face`, "span");
  showAction(face, action);
  return face;
};

/** Draws the stand-in after `body`, which the document has parsed, where the
 * runtime's chrome root will stand (base.css), and returns what says the words in its
 * field and what takes it away. */
export function standInRow() {
  // The runtime adopts this same sheet in its own place in the document's order as it
  // attaches its chrome (leaf.js), so the stand-in takes its own adoption away with it.
  const adopted = !document.adoptedStyleSheets.includes(chromeSheet);
  if (adopted)
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, chromeSheet];
  const root = box("lf-chrome");
  root.setAttribute("data-lf-runtime", "");
  const panel = box("lf-ui lf-floating-panel");
  panel.setAttribute("part", "panel");
  panel.setAttribute("data-lf-stand-in", "");
  const words = box("lf-compose-placeholder-words", "span");
  const placeholder = box("lf-compose-placeholder", "span");
  placeholder.append(words);
  const held = box("lf-fp-held", "span");
  held.setAttribute("role", "status");
  held.append(placeholder);
  const field = box("lf-compose-field");
  field.append(held);
  const fieldBox = box("lf-fp-field");
  fieldBox.append(field);
  const onMe = symbol("lf-fp-on-user", "on-me");
  onMe.append(box("lf-fp-num", "span"));
  const quick = box("lf-fp-quick");
  quick.append(onMe);
  const row = box("lf-fp-row");
  row.append(symbol("lf-fp-leaf", "menu"), fieldBox, quick);
  const inner = box("lf-fp-inner");
  inner.append(row);
  const card = box("lf-fp-card");
  card.append(inner);
  panel.append(card);
  root.append(panel);
  document.body.after(root);
  return {
    /** The words in the field, drawn as the panel's field draws its own
     * (composing/input.js). @param {HeldWords} said */
    say(said) {
      words.replaceChildren(
        ...said.map((part) => {
          if (typeof part !== "string") {
            const key = box("lf-key-badge lf-held-key", "kbd");
            key.textContent = part.key;
            return key;
          }
          const voiced = document.createElement("span");
          voiced.setAttribute("data-lf-voice", "leaf");
          voiced.textContent = part;
          return voiced;
        }),
      );
    },
    remove() {
      root.remove();
      const sheets = document.adoptedStyleSheets;
      const at = sheets.indexOf(chromeSheet);
      if (adopted && at >= 0) document.adoptedStyleSheets = sheets.toSpliced(at, 1);
    },
  };
}
