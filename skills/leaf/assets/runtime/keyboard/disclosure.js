/* This module owns the shared disclosure bindings: which presses open and close a
 * disclosable element, given where it stands. */
import { PRESS } from "./bindings.js";

let publishedDisclosure;
export const DISCLOSE = (...args) => publishedDisclosure(...args);

export function createDisclosure({ disclosed, inChrome }) {
  publishedDisclosure = (el) => {
    const open = disclosed(el);
    if (open === null) return [...PRESS, "ArrowLeft", "ArrowRight"];
    return inChrome(el) ? PRESS : [...PRESS, open ? "ArrowLeft" : "ArrowRight"];
  };
}
