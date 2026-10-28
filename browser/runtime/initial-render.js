/* Parser delivery renders each package's retained view before the first paint.
   A module reads the same view and returns its template from its live render;
   later markup initializes it on demand. Source copies and original node routes
   belong to the early coordinator (prepaint.js).

   `initialRender` also loads in any document (portable-api.js). Where no coordinator
   ran, as on a page without Leaf, nothing drew before the first paint, so the widget's
   own producer draws now, handed tools that write only the widget's own markup: a
   control keeps its class, type and name, and none of the marks Leaf's theme and
   readings key on (`lf-ui`, a role's face, `data-lf-gen`, `data-lf-offer`), which
   nothing reads there. */
import { render } from "/vendor/lit.js";
import { tabStore } from "./tab-store.js";

// Whether a coordinator draws this document's x-initial widgets before its first
// paint, as on a Leaf page. A widget that also runs off Leaf imports its producer only
// where none does, so a Leaf page fetches nothing it doesn't run.
export const drawsFirst = () => Boolean(document.documentElement.lfInitial);

const coordinator = (node) =>
  node.ownerDocument?.documentElement?.lfInitial ?? document.documentElement.lfInitial;

const offerElement = (node, cls) => {
  if (node instanceof HTMLButtonElement && !node.hasAttribute("type"))
    node.setAttribute("type", "button");
  if (cls) node.classList.add(...cls.split(" ").filter(Boolean));
  return node;
};
// `label` names the press, as prepaint.js's constructors take it: a symbol or mark says
// it as its accessible name and tooltip, and `offerAction` writes a worded role's words.
const offerActionElement = (node, role, cls, label, { title = label } = {}) => {
  offerElement(node, cls);
  if (label !== undefined && (role === "symbol" || role === "mark")) {
    node.setAttribute("aria-label", label);
    node.setAttribute("title", title);
  }
  return node;
};
const offerAction = (role, cls, label, options) => {
  const node = offerActionElement(
    document.createElement("button"),
    role,
    cls,
    label,
    options,
  );
  if (label !== undefined && role !== "symbol" && role !== "mark")
    node.textContent = label;
  return node;
};
// The producer tools a widget that also runs off Leaf may use, in the shapes
// prepaint.js gives them; the others stay Leaf's.
const plainTools = (host) => ({
  tabStore,
  offerElement,
  offerActionElement,
  offerAction,
  authoredBody(node) {
    node.append(...host.childNodes);
    return node;
  },
});

/** The drawing delivery made of `host` before the first paint, or, where Leaf drew
 * nothing, the one `draw` makes now: the producer the widget's initial bundle
 * registers, which a widget that also runs off Leaf passes. */
export function initialRender(host, draw) {
  const leaf = coordinator(host);
  if (leaf) return leaf.paint(host);
  const drawing = draw(host, plainTools(host));
  if (drawing !== null) render(drawing.render(), drawing.root ?? host, { host });
  return drawing;
}
export const initialOrigin = (node) => coordinator(node).origin(node) ?? node;
export const initialParent = (node) => coordinator(node).parent(node);
export const authoredBody = (host) => coordinator(host).authoredBody(host);
export const initialSource = (node) => coordinator(node).reading(node);
export const restoreInitialSource = (root) => coordinator(root).restoreSource(root);
// What the author wrote: the early coordinator restores original widget sources
// before copying and takes off its marks and delivery's placeholders (version.js).
export const unmarkedCopy = (node) => coordinator(node).authoredCopy(node);
export const fragmentId = (fragment) =>
  document.documentElement.lfInitial.fragmentId(fragment);
