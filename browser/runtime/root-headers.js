/* The headers packages declare over the document (`registerRootHeader`), whose heights
 * the root landing inset clears. CSS cannot sum heights across independent header
 * owners. Read the actual border boxes so typography and theme changes need no second
 * height declaration. Positioning and local sticky-content offsets remain the
 * package's.
 *
 * A header the page itself fixes or sticks at the window's top is the page's: Leaf
 * doesn't look for it, and the page gives its targets `scroll-margin-top`
 * (page-layout.md). Rejected: hit-testing the window's top for such a header and
 * starting Leaf's sticky-header slot below it, a reading on every layout, resize and
 * scroll end for the few pages with one (the user's decision). */
import { afterScript, sizeObserver } from "./rendering.js";
import { whileConnected } from "./arrivals.js";
import { removeRuntimeRootStyle, setRuntimeRootStyle } from "./root-state.js";

/** @type {Set<Element>} */
const rootHeaders = new Set();
const paintRootHeaders = () => {
  const height = [...rootHeaders]
    .filter((header) => header.isConnected)
    .reduce((total, header) => total + header.getBoundingClientRect().height, 0);
  const root = document.documentElement;
  if (height) setRuntimeRootStyle(root, "--lf-root-headers", `${height}px`);
  else removeRuntimeRootStyle(root, "--lf-root-headers");
};
const syncRootHeaders = () => afterScript(paintRootHeaders);

/** Reserve a header's height in document landings while it is connected. Independent
 * headers add their heights. Call the returned stop when a header changes to local
 * navigation; removing and reconnecting the node otherwise withdraws and restores it. */
/** @param {Element} header */
export function registerRootHeader(header) {
  return whileConnected(header, () => {
    rootHeaders.add(header);
    const size = sizeObserver(syncRootHeaders);
    size.observe(header, { box: "border-box" });
    syncRootHeaders();
    return () => {
      size.disconnect();
      rootHeaders.delete(header);
      syncRootHeaders();
    };
  });
}
