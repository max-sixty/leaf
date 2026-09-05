/* This site's layer: the shipped runtime, with a session in front of it.
 *
 * A page asks for /leaf.js. This remains the one door through which the static host
 * puts a session in front of the layer without touching a page or the runtime;
 * /runtime.js is the vendored entry file byte for byte.
 *
 * These are dynamic imports because the order is a dependency, not presentation.
 * /session.js starts reading the page's seed files and installs its in-tab /api/state
 * responder before the runtime asks. The responder waits for those files when asked,
 * so their reads overlap the runtime graph and widget modules. Published example
 * versions also get /sitenote.js last; product pages are Leaf documents in their own
 * right and do not need the example label.
 */
await import("/session.js");
await import("/runtime.js");
if (/^\/examples\/[a-z0-9-]+\/versions\/v[1-9]\d*\.html$/.test(location.pathname))
  await import("/sitenote.js");
