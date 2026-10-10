/* A bounded area-selection interaction over the current viewport.
 *
 * The page command owner supplies input and registers this controller's rows with the
 * shared keyboard and banner controls. The overlay only paints: it never intercepts
 * hit testing or introduces a modal. Its outline leaves the selected content clear;
 * instructions and errors belong to the shared controls and notice line. Pointer
 * drags set a rectangle; arrows move it and
 * Shift+arrows resize it, so capturing never requires a drag. The selected pixels stay
 * in viewport coordinates until confirmation, when SnapDOM takes a document-coordinate
 * crop of the live DOM, excluding the selector and shortcut bar. SnapDOM owns cloning,
 * shadow trees, styles, fonts, SVG and rasterization; Leaf owns no renderer.
 * The crop is approximate browser rendering, not privileged access to screen pixels.
 * Known missing images refuse capture instead of attaching a placeholder.
 *
 * The closest containing semantic target at the rectangle's center anchors its comment.
 * A canceled or superseded capture cannot create an attachment. Failed rasterization
 * leaves the rectangle available to retry. Image upload and draft ownership remain the
 * composition input's, including its protection against a draft changing mid-upload.
 */
import { el } from "../widget-elements.js";
import { paintKeys } from "../keyboard/scopes.js";
import { focusDestination, focused, handBack, closeLayer } from "../focus.js";
import { keeps, keepsText } from "../keeps.js";
import { runtime } from "../context.js";
import { nextRender } from "../rendering.js";
import { clamp } from "../rect.js";
import { notice } from "../notifications.js";

const MIN_SIZE = 8;
const STEP = 10;

export function createRegionSelector({
  parent,
  visibleTargets,
  openComposerWithMedia,
  returnTo = null,
}) {
  let settled;
  const done = new Promise((resolve) => (settled = resolve));
  const standing = focused();
  const origin = standing === document.body ? returnTo : standing;
  const overlay = el("div", "lf-ui lf-region-capture");
  overlay.setAttribute("role", "region");
  overlay.setAttribute("aria-label", "Capture area");
  overlay.tabIndex = -1;
  const selection = el("div", "lf-region-selection");
  selection.setAttribute("aria-hidden", "true");
  const status = el("p", "lf-live lf-region-status");
  status.setAttribute("role", "status");
  overlay.append(selection, status);
  let box = {
    x: Math.round(innerWidth * 0.2),
    y: Math.round(innerHeight * 0.2),
    width: Math.round(innerWidth * 0.6),
    height: Math.round(innerHeight * 0.5),
  };
  let drag = null;
  let busy = false;
  let attempt = 0;
  let ended = false;

  function paint() {
    selection.style.left = `${box.x}px`;
    selection.style.top = `${box.y}px`;
    selection.style.width = `${box.width}px`;
    selection.style.height = `${box.height}px`;
    keepsText(status, `${box.width} × ${box.height} pixels`);
    paintKeys();
  }

  function fit() {
    if (ended) return;
    box.width = clamp(box.width, MIN_SIZE, innerWidth);
    box.height = clamp(box.height, MIN_SIZE, innerHeight);
    box.x = clamp(box.x, 0, innerWidth - box.width);
    box.y = clamp(box.y, 0, innerHeight - box.height);
    paint();
  }

  function finish(land = null) {
    if (ended) return;
    ended = true;
    ++attempt;
    window.removeEventListener("resize", resize);
    closeLayer(() => overlay.remove(), land ?? (() => handBack(origin)));
    paintKeys();
    settled();
  }

  function resize() {
    ++attempt;
    busy = false;
    drag = null;
    keeps(overlay, "aria-busy", null);
    fit();
  }

  function move(binding) {
    const resizing = binding.startsWith("Shift+");
    const key = binding.split("+").at(-1);
    const dx = key === "ArrowLeft" ? -STEP : key === "ArrowRight" ? STEP : 0;
    const dy = key === "ArrowUp" ? -STEP : key === "ArrowDown" ? STEP : 0;
    if (resizing) {
      box.width = clamp(box.width + dx, MIN_SIZE, innerWidth - box.x);
      box.height = clamp(box.height + dy, MIN_SIZE, innerHeight - box.y);
    } else {
      box.x += dx;
      box.y += dy;
    }
    fit();
  }

  function anchorForBox() {
    // The passive paint leaves targets exposed to the ordinary visibility reading,
    // including revisions, widget updates and reflow made while the user selected.
    const x = box.x + box.width / 2;
    const y = box.y + box.height / 2;
    const winner = visibleTargets()
      .filter(({ rect }) => rect && rect.width && rect.height)
      .map((target) => ({
        ...target,
        distance: Math.hypot(
          Math.max(target.rect.left - x, 0, x - target.rect.right),
          Math.max(target.rect.top - y, 0, y - target.rect.bottom),
        ),
      }))
      .sort(
        (a, b) =>
          a.distance - b.distance ||
          a.rect.width * a.rect.height - b.rect.width * b.rect.height,
      )[0];
    const target = winner?.capture ? winner.capture() : winner;
    return target?.anchor ?? null;
  }

  async function capture() {
    if (ended || busy || drag) return;
    const ticket = ++attempt;
    const revision = runtime.currentRevision;
    const anchor = anchorForBox();
    const clip = { ...box, x: box.x + scrollX, y: box.y + scrollY };
    busy = true;
    keeps(overlay, "aria-busy", "true");
    keepsText(status, "Capturing…");
    paintKeys();
    try {
      const { snapdom } = await import("../../vendor/snapdom.esm.js");
      if (ended || ticket !== attempt) return;
      const image = await snapdom(document.body, {
        clip,
        dpr: window.devicePixelRatio,
        exclude: ".lf-region-capture, .lf-shortcut-bar, .lf-banner",
        excludeMode: "remove",
        invalidate: true,
        reconcile: true,
      });
      const blob = await image.toBlob({ format: "png" });
      if (image.warnings.some(({ code }) => code === "image-fallback"))
        throw new Error(
          "An image in this area could not be captured. Try another area or paste a screenshot.",
        );
      if (ended || ticket !== attempt) return;
      if (revision !== runtime.currentRevision)
        throw new Error("The page changed. Select the area again.");
      let adding;
      finish(() => {
        adding = openComposerWithMedia(anchor, [blob]);
      });
      await adding;
    } catch (error) {
      if (ended || ticket !== attempt) return;
      busy = false;
      keeps(overlay, "aria-busy", null);
      const message = `Could not capture — ${error.message}`;
      keepsText(status, message);
      notice(message, { announce: false });
      paintKeys();
    }
  }

  function dragTo(event) {
    box = {
      x: Math.round(Math.min(drag.x, event.clientX)),
      y: Math.round(Math.min(drag.y, event.clientY)),
      width: Math.max(MIN_SIZE, Math.round(Math.abs(event.clientX - drag.x))),
      height: Math.max(MIN_SIZE, Math.round(Math.abs(event.clientY - drag.y))),
    };
    fit();
  }

  // The command owner filters chrome and suppresses claimed events before authored
  // controls see them. Pointer capture, if needed, belongs to that input owner too.
  function pointer(event) {
    if (ended) return false;
    if (event.type === "pointerdown") {
      if (busy || drag || !event.isPrimary || event.button !== 0) return false;
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY };
      box = { x: drag.x, y: drag.y, width: MIN_SIZE, height: MIN_SIZE };
      fit();
      return true;
    }
    if (!drag || drag.id !== event.pointerId) return false;
    if (event.type === "pointermove") dragTo(event);
    else if (event.type === "pointerup" || event.type === "pointercancel") {
      if (event.type === "pointerup") dragTo(event);
      drag = null;
      paintKeys();
    } else return false;
    return true;
  }

  // A native editor taking focus ends selection without taking that focus back.
  const cancel = ({ restore = true } = {}) => finish(restore ? null : () => {});
  const rows = [
    {
      id: "capture.region.attach",
      keys: ["Enter"],
      title: "Attach capture",
      touch: "Attach capture",
      when: () => !ended && !busy && !drag,
      run: capture,
    },
    {
      id: "capture.region.adjust",
      keys: [
        "ArrowLeft",
        "ArrowRight",
        "ArrowUp",
        "ArrowDown",
        "Shift+ArrowLeft",
        "Shift+ArrowRight",
        "Shift+ArrowUp",
        "Shift+ArrowDown",
      ],
      title: "adjust area",
      description: "Arrow keys move the area; Shift and arrow keys resize it",
      repeat: true,
      when: () => !ended && !busy && !drag,
      run: move,
    },
    {
      id: "capture.region.cancel",
      keys: ["Escape"],
      title: "Cancel capture",
      touch: "Cancel capture",
      when: () => !ended,
      run: cancel,
    },
  ];
  parent.append(overlay);
  focusDestination(overlay, "move");
  window.addEventListener("resize", resize);
  nextRender(fit);
  return { rows, pointer, cancel, done };
}
