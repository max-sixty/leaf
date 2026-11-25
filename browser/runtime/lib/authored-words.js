/* The words an author wrote in an element, which name it. */
import { labelWords } from "./words.js";

/** The words that name an element, on one line: what its author wrote there, less the
 * words of any element inside it marked `data-lf-gen`, which a widget or Leaf wrote, and
 * of any popover, such as a gloss's explanation, which the element shows but is not
 * called by. A box that isn't drawn inline stands apart from the words beside it, as a
 * tag before an option's words does. A widget names one of its own parts this way where
 * `textContent` would carry those words along and run boxes together.
 * @param {Node} el */
export function authoredWords(el) {
  let words = "";
  /** @param {Node} node */
  const read = (node) => {
    for (const child of node.childNodes) {
      if (child.nodeType === Node.TEXT_NODE) words += /** @type {Text} */ (child).data;
      else if (
        child instanceof Element &&
        !child.hasAttribute("data-lf-gen") &&
        !child.hasAttribute("popover")
      ) {
        const apart = child.isConnected && getComputedStyle(child).display !== "inline";
        if (apart) words += " ";
        read(child);
        if (apart) words += " ";
      }
    }
  };
  read(el);
  return labelWords(words);
}
