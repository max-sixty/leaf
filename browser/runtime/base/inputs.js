/* The module face of the input clock that delivery starts before first paint. */
import "./document-inputs.js";
export const inputs = /** @type {DocumentInputs} */ (
  Reflect.get(window, Symbol.for("leaf.inputs"))
);
