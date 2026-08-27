/* This site's layer: the shipped runtime, with a session in front of it.
 *
 * A page asks for /leaf.js. This remains the one door through which the static host
 * puts a session in front of the layer without touching a page or the runtime;
 * /runtime.js is the vendored entry file byte for byte.
 *
 * These are dynamic imports because the order is a dependency, not presentation.
 * /session.js pauses while it reads the page's seed files and must finish installing
 * its in-tab /api/state responder before the runtime makes its first poll. Static
 * sibling imports may evaluate concurrently across that top-level await; the old
 * runtime-to-entry cycle happened to serialize them, until splitting the runtime into
 * its real owners correctly removed that cycle. /sitenote.js goes last, so a fault in
 * the site's own furniture costs the label rather than the chrome, the panel and every
 * widget on the page.
 */
await import("/session.js");
await import("/runtime.js");
await import("/sitenote.js");
