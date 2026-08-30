/* Which trees are the page, for the readings that answer for what a widget renders
 * rather than for what it declares.
 *
 * Every open root, found by walking rather than read off the registry's x-shadow list:
 * a root a module attached without declaring one still holds words and code the reader
 * has to read, and a reading that asked the registry would look away from exactly the
 * tree nobody vouched for. That is the whole of the difference from the runtime's own
 * `shadowRootsIn`, which answers the document's question — whose words these are — and
 * is right to stop at what a version promised.
 *
 * Written once, because it is one claim about the page and two copies of it are two
 * things to keep level. Every probe that crosses a shadow boundary imports it rather
 * than restating it, for the same reason UNMARKABLE_ITEMS imports its two readings
 * from the runtime: what one probe walks and what another walks cannot come apart.
 *
 * `standalone.js` keeps a walk of its own, and has to: it is served import-free so a
 * BAKE'd copy can be probed from a file:// URL with no module graph behind it. */
export const openRoots = (root) => [
  root,
  ...[...root.querySelectorAll("*")]
    .filter((el) => el.shadowRoot)
    .flatMap((el) => openRoots(el.shadowRoot)),
];
