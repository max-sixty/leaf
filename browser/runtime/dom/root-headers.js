// Compiled from root-headers.ts by build/typescript.mjs; edit that file.
/* The headers packages place over the document, each marked `data-lf-root-header`,
 * whose heights the root landing inset clears. CSS cannot sum heights across
 * independent header owners. Read the actual border boxes so typography and theme
 * changes need no second height declaration. Positioning and local sticky-content
 * offsets remain the package's.
 *
 * A marked element counts while it stands in the page and carries the mark, so a
 * module that stops placing its header over the document takes the mark off, and one
 * that removes the header withdraws it with the node; one arrival watch
 * (`watchRootHeaders`, started at installation) hears both.
 *
 * A header the page itself fixes or sticks at the window's top is the page's: Leaf
 * doesn't look for it, and the page gives its targets `scroll-margin-top`
 * (page-layout.md). Rejected: hit-testing the window's top for such a header and
 * starting Leaf's sticky-header slot below it, a reading on every layout, resize and
 * scroll end for the few pages with one (the user's decision). */
import { afterScript } from "../base/rendering.js";
import { sizeObserver } from "../lib/frame-pass.js";
import { watchArrivals } from "./arrivals.js";
import { removeRuntimeRootStyle, setRuntimeRootStyle } from "../state/root-state.js";

const ROOT_HEADER = "data-lf-root-header";

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
const sizes = sizeObserver(syncRootHeaders);

// Reserve each marked header's height in document landings while it stands marked.
// Independent headers add their heights.
export function watchRootHeaders() {
  watchArrivals(`[${ROOT_HEADER}]`, [ROOT_HEADER], {
    arrive(header) {
      // Offered again as what stands beside it changes, which changes nothing here.
      if (rootHeaders.has(header)) return;
      rootHeaders.add(header);
      sizes.observe(header, { box: "border-box" });
      syncRootHeaders();
    },
    leave(header) {
      sizes.unobserve(header);
      rootHeaders.delete(header);
      syncRootHeaders();
    },
  });
}
