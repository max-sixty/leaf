/* Leaf's copy control: Web Awesome's copy button, which copies its `value` and shows
 * the result on its own face, a check or a cross where its copy icon stood, and Leaf
 * says the same words in its status line, since focus need not be on the control to
 * have pressed it. Every copy Leaf offers is this one control, so a code block and the
 * floating panel's About rows look and answer alike.
 * A control wrapping a trigger of its own wears that trigger's face
 * instead of the icon. A failed copy remains an error after the control's transient
 * face changes again; Web Awesome announces the outcome itself. */
import { offer } from "./widget-elements.js";
import { notice } from "./notifications.js";
import { raiseError } from "./errors.js";

/** A copy control named `label` that says `success` or `error` once pressed. */
export function copyControl(className, { label = "", success, error }) {
  const copy = offer("wa-copy-button", className);
  if (label) copy.copyLabel = label;
  copy.successLabel = success;
  copy.errorLabel = error;
  copy.tooltip = "none";
  // Web Awesome announces the result; Leaf puts the same words in its status line.
  copy.addEventListener("wa-copy", () => notice(success, { announce: false }));
  copy.addEventListener("wa-error", () => raiseError(error, { announce: false }));
  return copy;
}
