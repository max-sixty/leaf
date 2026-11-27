// Compiled from text-width.ts by build/typescript.mjs; edit that file.
/* The width text takes in a font, measured on one canvas this module keeps and never
 * adds to a document, so a widget can fit a label before it draws it. */

import { canvas2D } from "./canvas.js";

let measuring = null;

/** The advance width of `text` in pixels, set in a CSS `font` shorthand. */
export function textWidth(text, font) {
  measuring ??= canvas2D(document.createElement("canvas"));
  measuring.font = font;
  return measuring.measureText(text).width;
}
