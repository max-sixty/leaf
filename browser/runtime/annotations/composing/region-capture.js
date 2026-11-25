/* Area capture is a bounded page interaction; the selector and rasterizer load on demand.
 * Its page scope and early pointer/touch claim suspend page input without changing
 * Draw or Design mode. The passive overlay leaves current target hit tests intact. Captures
 * enter the same anchored draft and media admission path as other attached images.
 */
import { describeFailure } from "../../lib/exception.js";
import {
  pageCommand,
  pageScope,
  allButCommandReference,
} from "../../dom/keyboard/register.js";
import { paintKeys } from "../../dom/keyboard/scopes.js";
import { anchoringIsReady } from "../../readings/anchor-resolution.js";
import { offlineInteractive } from "../../state/context.js";
import { retainUserIntent } from "../../dom/user-intent.js";
import { leafSurface, elementFromPointAcross } from "../../readings/passages.js";
import { pressIsKeyboardActivation } from "../../base/pointer.js";
import { onCurrentLocation, pressHolds, pressRecords } from "../../dom/focus.js";
import { raiseError } from "../../transport/errors.js";
import { closestAcross } from "../../lib/shadow-tree.js";

/** @param {Omit<import("./region-selector.js").RegionSelectorOptions, "returnTo"> & {
 * refreshCrosshair: () => void, closeTargetPicker: () => void,
 * closeReactionMode: () => void}} options */
export function createRegionCapture({
  refreshCrosshair,
  parent,
  visibleTargets,
  openComposerWithMedia,
  closeTargetPicker,
  closeReactionMode,
}) {
  let opening = false;
  /** @type {ReturnType<typeof import("./region-selector.js").createRegionSelector> | null} */
  let selector = null;
  // A claimed drag owns its compatibility mouse events, even after release, for as long
  // as the press lasts (dom/focus.js, `pressRecords`), and the next primary press starts a
  // new gesture, including on a chrome control. A timer cannot delimit that ownership:
  // its work may outlive the next tap.
  /** @type {import("../../dom/focus.js").PressRecords<true>} */
  const claimed = pressRecords();
  const active = () => opening;
  /** @param {Event} event */
  const claim = (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
  };
  // Preventing pointer defaults and touch-action stop page input, but Chromium can
  // still recognize a fling that consumes the next tap. Consume the native touch
  // gesture at its start; Leaf's controls keep their own native activation.
  /** @param {TouchEvent} event */
  const claimTouch = (event) => {
    if (!leafSurface(event.composedPath()[0])) claim(event);
  };
  // Register before Drawing and Aim mount. Paint is pointer-transparent, so selection
  // never occludes the actual page targets that anchor confirmation reads.
  for (const type of /** @type {const} */ ([
    "pointerdown",
    "pointermove",
    "pointerup",
    "pointercancel",
  ]))
    document.addEventListener(
      type,
      (event) => {
        const held = Boolean(claimed.kept()) && pressHolds(event);
        if (!held && (!selector || leafSurface(event.composedPath()[0]))) return;
        if (type === "pointerdown") {
          if (!event.isPrimary || event.button !== 0) return;
          claimed.keep(event, true);
          // The browser shows the cursor of the element holding the pointer, so the
          // drag goes to the one wearing the crosshair (panel/page-geometry.js), which stays
          // where the press landed until the release.
          (
            elementFromPointAcross(event.clientX, event.clientY) ??
            document.documentElement
          ).setPointerCapture(event.pointerId);
        }
        claim(event);
        selector?.pointer(event);
        // The claim keeps a move from the aim, which moves the crosshair.
        if (type === "pointermove" && !held) refreshCrosshair();
      },
      { capture: true },
    );
  /** @type {readonly ("mousedown" | "mouseup" | "click" | "dblclick" | "auxclick")[]} */
  const mouseEvents = ["mousedown", "mouseup", "click", "dblclick", "auxclick"];
  for (const type of mouseEvents)
    document.addEventListener(
      type,
      (event) => {
        if (
          !pressIsKeyboardActivation(event) &&
          (claimed.kept() || (selector && !leafSurface(event.composedPath()[0])))
        )
          claim(event);
      },
      { capture: true },
    );

  // Native editing elsewhere is a new task. Keep the focus the user just chose.
  onCurrentLocation(
    /** @param {Element | null} node */ (node) => {
      if (
        selector &&
        node &&
        node !== document.body &&
        !closestAcross(
          node,
          ".lf-floating-panel, .lf-command-reference, .lf-region-capture",
        )
      )
        selector.cancel({ restore: false });
    },
  );

  // A different command starts a new interaction. Let it take over before it runs,
  // while the universal command reference can inspect this interaction and return.
  document.addEventListener("lf-command-invoked", ({ detail: { id } }) => {
    if (!id.startsWith("capture.region.") && !id.startsWith("command.reference."))
      selector?.cancel();
  });

  pageCommand({
    id: "capture.region.open",
    keys: [],
    title: "Capture area",
    touch: "Capture area",
    menu: "annotate",
    retainCurrentLocation: true,
    when: () => anchoringIsReady() && !offlineInteractive && !opening,
    run: async () => {
      const intent = retainUserIntent();
      opening = true;
      paintKeys();
      /** @type {(() => void) | undefined} */
      let removeScope;
      try {
        const { createRegionSelector } = await import("./region-selector.js");
        if (!intent()) return;
        closeTargetPicker();
        closeReactionMode();
        selector = createRegionSelector({
          parent,
          visibleTargets,
          openComposerWithMedia,
        });
        document.addEventListener("touchstart", claimTouch, {
          capture: true,
          passive: false,
        });
        document.documentElement.setAttribute("data-lf-region-capture", "");
        refreshCrosshair();
        removeScope = pageScope("region capture", {
          title: "Drag an area to capture",
          says: "Capture",
          escape: "inner",
          at: () => Boolean(selector),
          claims: allButCommandReference,
          rows: selector.rows,
        });
        await selector.done;
      } catch (error) {
        selector?.cancel();
        raiseError(`Could not open area capture — ${describeFailure(error)}`);
      } finally {
        document.removeEventListener("touchstart", claimTouch, true);
        selector = null;
        opening = false;
        document.documentElement.removeAttribute("data-lf-region-capture");
        refreshCrosshair();
        removeScope?.();
        paintKeys();
      }
    },
  });
  return { active };
}
