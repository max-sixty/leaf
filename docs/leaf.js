/* This site's layer: the shipped runtime, with a session in front of it.
 *
 * A page asks for /leaf.js and its widget modules import from the same path, so this is
 * the one door the whole layer comes through — which is what lets a static host put
 * something in front of it without touching a page or the runtime. /runtime.js is the
 * vendored file byte for byte.
 *
 * The order is what each piece needs of the runtime, not a list. /session.js goes in
 * front because the runtime's first poll is a question it has to be there to answer.
 * /sitenote.js needs nothing of it and only writes a label onto the page, so it goes
 * behind — where a fault in the site's own furniture costs the label rather than the
 * chrome, the panel and every widget on the page.
 */
import "/session.js";
export * from "/runtime.js";
import "/sitenote.js";
