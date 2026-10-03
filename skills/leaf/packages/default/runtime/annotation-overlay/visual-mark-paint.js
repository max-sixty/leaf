/* Optional persistent element-target marks in Leaf's chrome layer.
 *
 * The selected annotation renderer constructs this painter and supplies resolved
 * targets; it neither resolves anchors nor changes semantic state. Each instance
 * owns its mark nodes, state classes and geometry cache. Scroll moves cached paint;
 * layout, resize, source replacement and target changes rebuild it. Importing this
 * module creates no layer, overlays or scheduled work. */

import { cancelRender, nextRender } from "/runtime/rendering.js";
import { el } from "/runtime/widget-elements.js";
import { keeps } from "/runtime/keeps.js";
import { inChrome } from "/runtime/passages.js";
import {
  SVG_NS,
  paintGeometry,
  paintShape,
  placement,
  standOver,
} from "/runtime/target-paint-geometry.js";

const PROJECTED = "lf-projected-mark";
const STATE_CLASSES = {
  pending: "lf-visual-mark-pending",
  action: "lf-visual-mark-action",
  hover: "lf-visual-mark-hover",
  focus: "lf-visual-mark-focus",
  here: "lf-visual-mark-here",
};

export function createVisualMarkPaint() {
  const layer = el("div", "lf-ui lf-visual-marks");
  layer.setAttribute("aria-hidden", "true");
  let targets = new Map();
  const overlays = new Map();
  let placementFrame = 0;
  let geometryFrame = 0;
  let geometryDirty = false;

  function syncStates() {
    for (const [element, { overlay }] of overlays) {
      const states = targets.get(element)?.states ?? new Set();
      for (const [state, className] of Object.entries(STATE_CLASSES))
        overlay.classList.toggle(className, states.has(state));
    }
  }

  function paintTargets(rebuildGeometry = true) {
    for (const element of [...overlays.keys()])
      if (!targets.has(element)) {
        element.classList.remove(PROJECTED);
        overlays.get(element).overlay.remove();
        overlays.delete(element);
      }

    for (const [element, target] of targets) {
      let record = overlays.get(element);
      const geometry =
        rebuildGeometry || !record ? paintGeometry(target.surface) : record.geometry;
      const placed = placement(target.surface, Boolean(geometry));
      if (!placed) {
        element.classList.toggle(PROJECTED, false);
        if (record) {
          record.geometry = geometry;
          record.shapeKey = "";
          record.overlay.style.display = "none";
        }
        continue;
      }
      if (!record) {
        const overlay = el("div", "lf-ui lf-visual-mark lf-target-paint");
        const shape = document.createElementNS(SVG_NS, "svg");
        shape.classList.add("lf-visual-mark-shape");
        overlay.append(shape);
        layer.append(overlay);
        record = { overlay, shape, geometry: null, shapeKey: "" };
        overlays.set(element, record);
      }
      const { overlay, shape } = record;
      const { rect, shapeKey } = placed;
      element.classList.toggle(PROJECTED, true);
      keeps(overlay, "data-for", element.id || null);
      overlay.classList.toggle("lf-shaped", Boolean(geometry));
      if (
        rebuildGeometry ||
        record.geometry !== geometry ||
        record.shapeKey !== shapeKey
      ) {
        if (geometry) paintShape(shape, geometry, rect);
        else shape.replaceChildren();
        record.geometry = geometry;
        record.shapeKey = shapeKey;
      }
      keeps(overlay, "data-lf-paint-plane", inChrome(element) ? "chrome" : "page");
      standOver(
        overlay,
        rect,
        geometry ? "0" : getComputedStyle(target.surface).borderRadius,
      );
    }
    syncStates();
  }

  function setTargets(next) {
    const nextTargets = new Map(
      [...next]
        .filter((target) => target.states?.size)
        .map((target) => [target.element, target]),
    );
    const identitiesChanged =
      nextTargets.size !== targets.size ||
      [...nextTargets].some(
        ([element, target]) => targets.get(element)?.surface !== target.surface,
      );
    targets = nextTargets;
    const rebuild = identitiesChanged || geometryDirty;
    if (rebuild && geometryFrame) cancelRender(geometryFrame);
    if (rebuild && placementFrame) cancelRender(placementFrame);
    if (rebuild) geometryFrame = placementFrame = 0;
    geometryDirty = false;
    paintTargets(rebuild);
  }

  function shifted() {
    if (placementFrame || geometryFrame || !targets.size) return;
    placementFrame = nextRender(() => {
      placementFrame = 0;
      paintTargets(false);
    });
  }

  function geometryChanged() {
    geometryDirty = true;
    if (placementFrame) cancelRender(placementFrame);
    placementFrame = 0;
    if (geometryFrame || !targets.size) return;
    geometryFrame = nextRender(() => {
      geometryFrame = 0;
      if (!geometryDirty) return;
      geometryDirty = false;
      paintTargets(true);
    });
  }

  return { layer, setTargets, shifted, geometryChanged };
}
