/* Which trees are the page, for the readings that answer for what a widget renders
 * rather than for what it declares.
 *
 * Every open root, found by walking rather than read off the registry's `shadow`
 * list: a root a module attached without declaring one still holds words and code the
 * user has to read, and a reading that asked the registry would look away from exactly
 * the tree nobody vouched for. That is the whole of the difference from the runtime's
 * own `shadowRootsIn`, which answers the document's question — whose words these are —
 * and is right to stop at what a version promised.
 *
 * Written once, because it is one claim about the page and two copies of it are two
 * things to keep level. Every probe that crosses a shadow boundary imports it rather
 * than restating it, so what one probe walks and what another walks cannot come apart. A
 * reading of the page as the user sees it walks `drawnPage` instead, which passes over
 * what the browser skips. */
import { pageDocument } from "/runtime/check-api.js";
import { drawnElements, treesUnder } from "/runtime/lib/shadow-tree.js";

/** @template {Document | ShadowRoot | Element} Root
 * @param {Root} root @returns {(Root | ShadowRoot)[]} */
export const openRoots = (root) => treesUnder(root);

// What the browser draws of the page (`drawnElements` in runtime/lib/shadow-tree.js). Two
// readings can share one walk, as each reading of the view and each geometry sample do.
export const drawnPage = () => {
  const page = pageDocument();
  return page ? drawnElements(page) : [];
};
