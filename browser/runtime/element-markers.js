/* The marks the runtime writes on words and presses of its own that the library's
 * control constructors don't build (lib/controls.js): a box of words it wrote, and a
 * press that is content of its own. They load without Leaf's runtime; a host without
 * Leaf simply does not interpret its markers. */
import { keeps } from "./lib/keeps.js";
import { actionClass } from "./lib/control-faces.js";
import { elementDirective } from "./lib/controls.js";

// Words an upgrade wrote, which the page's authored source lacks: the `wrote` reading
// leaves them out, and they are a passage cell of their own. `says` is whether they
// are the page speaking (data-lf-said, quotable even inside chrome), a copy of words
// the page says elsewhere ("echo", data-lf-echo), or neither; widget-elements.js,
// control-labels.js says why each answer matters and why none is assumed.
/**
 * @template {Element} T
 * @param {T} node
 * @param {{says?: boolean | "echo"}} [options]
 * @returns {T}
 */
export const generatedElement = (node, { says } = {}) => {
  if (typeof says !== "boolean" && says !== "echo")
    throw new TypeError(
      `Say whether these words are the page speaking: ` +
        `true, false, or "echo" for a copy of words it says elsewhere`,
    );
  keeps(node, "data-lf-gen", "1");
  node.toggleAttribute("data-lf-said", says === true);
  node.toggleAttribute("data-lf-echo", says === "echo");
  return node;
};

// A press that is content of its own, such as a message's picture, which the page's
// readings treat as the message's words rather than Leaf's apparatus: it wears its
// role's face and the press's mark, and none of a generated control's (`lf-ui`,
// `data-lf-gen`).
/** @template {Element} T @param {T} node @param {LeafActionRole} role @param {string} [cls] @returns {T} */
export const offerContentElement = (node, role, cls) => {
  keeps(node, "class", actionClass(role, cls));
  if (node instanceof HTMLButtonElement) keeps(node, "type", "button");
  keeps(
    node,
    "data-lf-offer",
    node instanceof HTMLButtonElement ? node.type : node.localName,
  );
  return node;
};

export const generated = elementDirective("generated", generatedElement);
