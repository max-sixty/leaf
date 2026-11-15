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
import { LAYOUT } from "./widget-upgrade.js";
import { keepsOnOne, keepsText } from "./keeps.js";
import { RUNTIME_PAINT_ATTRIBUTE } from "./page-paint.js";
import { closestAcross, elementFromPointAcross, inChrome } from "./passages.js";
import { WORKS } from "./control-selectors.js";
import { isHTML } from "./shadow-tree.js";
import { declaredRoot } from "./shadow.js";

// Whether the point is over `el`'s own words, or in content the user edits there: the
// places a cursor of `auto` draws as anything but the arrow. The caret reading answers
// for a shadow tree only when named, with every tree on the way to it (user-place.js).
// The pointer reaches no further than the host of a tree Leaf does not read, such as a
// page script's own element's (shadow.js, `declaredRoot`), whose words inherit its cursor.
/** @param {Element} el @param {{x: number, y: number}} at */
function wordsAt(el, at) {
  if (isHTML(el) && el.isContentEditable) return true;
  if (el.shadowRoot && !declaredRoot(el)) return true;
  /** @type {ShadowRoot[]} */
  const shadowRoots = [];
  for (let root = el.getRootNode(); root instanceof ShadowRoot;) {
    shadowRoots.push(root);
    root = root.host.getRootNode();
  }
  const node = document.caretPositionFromPoint(at.x, at.y, { shadowRoots })?.offsetNode;
  return node === el || node?.parentNode === el;
}

/** @typedef {ReturnType<typeof import("./design.js").createDesignMode>} DesignMode */
/** @param {{refreshAnchorHover?: (() => unknown) | undefined,
 * aim: {isOn: ReturnType<typeof import("./composing/aim.js").createAim>["aimIsOn"],
 * armed: ReturnType<typeof import("./composing/aim.js").createAim>["armed"],
 * target: ReturnType<typeof import("./composing/aim.js").createAim>["aimedTarget"]},
 * pointer: typeof import("./pointer.js").pointerAt,
 * designMode: Pick<DesignMode, "active" | "target" | "inspectElement" | "name">,
 * targetPaint: Pick<typeof import("./target-paint.js"), "clearAim" | "geometryChanged" | "labelAim" | "paintAim" | "shifted">,
 * shiftDrawings: () => unknown, queueLegend: DesignMode["queueLegend"],
 * legendScrolled: DesignMode["legendScrolled"],
 * activeActionAnchor: () => import("../types/domain.js").Anchor | null,
 * refreshActionBar: () => unknown}} dependencies */
export function createPageGeometry({
  refreshAnchorHover,
  aim,
  pointer,
  designMode,
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

  // The armed page's cursor says whether a press takes anything: the hand where it takes
  // an item, the arrow where it takes nothing, and a control's own cursor on a control.
  // Each stands on the element under the pointer, as a mark's hand does (anchor-paint.js),
  // so arming and moving restyle what that element holds rather than all `body` does: an
  // arrow inherited from `body` restyled 2.4 million elements each time the page armed
  // or disarmed on a page of thirty 4 MB text documents in tabs, 1.0 to 1.2 s in
  // Firefox. The hand stands on the document's element
  // (chrome.css), so a widget's shadow tree keeps any cursor it states.
  //
  // The arrow stands on the innermost element, whose cursor the browser draws
  // (marks.css), and only where it changes what the browser draws: where that element's
  // cursor is `auto` and the pointer is over the element's own words or in content the
  // user edits, the only places `auto` draws anything but the arrow. Over the gap
  // between two blocks, `auto` on the element holding both draws the arrow already, and
  // an arrow stood on that element would restyle all it holds at every crossing.
  const paintItemHand = keepsOnOne(RUNTIME_PAINT_ATTRIBUTE.overItem);
  const paintArrow = keepsOnOne(RUNTIME_PAINT_ATTRIBUTE.armedArrow);
  /** @type {Element | null} */
  let arrowAsked = null;
  /** @param {Element | null} aimed */
  function paintArmedCursor(aimed) {
    const at = pointer();
    const under = aim.armed() ? elementFromPointAcross(at.x, at.y) : null;
    const takes = aimed && under && !closestAcross(under, WORKS);
    paintItemHand(takes ? document.elementFromPoint(at.x, at.y) : null);
    // The arrow answers for the page, which `body` holds; the chrome states its own
    // cursors (chrome.css).
    const bare =
      !takes &&
      under &&
      closestAcross(under, "body") &&
      !inChrome(under) &&
      wordsAt(under, at)
        ? under
        : null;
    if (bare === arrowAsked) return;
    arrowAsked = bare;
    // Asked with no arrow standing, which would answer for what it holds.
    paintArrow(null);
    if (bare && getComputedStyle(bare).cursor === "auto") paintArrow(bare);
  }

  // Aim paint is synchronous: the keydown that arms the page and the press that follows
  // may be one gesture, so a scheduled frame could leave the visible promise behind it.
  function refreshAim() {
    const target = aimTarget();
    paintArmedCursor(target?.element ?? null);
    const shown = target && targetPaint.paintAim(target.element, target.surface);
    if (!shown) {
      targetPaint.clearAim();
      paintInspect(null);
      return;
    }
    paintInspect(designMode.active() ? target : null);
  }

  // The design name stands at the aim box's corner, in its planes (target-paint.js,
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
  }

  return {
    mount,
    destroy,
    refreshAim,
    invalidate,
    pageShifted,
  };
}
