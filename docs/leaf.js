/* The product pages' static layer: the shipped runtime with a session in front of it.
 *
 * Product documents still ask for /leaf.js, and /runtime.js remains the vendored entry
 * file byte for byte. Published examples do not enter this adapter: the website Worker
 * sends them through Leaf's canonical Python server and their own vendored layers.
 *
 * These are dynamic imports because the order is a dependency, not presentation.
 * /session.js starts reading the page's seed files and installs its in-tab /api/state
 * responder before the runtime asks. The responder waits for those files when asked,
 * so their reads overlap the runtime graph and widget modules.
 */
await import("/session.js");
await import("/runtime.js");

if (document.querySelector("[data-interaction-gallery]")) {
  await import("/interactions.js");
}
