/* The width text takes in a font, measured on one canvas this module keeps and never
 * adds to a document, so a widget can fit a label before it draws it. */

/** @type {CanvasRenderingContext2D | null} */
let measuring = null;

/** The advance width of `text` in pixels, set in a CSS `font` shorthand. */
/** @param {string} text @param {string} font */
export function textWidth(text, font) {
  measuring ??= document.createElement("canvas").getContext("2d");
  if (!measuring) throw new Error("The browser could not create a 2D canvas context");
  measuring.font = font;
  return measuring.measureText(text).width;
}
