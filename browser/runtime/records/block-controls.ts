/* A control the runtime stands over one of the page's blocks: Copy at a code block's
   corner (code-copy.js) and a heading's link (heading-links.js).

   A document block's control stands in chrome, so the page's own sibling and child
   selectors keep matching what the page wrote. CSS anchors keep it on the block without
   wrapping authored nodes or moving them on arrival: `aimControl` names the block as
   the control's `position-anchor`, as a heading's link does only while it shows
   (heading-links.js), and the control's rules place it with `anchor()` against that
   block. The control passes under the sticky headers the page declares
   over its block, as the block's own words do, standing in the frames that cut every
   box following scrolled content (dom/css-anchors.js, `headerLevels`), so a block scrolled
   under a stuck toolbar offers no control over the toolbar's.
   Document controls share one stable chrome child, including their clipping frames.
   Making every control a sibling of transient chrome lets a new margin measurement
   invalidate structural selectors on every block's control in a long page.
   A control a widget stands inside its own tree uses the anchor alone (`anchorControl`,
   `aimControl`), since the widget's tree is where its hover and focus are read.

   Read every block before writing any control (`anchorControl`, `headerLevels`), since
   naming an anchor and connecting a control change layout. */
import {
  anchorBox,
  anchorReading,
  cutFrames,
  headerLevels,
  nameAnchor,
  anchorView,
  refreshAnchorView,
} from "../dom/css-anchors.js";
import { chromeRoot } from "../base/chrome.js";
import { focusDestination } from "../dom/focus.js";
import { move } from "../dom/dom-move.js";
import { keepsHidden, layoutPx } from "../lib/keeps.js";
import { nextRender } from "../lib/frame-pass.js";
import { skipped } from "../lib/shadow-tree.js";

const home = document.createElement("div");
home.className = "lf-block-controls";
// The frames each document control stands in, under its block's sticky headers.
const cuts = new WeakMap<HTMLElement, ReturnType<typeof cutFrames>>();
const makeCut = () => {
  const frame = document.createElement("div");
  frame.className = "lf-block-control-cut";
  return frame;
};
// Stands a document control in the frames its block's headers cut (`headerLevels`),
// read again each time the control is revealed and once a frame after a resize, since a
// header can come, go or change height while the control shows or while it hides.
const placed = new Map<HTMLElement, Element>(); // document control → its block
// The controls other chrome keeps clear of where they stand (`blockControlBoxes`).
const footprints = new WeakSet<HTMLElement>();
let restanding = 0;
addEventListener("resize", () => {
  restanding ||= nextRender(() => {
    restanding = 0;
    // A hidden panel's old layout is invalid after resize. Reading its cuts would
    // force the browser to lay out each skipped subtree; revealControl reads them
    // when the user next reveals the control. Read every shown block before writing.
    const read = [...placed]
      .filter(([, block]) => !skipped(block))
      .map(([control, block]) => ({ control, block, levels: headerLevels(block) }));
    for (const { control, block, levels } of read)
      standInChrome(control, block, levels);
  });
});

/** Where each document control with a footprint stands over its block, shown or
 * hidden at rest, so a margin pin keeps off it (margin-layout.js, `coverIn`) and
 * takes no press meant for it. Each control's insets are read from its block first,
 * every block before any control is written, since a deck moves and scales its
 * slides with no resize to say so (`readInsets`). */
export function blockControlBoxes() {
  const read = [...placed]
    .filter(([control]) => footprints.has(control) && !control.hidden)
    .map(([control, block]) => ({ control, insets: readInsets(block) }));
  for (const { control, insets } of read) writeInsets(control, insets);
  return read.map(({ control }) => control.getBoundingClientRect());
}

/** Stand `control` over `block` from chrome, cut by `levels`, its block's
 * `headerLevels` read before any control was written. `footprint`, read where the
 * control first stands, says whether other chrome keeps clear of it
 * (`blockControlBoxes`). A control made only when it shows, as a heading's link is,
 * has none, since a pin keeping clear of it would move as the pointer passed. */
export function standInChrome(
  control: HTMLElement,
  block: Element,
  levels: ReturnType<typeof headerLevels>,
  footprint: boolean = true,
) {
  if (footprint && !placed.has(control)) footprints.add(control);
  const frames = cutFrames(
    levels,
    (cuts.get(control) ?? []).map(({ frame }) => frame),
    makeCut,
  );
  cuts.set(control, frames);
  placed.set(control, block);
  if (home.parentNode !== chromeRoot) move(chromeRoot, home, null);
  const outer = frames[0]?.frame;
  if (outer && outer.parentNode !== home) move(home, outer, null);
  const frame = frames.at(-1)?.frame ?? home;
  if (control.parentNode !== frame) move(frame, control, null);
}

/** Whether `block` renders near the window, kept current while the control stands: a
 * control whose block is away is `hidden`, which hides it whatever display its own
 * rules give it (base.css). The caller writes the first reading. */
export function watchNear(control: HTMLElement, block: Element) {
  const place = () => {
    keepsHidden(control, !anchorView(control, block, place));
  };
  return anchorView(control, block, place);
}

/** The reading `aimControl` writes from: whether `block` renders near the window
 * (`watchNear`), and the block's anchor name. */
export function anchorControl<C extends HTMLElement>(control: C, block: Element) {
  return { control, near: watchNear(control, block), anchor: anchorReading(block) };
}

export function aimControl<C extends HTMLElement>({
  control,
  near,
  anchor,
}: {
  control: C;
  near: boolean;
  anchor: ReturnType<typeof anchorReading>;
}) {
  keepsHidden(control, !near);
  const name = nameAnchor(anchor);
  if (control.style.positionAnchor !== name) control.style.positionAnchor = name;
  return control;
}

// The control's anchor insets carry how far `anchor()` reads the block's corner from
// where it shows, and `anchor-size()` its size, which only an engine that leaves
// transforms out makes other than nothing (dom/css-anchors.js, `anchorBox`), such as Firefox
// on a block in a table granted room or a scaled slide. Read whenever the control is
// about to show, and wherever a pin keeps off where it stands at rest
// (`blockControlBoxes`); a control shown as it arrives reads them with the batch's
// other readings.
export function readInsets(block: Element) {
  const box = block.getBoundingClientRect();
  const at = anchorBox(block);
  return {
    dx: box.left - at.left,
    dy: box.top - at.top,
    dw: box.width - at.width,
    dh: box.height - at.height,
  };
}
export function writeInsets(
  control: HTMLElement,
  { dx, dy, dw, dh }: ReturnType<typeof readInsets>,
) {
  for (const [property, length] of Object.entries({
    "--lf-block-control-dx": dx,
    "--lf-block-control-dy": dy,
    "--lf-block-control-dw": dw,
    "--lf-block-control-dh": dh,
  })) {
    control.style.setProperty(property, length ? layoutPx(length) : "");
  }
}
export function revealControl(control: HTMLElement, block: Element) {
  if (cuts.has(control)) standInChrome(control, block, headerLevels(block));
  writeInsets(control, readInsets(block));
  refreshAnchorView(control);
}

/** Let Tab from a document control continue from its block's place in the document,
 * rather than from the control's later place in chrome, until `signal` aborts. */
export function tabFromBlock(
  control: HTMLElement,
  block: Element,
  signal: AbortSignal,
) {
  control.addEventListener(
    "keydown",
    (event) => {
      if (event.key === "Tab") focusDestination(block, "step");
    },
    { signal },
  );
}

// A tap that stands the user on a block reveals its control before the tap's click is
// aimed, so the click lands on a control the press never touched. Only a press that
// began on a shown control presses it; Enter's click carries no press (`detail` 0).
// The last press may have been on markup a revision removes before another press, so
// the path is held weakly.
let pressedPath = new WeakSet();
addEventListener(
  "pointerdown",
  (event) => (pressedPath = new WeakSet(event.composedPath())),
  { capture: true },
);
/** Whether a click on `control` comes from a press that began elsewhere. */
export const pressedElsewhere = (event: MouseEvent, control: Element) =>
  event.detail > 0 && !pressedPath.has(control);

/** Take a document control and its frames out of chrome once its block has left. */
export function releaseControl(control: HTMLElement) {
  control.remove();
  cuts.get(control)?.[0]?.frame.remove();
  cuts.delete(control);
  placed.delete(control);
}
