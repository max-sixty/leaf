/* Area capture is a bounded page interaction; the selector and rasterizer load on demand.
 * Its page scope and early pointer/touch claim suspend page input without changing
 * Draw or Design mode. The passive overlay leaves current target hit tests intact. Captures
 * enter the same anchored draft and media admission path as other attached images.
 */
import { describeFailure } from "../exception.js";
import {
  pageCommand,
  pageScope,
  allButCommandReference,
} from "../keyboard/register.js";
import { paintKeys } from "../keyboard/scopes.js";
import { anchoringIsReady } from "../anchor-resolution.js";
import { offlineInteractive } from "../context.js";
import { retainUserIntent } from "../user-intent.js";
import { leafSurface, closestAcross } from "../passages.js";
import { pressIsKeyboardActivation } from "../pointer.js";
import { onCurrentLocation, pressHolds, pressRecords } from "../focus.js";
import { raiseError } from "../errors.js";

export function createRegionCapture({
  parent,
  visibleTargets,
  openComposerWithMedia,
  closeTargetPicker,
  closeReactionMode,
}) {
  let opening = false;
  let selector = null;
  // A claimed drag owns its compatibility mouse events, even after release, for as long
  // as the press lasts (focus.js, `pressRecords`), and the next primary press starts a
  // new gesture, including on a chrome control. A timer cannot delimit that ownership:
  // its work may outlive the next tap.
  const claimed = pressRecords();
  const active = () => opening;
  const claim = (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
  };
  // Preventing pointer defaults and touch-action stop page input, but Chromium can
  // still recognize a fling that consumes the next tap. Consume the native touch
  // gesture at its start; Leaf's controls keep their own native activation.
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
          document.documentElement.setPointerCapture(event.pointerId);
        }
        claim(event);
        selector?.pointer(event);
      },
      { capture: true },
    );
  for (const type of ["mousedown", "mouseup", "click", "dblclick", "auxclick"])
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
  onCurrentLocation((node) => {
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
  });

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
        removeScope = pageScope("region capture", {
          title: "Drag an area to capture",
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
        removeScope?.();
        paintKeys();
      }
    },
  });
  return { active };
}
