/* A control the runtime stands over one of the page's blocks: Copy at a code block's
   corner (code-copy.js), a heading's link (heading-links.js) and a recording's play bar
   (video-controls.js).

   A document block's control stands in chrome, so the page's own sibling and child
   selectors keep matching what the page wrote. CSS anchors keep it on the block without
   wrapping authored nodes or moving them on arrival: `aimControl` names the block as
   the control's `position-anchor`, and the control's rules place it with `anchor()`
   against that block. The control passes under the sticky headers the page declares
   over its block, as the block's own words do, standing in the frames that cut every
   box following scrolled content (css-anchors.js, `headerLevels`), so a block scrolled
   under a stuck toolbar offers no control over the toolbar's.
   Document controls share one stable chrome child, including their clipping frames.
   Making every control a sibling of transient chrome lets a new margin measurement
   invalidate structural selectors on every block's control in a long page.
   A block with a hovered or focused chrome control carries `data-lf-control-active`,
   so the page can keep its own hover or focus reveal active across the separate trees.
   The mark leaves when the control does, including when the block is removed.
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
} from "./css-anchors.js";
import { chromeRoot } from "./chrome.js";
import { focusDestination, onCurrentLocation } from "./focus.js";
import { move } from "./dom-move.js";
import { keepsHidden, layoutPx } from "./keeps.js";
import { nextRender } from "./rendering.js";
import { skipped } from "./shown-box.js";
import { upFrom } from "./shadow-tree.js";

const home = document.createElement("div");
home.className = "lf-block-controls";
// The frames each document control stands in, under its block's sticky headers.
const cuts = new WeakMap();
const makeCut = () => {
  const frame = document.createElement("div");
  frame.className = "lf-block-control-cut";
  return frame;
};
// Stands a document control in the frames its block's headers cut (`headerLevels`),
// read again each time the control is revealed and once a frame after a resize, since a
// header can come, go or change height while the control shows or while it hides.
const placed = new Map(); // document control → its block
const wired = new WeakSet();
let hoveredControl = null;
let focusedControl = null;
const activeBlock = (control) => control && placed.get(control);
const syncActive = (block) => {
  if (block)
    block.toggleAttribute(
      "data-lf-control-active",
      activeBlock(hoveredControl) === block || activeBlock(focusedControl) === block,
    );
};
const setActiveControl = (kind, control) => {
  const previous = kind === "hover" ? hoveredControl : focusedControl;
  if (previous === control) return;
  if (kind === "hover") hoveredControl = control;
  else focusedControl = control;
  syncActive(activeBlock(previous));
  syncActive(activeBlock(control));
};
onCurrentLocation((node) => {
  for (let at = node; at; at = upFrom(at)) {
    if (placed.has(at)) return setActiveControl("focus", at);
  }
  setActiveControl("focus", null);
});
let resized = 0;
addEventListener("resize", () => {
  resized ||= nextRender(() => {
    resized = 0;
    // A hidden panel's old layout is invalid after resize. Reading its cuts would
    // force the browser to lay out each skipped subtree; revealControl reads them
    // when the user next reveals the control. Read every shown block before writing.
    const read = [...placed]
      .filter(([, block]) => !skipped(block))
      .map(([control, block]) => [control, block, headerLevels(block)]);
    for (const [control, block, levels] of read) standInChrome(control, block, levels);
  });
});

/** Stand `control` over `block` from chrome, cut by `levels`, its block's
 * `headerLevels` read before any control was written. */
export function standInChrome(control, block, levels) {
  const previousBlock = placed.get(control);
  const frames = cutFrames(levels, cuts.get(control) ?? [], makeCut);
  cuts.set(control, frames);
  placed.set(control, block);
  if (!wired.has(control)) {
    wired.add(control);
    control.addEventListener("pointerenter", () => setActiveControl("hover", control));
    control.addEventListener("pointerleave", () => {
      if (hoveredControl === control) setActiveControl("hover", null);
    });
  }
  if (previousBlock !== block) {
    syncActive(previousBlock);
    syncActive(block);
  }
  if (home.parentNode !== chromeRoot) move(chromeRoot, home, null);
  if (frames[0] && frames[0].parentNode !== home) move(home, frames[0], null);
  const frame = frames.at(-1) ?? home;
  if (control.parentNode !== frame) move(frame, control, null);
}

/** The reading `aimControl` writes from: whether `block` renders near the window,
 * kept current while the control stands, and the block's anchor name. A control
 * whose block is away is `hidden`, which hides it whatever display its own rules give
 * it (base.css). */
export function anchorControl(control, block) {
  const place = () => {
    keepsHidden(control, !anchorView(control, block, place));
  };
  return {
    control,
    near: anchorView(control, block, place),
    anchor: anchorReading(block),
  };
}

/** @param {ReturnType<typeof anchorControl>} reading */
export function aimControl({ control, near, anchor }) {
  keepsHidden(control, !near);
  const name = nameAnchor(anchor);
  if (control.style.positionAnchor !== name) control.style.positionAnchor = name;
  return control;
}

// The control's anchor insets carry how far `anchor()` reads the block from where it
// shows, which only an engine that leaves transforms out makes other than nothing
// (css-anchors.js, `anchorBox`), such as Firefox on a block in a table granted room.
// Read whenever the control is about to show, since only a shown control needs it; a
// control shown as it arrives reads them with the batch's other readings.
export function readInsets(block) {
  const box = block.getBoundingClientRect();
  const at = anchorBox(block);
  return { dx: box.left - at.left, dy: box.top - at.top };
}
/**
 * @param {HTMLElement} control
 * @param {ReturnType<typeof readInsets>} insets
 */
export function writeInsets(control, { dx, dy }) {
  for (const [property, length] of /** @type {[string, number][]} */ ([
    ["--lf-block-control-dx", dx],
    ["--lf-block-control-dy", dy],
  ])) {
    const value = length ? layoutPx(length) : "";
    if (control.style.getPropertyValue(property) !== value)
      control.style.setProperty(property, value);
  }
}
export function revealControl(control, block) {
  if (cuts.has(control)) standInChrome(control, block, headerLevels(block));
  writeInsets(control, readInsets(block));
  refreshAnchorView(control);
}

/** Let Tab from a document control continue from its block's place in the document,
 * rather than from the control's later place in chrome, until `signal` aborts. */
export function tabFromBlock(control, block, signal) {
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
export const pressedElsewhere = (event, control) =>
  event.detail > 0 && !pressedPath.has(control);

/** Take a document control and its frames out of chrome once its block has left. */
export function releaseControl(control) {
  const block = placed.get(control);
  if (hoveredControl === control) hoveredControl = null;
  if (focusedControl === control) focusedControl = null;
  control.remove();
  cuts.get(control)?.[0]?.remove();
  cuts.delete(control);
  placed.delete(control);
  syncActive(block);
}
