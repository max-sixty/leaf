/* The width text takes in a font, measured on one canvas this module keeps and never
 * adds to a document, so a widget can fit a label before it draws it. */

import { canvas2D } from "./canvas.js";

let measuring: ReturnType<typeof canvas2D> | null = null;

/** The advance width of `text` in pixels, set in a CSS `font` shorthand. */
export function textWidth(text: string, font: string) {
  measuring ??= canvas2D(document.createElement("canvas"));
  measuring.font = font;
  return measuring.measureText(text).width;
}
