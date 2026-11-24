/* The width text takes in a font, measured on one canvas this module keeps and never
 * adds to a document, so a widget can fit a label before it draws it. */

import { canvas2D } from "./canvas.js";

/** @type {ReturnType<typeof canvas2D> | null} */
let measuring = null;

/** The advance width of `text` in pixels, set in a CSS `font` shorthand. */
/** @param {string} text @param {string} font */
export function textWidth(text, font) {
  measuring ??= canvas2D(document.createElement("canvas"));
  measuring.font = font;
  return measuring.measureText(text).width;
}
