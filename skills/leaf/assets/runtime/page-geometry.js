/* Cross-feature page geometry invalidation.
 *
 * This object owns the shared scroll/resize doors and the one response-bar placement
 * frame. Feature state and paint enter as fixed constructor capabilities; no feature
 * imports the conversation presenter to request a refresh.
 */

import { visualAt } from "./anchor-resolution.js";
import { documentPoint } from "./geometry.js";
import { inChrome } from "./passages.js";

export function createPageGeometry({
  refreshAnchorHover,
  aim,
  pointer,
  design,
  targetPaint,
  shiftDrawings,
  queueLegend,
  activeActionAnchor,
  refreshActionBar,
}) {
  let actionFrame = 0;
  let mounted = false;

  function aimTarget() {
    if (aim.isOn()) {
      const target = aim.target();
      return target
        ? { element: target.element, part: "", surface: target.surface ?? null }
        : null;
    }
    const at = pointer();
    if (design.isOn() && at.x >= 0)
      return design.target(document.elementFromPoint(at.x, at.y));
    return null;
  }

  // Aim paint is synchronous: the keydown that arms the page and the press that follows
  // may be one gesture, so a scheduled frame could leave the visible promise behind it.
  function refreshAim() {
    const target = aimTarget();
    const aimed = target?.element ?? null;
    document.body.classList.toggle("lf-over-item", Boolean(aimed));
    const rect = aimed && targetPaint.paintAim(aimed, target.surface);
    if (!rect) {
      targetPaint.clearAim();
      paintInspect(null);
      return;
    }
    paintInspect(design.isOn() ? target : null, { left: rect.left, top: rect.top });
  }

  // The design name shares the aim box's top-left corner and document plane. It sits
  // above the box where room permits and inside it beneath the banner otherwise.
  function paintInspect(target, corner) {
    const inspect = design.inspectElement;
    inspect.classList.toggle("lf-shown", Boolean(target));
    if (!target) {
      delete inspect.dataset.lfPaintPlane;
      return;
    }
    inspect.dataset.lfPaintPlane = inChrome(target.element) ? "chrome" : "page";
    const name = target.part
      ? `${target.part} · ${design.name(target.element)}`
      : design.name(target.element);
    if (inspect.textContent !== name) inspect.textContent = name;
    const above = corner.top - inspect.offsetHeight - 2;
    const at = documentPoint(
      Math.max(2, corner.left),
      above >= 0 ? above : corner.top + 2,
    );
    inspect.style.left = `${at.left}px`;
    inspect.style.top = `${at.top}px`;
  }

  function queueActionPlacement() {
    if (actionFrame) return;
    actionFrame = requestAnimationFrame(() => {
      actionFrame = 0;
      refreshActionBar();
    });
  }

  function pageShifted() {
    refreshAnchorHover();
    refreshAim();
    targetPaint.shifted();
    shiftDrawings();
    // Sideways widget scrolling changes which item lies under a stationary overlay,
    // while page scrolling may bring previously unpaintable items into view.
    queueLegend();
    if (activeActionAnchor()) queueActionPlacement();
  }

  function traceTarget(target) {
    const part = target ? visualAt(target, { unclaimed: false })?.part : null;
    targetPaint.paintTrace(target, part?.element === target ? part.surface : target);
  }

  const invalidate = () => targetPaint.geometryChanged();

  const onResize = () => {
    targetPaint.geometryChanged();
    pageShifted();
  };

  function mount() {
    if (mounted) return;
    mounted = true;
    // Scroll does not bubble. Capture is the one door shared by the root and nested
    // page scrollers such as boards and code blocks.
    document.addEventListener("scroll", pageShifted, {
      capture: true,
      passive: true,
    });
    addEventListener("resize", onResize, { passive: true });
  }

  function destroy() {
    if (!mounted) return;
    mounted = false;
    document.removeEventListener("scroll", pageShifted, { capture: true });
    globalThis.removeEventListener("resize", onResize);
    if (actionFrame) cancelAnimationFrame(actionFrame);
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
    traceTarget,
  };
}
