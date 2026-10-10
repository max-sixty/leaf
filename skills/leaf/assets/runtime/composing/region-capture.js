/* Area capture is a bounded page interaction; the selector and rasterizer load on demand.
 * Its page scope and early pointer claim suspend page input without changing Draw or
 * Design mode. The passive overlay leaves current target hit tests intact. Captures
 * enter the same anchored draft and media admission path as other attached images.
 */
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
import { onStanding } from "../focus.js";
import { bannerControlDoor } from "../banner-toolbar.js";
import { notice } from "../notifications.js";

export function createRegionCapture({
  parent,
  visibleTargets,
  openComposerWithMedia,
  closeTargetPicker,
  closeReactionMode,
}) {
  let opening = false;
  let selector = null;
  let claimedPointer = null;
  let throughClick = false;
  const active = () => opening;
  const claim = (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
  };
  // Register before Drawing and Aim mount. Paint is pointer-transparent, so selection
  // never occludes the actual page targets that anchor confirmation reads.
  for (const type of ["pointerdown", "pointermove", "pointerup", "pointercancel"])
    document.addEventListener(
      type,
      (event) => {
        // A claimed drag owns its compatibility mouse events, even after release.
        // The next primary press starts a new gesture, including on a chrome control.
        // A timer cannot delimit that ownership: its work may outlive the next tap.
        if (type === "pointerdown" && event.isPrimary) throughClick = false;
        const held = event.pointerId === claimedPointer;
        if (!held && (!selector || leafSurface(event.composedPath()[0]))) return;
        if (type === "pointerdown") {
          if (!event.isPrimary || event.button !== 0) return;
          claimedPointer = event.pointerId;
          throughClick = true;
          document.documentElement.setPointerCapture(event.pointerId);
        }
        claim(event);
        selector?.pointer(event);
        if (held && (type === "pointerup" || type === "pointercancel"))
          claimedPointer = null;
      },
      { capture: true },
    );
  for (const type of ["mousedown", "mouseup", "click", "dblclick", "auxclick"])
    document.addEventListener(
      type,
      (event) => {
        if (
          !pressIsKeyboardActivation(event) &&
          (throughClick || (selector && !leafSurface(event.composedPath()[0])))
        )
          claim(event);
      },
      { capture: true },
    );

  // Native editing elsewhere is a new task. Keep the focus the user just chose.
  onStanding((node) => {
    if (
      selector &&
      node &&
      node !== document.body &&
      !closestAcross(
        node,
        ".lf-banner, .lf-banner-menu, .lf-command-reference, .lf-region-capture",
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
    description: "Select an area of the page and attach its image to a comment",
    touch: "Capture area",
    retainStanding: true,
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
          returnTo: bannerControlDoor(),
        });
        document.documentElement.setAttribute("data-lf-region-capture", "");
        removeScope = pageScope("region capture", {
          title: "In area capture",
          escape: "inner",
          at: () => Boolean(selector),
          claims: allButCommandReference,
          rows: selector.rows,
        });
        await selector.done;
      } catch (error) {
        selector?.cancel();
        notice(`Could not open area capture — ${error.message}`);
      } finally {
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
