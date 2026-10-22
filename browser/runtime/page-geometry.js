/* Cross-feature page geometry invalidation.
 *
 * This object owns the shared scroll/resize doors and the one response-bar placement
 * frame. Feature state and paint enter as fixed constructor capabilities; no feature
 * imports the thread presenter to request a refresh.
 *
 * `pageScrolled` runs on every scroll event, so each capability it calls writes only
 * what changed (keeps.js). Target paint and the design legend stand in the planes of
 * what carries their targets (target-paint-geometry.js, `paintStand`), where the browser
 * moves them with every scroll, so a scroll finds nothing to write unless it changed
 * what the paint stands over. `pageShifted` answers layout, which moves the legend's
 * targets too.
 */

import { watchScrolls } from "./arrivals.js";
import { cancelRender, nextRender } from "./rendering.js";
import { coarsePointer } from "./pointer.js";
import { LAYOUT } from "./widget-elements.js";
import { keepsText } from "./keeps.js";

export function createPageGeometry({
  refreshAnchorHover,
  aim,
  pointer,
  designMode,
  targetPaint,
  visualMarkPaint,
  shiftDrawings,
  queueLegend,
  legendScrolled,
  activeActionAnchor,
  refreshActionBar,
}) {
  let actionFrame = 0;
  let mounted = false;
  let stopScrolls = null;

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
  function refreshAim() {
    const target = aimTarget();
    const aimed = target?.element ?? null;
    document.body.classList.toggle("lf-over-item", Boolean(aimed));
    const shown = aimed && targetPaint.paintAim(aimed, target.surface);
    if (!shown) {
      targetPaint.clearAim();
      paintInspect(null);
      return;
    }
    paintInspect(designMode.active() ? target : null);
  }

  // The design name stands at the aim box's corner, in its planes (target-paint.js,
  // `labelAim`).
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
    visualMarkPaint?.shifted();
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
    visualMarkPaint?.geometryChanged();
  }

  const onResize = () => {
    invalidate();
    pageShifted();
  };

  function mount() {
    if (mounted) return;
    mounted = true;
    // Scroll does not bubble: one door hears the root, nested page scrollers such as
    // boards and code blocks, and scrollers inside a widget's shadow stage.
    stopScrolls = watchScrolls(pageScrolled);
    document.addEventListener(LAYOUT, pageShifted);
    addEventListener("resize", onResize, { passive: true });
  }

  function destroy() {
    if (!mounted) return;
    mounted = false;
    stopScrolls();
    document.removeEventListener(LAYOUT, pageShifted);
    globalThis.removeEventListener("resize", onResize);
    if (actionFrame) cancelRender(actionFrame);
    actionFrame = 0;
    targetPaint.clearAim();
    paintInspect(null);
  }

  return {
    mount,
    destroy,
    refreshAim,
    invalidate,
    pageShifted,
  };
}
