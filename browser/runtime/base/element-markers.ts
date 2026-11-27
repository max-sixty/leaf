/* The marks the runtime writes on words and presses of its own that the library's
 * control constructors don't build (lib/controls.js): a box of words it wrote, and a
 * press that is content of its own. */
import { keeps } from "../lib/keeps.js";
import { actionClass } from "../lib/control-faces.js";

// A box of words the runtime wrote, which the page's authored source lacks: the
// `wrote` reading leaves them out, and they are a passage cell of their own
// (dom/control-labels.js). A package marks its own words the same way, with the
// attributes themselves (module-plain-elements.md, "Words it writes").
export const generatedElement = <T extends Element>(node: T): T => {
  keeps(node, "data-lf-gen", "1");
  return node;
};

// A press that is content of its own, such as a message's picture, which the page's
// readings treat as the message's words rather than Leaf's apparatus: it wears its
// role's face and the press's mark, and none of a generated control's (`lf-ui`,
// `data-lf-gen`).
export const offerContentElement = <T extends Element>(
  node: T,
  role: LeafActionRole,
  cls?: string,
): T => {
  keeps(node, "class", actionClass(role, cls));
  if (node instanceof HTMLButtonElement) keeps(node, "type", "button");
  keeps(
    node,
    "data-lf-offer",
    node instanceof HTMLButtonElement ? node.type : node.localName,
  );
  return node;
};
