/* Cross-feature page geometry invalidation.
 *
 * This object owns the shared scroll/resize doors and the one response-bar placement
 * frame. Feature state and paint enter as fixed constructor capabilities; no feature
 * imports the thread presenter to request a refresh.
 *
 * `pageScrolled` runs on every scroll event, so each capability it calls writes only
 * what changed (lib/keeps.js). Target paint and the design legend stand in the planes of
 * what carries their targets (readings/target-paint-geometry.js, `paintStand`), where the browser
 * moves them with every scroll, so a scroll finds nothing to write unless it changed
 * what the paint stands over. `pageShifted` answers layout, which moves the legend's
 * targets too.
 */

import { watchScrolls } from "../dom/arrivals.js";
import { cancelRender, nextRender } from "../lib/frame-pass.js";
import { coarsePointer } from "../base/pointer.js";
import { LAYOUT } from "../lib/widget-events.js";
import { keepsOnOne, keepsText } from "../lib/keeps.js";
import { RUNTIME_PAINT_ATTRIBUTE } from "../base/page-paint.js";
import { elementFromPointAcross, leafSurface } from "../readings/passages.js";
import { WORKS } from "../dom/control-selectors.js";
import { closestAcross } from "../lib/shadow-tree.js";

/** @typedef {ReturnType<typeof import("../annotations/design.js").createDesignMode>} DesignMode */
/** @param {{refreshAnchorHover?: (() => unknown) | undefined,
 * aim: {isOn: ReturnType<typeof import("../annotations/composing/aim.js").createAim>["aimIsOn"],
 * target: ReturnType<typeof import("../annotations/composing/aim.js").createAim>["aimedTarget"]},
 * pointer: typeof import("../base/pointer.js").pointerAt,
 * designMode: Pick<DesignMode, "active" | "target" | "inspectElement" | "name">,
 * pointerModeActive: () => boolean,
 * targetPaint: Pick<typeof import("../readings/target-paint.js"), "clearAim" | "geometryChanged" | "labelAim" | "paintAim" | "shifted">,
 * shiftDrawings: () => unknown, queueLegend: DesignMode["queueLegend"],
 * legendScrolled: DesignMode["legendScrolled"],
 * activeActionAnchor: () => import("../../types/domain.js").Anchor | null,
 * refreshActionBar: () => unknown}} dependencies */
export function createPageGeometry({
  refreshAnchorHover,
  aim,
  pointer,
  designMode,
  pointerModeActive,
  targetPaint,
  shiftDrawings,
  queueLegend,
  legendScrolled,
  activeActionAnchor,
  refreshActionBar,
}) {
  let actionFrame = 0;
  /** @type {ReturnType<typeof watchScrolls> | null} */
  let mounted = null;

  function aimTarget() {
    if (aim.isOn()) return aim.target();
    // Design mode's box and name follow a hovering pointer. A finger does not hover: its
    // last tap is not where it stands, and a box left there follows every scroll.
    const at = pointer();
    if (designMode.active() && at.x >= 0 && !coarsePointer.matches)
      return designMode.target(document.elementFromPoint(at.x, at.y));
    return null;
  }

  // Aim paint is synchronous: the keydown that arms the page and the press that follows
  // may be one gesture, so a scheduled frame could leave the visible promise behind it.
  // The hand where an armed press takes an item stands on the element under the pointer
  // (chrome.css), as a mark's does (annotations/anchor-paint.js), so a crossing restyles what that
  // element holds rather than all `body` does; a control keeps its own cursor.
  const paintItemHand = keepsOnOne(RUNTIME_PAINT_ATTRIBUTE.overItem);
  // The crosshair of a mode that takes presses on the whole plane, Draw mode or Capture
  // area, stands there too (integration.css), on the element inside a widget's tree
  // where the pointer is over one, so a widget's control shows it, and never on Leaf's
  // own surfaces, which keep their gestures and their cursors. Capture area claims the
  // pointer's moves before the aim hears them, so it asks for this one itself.
  const paintCrosshair = keepsOnOne(RUNTIME_PAINT_ATTRIBUTE.crosshair);
  function refreshCrosshair() {
    const at = pointer();
    const under =
      pointerModeActive() && at.x >= 0 ? elementFromPointAcross(at.x, at.y) : null;
    paintCrosshair(under && !leafSurface(under) ? under : null);
  }
  function refreshAim() {
    refreshCrosshair();
    const target = aimTarget();
    const aimed = target?.element ?? null;
    const at = pointer();
    const takes = aimed && !closestAcross(elementFromPointAcross(at.x, at.y), WORKS);
    paintItemHand(takes ? document.elementFromPoint(at.x, at.y) : null);
    const shown = target && targetPaint.paintAim(target.element, target.surface);
    if (!shown) {
      targetPaint.clearAim();
      paintInspect(null);
      return;
    }
    paintInspect(designMode.active() ? target : null);
  }

  // The design name stands at the aim box's corner, in its planes (readings/target-paint.js,
  // `labelAim`).
  /** @param {ReturnType<typeof aimTarget>} target */
  function paintInspect(target) {
    const inspect = designMode.inspectElement;
    inspect.classList.toggle("lf-shown", Boolean(target));
    if (!target) return;
    const name = target.anchor.part
      ? `${target.anchor.part} · ${designMode.name(target.element)}`
      : designMode.name(target.element);
    keepsText(inspect, name);
    targetPaint.labelAim(inspect);
  }

  function queueActionPlacement() {
    if (actionFrame) return;
    actionFrame = nextRender(() => {
      actionFrame = 0;
      refreshActionBar();
    });
  }

  // A scroll moves what stands under the pointer and which paint its cuts show; the
  // design legend stands in the planes that carry it, so it steps only its tags.
  function pageScrolled() {
    refreshAnchorHover?.();
    refreshAim();
    targetPaint.shifted();
    shiftDrawings();
    legendScrolled();
    if (activeActionAnchor()) queueActionPlacement();
  }

  // Layout moves what the legend names as well.
  function pageShifted() {
    pageScrolled();
    queueLegend();
  }

  function invalidate() {
    targetPaint.geometryChanged();
  }

  const onResize = () => {
    invalidate();
    pageShifted();
  };

  function mount() {
    if (mounted) return;
    // Scroll does not bubble: one door hears the root, nested page scrollers such as
    // boards and code blocks, and scrollers inside a widget's shadow stage.
    mounted = watchScrolls(pageScrolled);
    document.addEventListener(LAYOUT, pageShifted);
    addEventListener("resize", onResize, { passive: true });
  }

  function destroy() {
    if (!mounted) return;
    mounted();
    mounted = null;
    document.removeEventListener(LAYOUT, pageShifted);
    globalThis.removeEventListener("resize", onResize);
    if (actionFrame) cancelRender(actionFrame);
    actionFrame = 0;
    targetPaint.clearAim();
    paintInspect(null);
    paintItemHand(null);
    paintCrosshair(null);
  }

  return {
    mount,
    destroy,
    refreshAim,
    refreshCrosshair,
    invalidate,
    pageShifted,
  };
}
