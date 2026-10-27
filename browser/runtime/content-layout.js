/* Authored sidebar, sidenote and contents-outline margin content layout after initial parsing, and
   the height of a Layout's sticky header.
   The initial coordinator owns the one computed margin content layout reading, used before first
   paint and adopted here after upgrade. This owner schedules later reads and informs
   annotation geometry and reading-region discovery when that composition changes.
   Imports are inert; boot opens it once for every interactive document. */
import { nextFrame, nextRender, sizeObserver } from "./rendering.js";
import { repaintPage } from "./repaint.js";
import { layoutChanged } from "./widget-elements.js";
import { layoutBox, pageDocument } from "./passages.js";
import { marks } from "./kernel-facts.js";
import { pageControlsChanged } from "./page-controls.js";
// One computed reading seats the rail first without moving the column, then each
// authored margin element on its preferred side, or in flow when there is no room. The
// column's runtime grid offset is removed before measuring, including RTL, while an
// authored offset remains part of its room. --lf-margin-content (layouts.css) declares placement
// preferences; data-lf-margin and the shell's --lf-column-shift publish their geometry,
// and data-lf-beside whether a sidebar page's track stands beside its body.
// Read at most once per frame after widgets upgrade. Every completed read notifies
// the selected annotation owner, including an unchanged or missing column; only a
// changed reading repaints page geometry. Imports never start this document owner.
let marginContentLayoutOpen = false;
let readFinished = null;
let marginContentLayoutPending = 0;
let marginContentLayoutRead = -1;
function marginContentLayoutPass(time) {
  marginContentLayoutPending = 0;
  if (time === marginContentLayoutRead) {
    marginContentLayoutPending = nextFrame(marginContentLayoutPass);
    return;
  }
  marginContentLayoutRead = time;
  readMarginContentLayout();
}
// The Layout's header is read with the margin elements, and its height can change with no
// resize or toggle, as a web font arriving rewraps its title, so its size is watched.
let headSizes = null;
let watchedHead = null;
function watchHead() {
  const header =
    document.documentElement.lfInitial.layoutBox()?.querySelector(":scope > header") ??
    null;
  if (header === watchedHead) return;
  headSizes ??= sizeObserver(() => scheduleMarginContentLayout());
  if (watchedHead) headSizes.unobserve(watchedHead);
  if (header) headSizes.observe(header);
  watchedHead = header;
}
function readMarginContentLayout() {
  const { changed } = document.documentElement.lfInitial.marginContentLayout();
  watchHead();
  if (changed) layoutChanged(pageDocument());
  readFinished?.(changed);
  if (!changed) return;
  repaintPage();
  // A page control may stand where it does by whether the rail stands (page-map-dialog.js).
  pageControlsChanged();
}
// Whether the reading seated the margin's rail beside `main`, the column, rather than
// leaving its rows to pin over the content where the window has no room for it.
export const railStands = (main = layoutBox()) =>
  (main?.getAttribute("data-lf-margin") ?? "").split(" ").includes("rail");
export function scheduleMarginContentLayout() {
  if (marginContentLayoutOpen)
    marginContentLayoutPending ||= nextRender(marginContentLayoutPass);
}
// A revision returns the reader to their place once its document stands, and where that
// place is depends on the margin elements' placements: a sidebar page's track that a revision
// replaced is not yet marked beside its body, so its block would not yet scroll and the
// place would land in the page. The revision reads them first (version.js, `land`); a
// scheduled pass still follows.
export function settleMarginContentLayout() {
  if (marginContentLayoutOpen) readMarginContentLayout();
}
// The same read also says whether each breakout keeps to its holder (prepaint.js,
// `breakouts`). A breakout a revision or a widget inserts, or one a holder reveals (a panel
// losing `hidden`, a disclosure opening), is read in the microtask its arrival queues.
// A holder a class or a script moves or pads anew keeps its reading until the next pass.
const ROOM = marks["x-space"].paint;
const BREAKOUT = `[${ROOM}]`;
const bringsBreakout = (node) =>
  node.nodeType === Node.ELEMENT_NODE &&
  (node.matches(BREAKOUT) || node.querySelector(BREAKOUT) !== null);
function readBreakouts() {
  const { changed } = document.documentElement.lfInitial.breakouts();
  if (!changed) return;
  layoutChanged(pageDocument());
  repaintPage();
}
// A part can replace the Layout box, and a page view can replace its margin
// margin elements. Read either before the frame paints, so its margins stand immediately.
const mayChangeMarginContentLayout = (node) =>
  node.matches(
    'body > main > *, body > main > [data-lf-views="parts"] > *, [data-lf-views-flow="page"] > *',
  );
export function openMarginContentLayout({ onRead }) {
  readFinished = onRead;
  marginContentLayoutOpen = true;
  document.addEventListener("toggle", scheduleMarginContentLayout, { capture: true });
  window.addEventListener("resize", scheduleMarginContentLayout);
  const main = pageDocument();
  if (main)
    new MutationObserver((records) => {
      if (
        records.some(
          (record) =>
            record.type === "attributes" &&
            record.attributeName === "hidden" &&
            mayChangeMarginContentLayout(record.target),
        )
      )
        readMarginContentLayout();
      else if (
        records.some((record) =>
          record.type === "attributes"
            ? bringsBreakout(record.target)
            : [...record.addedNodes].some(bringsBreakout),
        )
      )
        readBreakouts();
    }).observe(main, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: [ROOM, "hidden", "open"],
    });
  readMarginContentLayout();
}
