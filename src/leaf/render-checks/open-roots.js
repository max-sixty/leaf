/* Which trees are the page, for the readings that answer for what a widget renders
 * rather than for what it declares.
 *
 * Every open root, found by walking rather than read off the registry's x-shadow list:
 * a root a module attached without declaring one still holds words and code the user
 * has to read, and a reading that asked the registry would look away from exactly the
 * tree nobody vouched for. That is the whole of the difference from the runtime's own
 * `shadowRootsIn`, which answers the document's question — whose words these are — and
 * is right to stop at what a version promised.
 *
 * A reading of only what the browser draws walks `drawnElements` instead, which passes
 * over each subtree the browser doesn't draw as a whole: a hidden tab, a closed
 * disclosure, a long text document's runs out of view, and what `display: none`
 * removes. On a page of thirty 4 MB documents in tabs, that leaves about 900 of its two
 * million elements; asking about every one had two readings hold the main thread for
 * half a second. It asks the browser nothing that would make it style or lay out a
 * skipped subtree (`skipped` in runtime/shadow-tree.js): one look at the first undrawn
 * child of a box says the box skips what it holds, as `skipped` decides, and the rest
 * of its children go unasked.
 *
 * Written once, because it is one claim about the page and two copies of it are two
 * things to keep level. Every probe that crosses a shadow boundary imports it rather
 * than restating it, for the same reason UNMARKABLE_ITEMS imports its two readings
 * from the runtime: what one probe walks and what another walks cannot come apart. */
import { pageDocument, skipped } from "/runtime/check-api.js";

/** @template {Document | ShadowRoot | Element} Root
 * @param {Root} root @returns {(Root | ShadowRoot)[]} */
export const openRoots = (root) => [
  root,
  ...(root instanceof Element && root.shadowRoot ? openRoots(root.shadowRoot) : []),
  ...[...root.querySelectorAll("*")].flatMap((el) =>
    el.shadowRoot ? openRoots(el.shadowRoot) : [],
  ),
];

const DRAWN = { contentVisibilityAuto: true };

/** Every element the browser draws at or under `root`, through the open trees of the
 * hosts it draws, each tree in its own order. An element that draws no box of its own
 * (`display: contents`, a slot) is left out, and what it holds is walked.
 * @param {Element} root @returns {Element[]} */
export function drawnElements(root) {
  /** @type {Element[]} */
  const found = [];
  // `holder` is the drawn box the children stand in, which decides whether they are
  // skipped: a box skips all it holds or none of it, so its first undrawn child
  // answers for the rest. A slotted child stands in its slot instead, so it asks for
  // itself; one no slot takes is never drawn.
  /** @param {Element} parent @param {Element} holder */
  const walk = (parent, holder) => {
    const shadow = parent.shadowRoot;
    if (shadow) within(shadow.firstElementChild, holder, false);
    within(parent.firstElementChild, holder, shadow !== null);
  };
  /** @param {Element | null} child @param {Element} holder @param {boolean} hosted */
  const within = (child, holder, hosted) => {
    // A closed disclosure draws its summary alone, wherever it stands.
    const shut =
      !hosted && holder.localName === "details" && !holder.hasAttribute("open");
    for (; child; child = child.nextElementSibling) {
      if (shut && child.localName !== "summary") continue;
      if (child.checkVisibility(DRAWN)) {
        found.push(child);
        walk(child, child);
        continue;
      }
      if (hosted) {
        if (!child.assignedSlot || skipped(child)) continue;
      } else if (getComputedStyle(holder).contentVisibility !== "visible") return;
      if (getComputedStyle(child).display === "contents") walk(child, holder);
    }
  };
  if (root.checkVisibility(DRAWN)) {
    found.push(root);
    walk(root, root);
  }
  return found;
}

// What the browser draws of the page: one walk two readings can share, as each reading
// of the view and each geometry sample does.
export const drawnPage = () => {
  const page = pageDocument();
  return page ? drawnElements(page) : [];
};
