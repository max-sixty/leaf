/* A bounded area-selection interaction over the current viewport.
 *
 * The page command owner supplies input and registers this controller's rows with the
 * shared keyboard and the floating panel's controls. The overlay only paints: it never intercepts
 * hit testing or introduces a modal. Its outline leaves the selected content clear;
 * instructions and errors belong to the shared controls and notice line.
 *
 * A pointer drag draws a rectangle, and lifting the drag attaches it: the drag is a
 * pointer's whole gesture, so the panel's row offers no Attach step, and the
 * attachment's ✕ in the composer takes back a bad one, as a drawing's does. The user
 * chose this over drawing the area and then pressing Attach, which made one intent two
 * gestures; the cost is that neither a finger nor a mouse can adjust the area before it
 * attaches, only drag it again. A press that travels less than `MIN_SIZE` along both
 * axes is a tap, not a drag. A tap, or a pointer the browser cancels, attaches nothing
 * and puts back whatever rectangle stood before the press, with capture still standing
 * so the user can drag again or leave by its ✕.
 *
 * Capture opens on the dimmed page with no rectangle, and the field says "Drag an area
 * to capture". The first arrow key draws a preset rectangle in the middle of the
 * window; then arrows move it, Shift+arrows resize it and Enter attaches it, so
 * capturing never requires a drag. The user chose this over drawing the preset at open,
 * which read as a selection waiting for a press inside it, where a press did nothing.
 *
 * The selected pixels stay in viewport coordinates until confirmation, when
 * `pageImage` draws that document-coordinate crop, excluding the selector and the
 * floating panel. The crop is approximate browser rendering, not privileged access to
 * screen pixels. The closest containing semantic target at the rectangle's center
 * anchors its comment. A canceled or superseded capture cannot create an attachment.
 * Failed rasterization keeps capture standing over the same rectangle: Enter retries
 * it, and a pointer drags again. A part that could not be drawn attaches the image
 * anyway, with a notice naming what may be missing. Image upload and draft ownership
 * remain the composition input's, including its protection against a draft changing
 * mid-upload.
 */
import { describeFailure } from "../exception.js";
import { el } from "../widget-elements.js";
import { paintKeys } from "../keyboard/scopes.js";
import { focusDestination, focused, handBack, closeLayer } from "../focus.js";
import { keeps, keepsHidden, keepsText } from "../keeps.js";
import { runtime } from "../context.js";
import { nextRender } from "../rendering.js";
import { clamp } from "../rect.js";
import { layoutWindow } from "../geometry.js";
import { notice } from "../notifications.js";
import { pageImage } from "./page-image.js";
import { raiseError } from "../errors.js";

const MIN_SIZE = 8;
const STEP = 10;

export function createRegionSelector({
  parent,
  visibleTargets,
  openComposerWithMedia,
  returnTo = null,
}) {
  /** @type {PromiseWithResolvers<void>} */
  const { promise: done, resolve: settled } = Promise.withResolvers();
  const currentLocation = focused();
  const origin = currentLocation === document.body ? returnTo : currentLocation;
  const overlay = el("div", "lf-ui lf-region-capture");
  overlay.setAttribute("role", "region");
  overlay.setAttribute("aria-label", "Capture area");
  overlay.tabIndex = -1;
  const selection = el("div", "lf-region-selection");
  selection.setAttribute("aria-hidden", "true");
  const status = el("p", "lf-live lf-region-status");
  status.setAttribute("role", "status");
  overlay.append(selection, status);
  // No area until a drag draws one or an arrow key asks for the preset.
  let box = null;
  let drag = null;
  let busy = false;
  let attempt = 0;
  let ended = false;

  function paint() {
    keepsHidden(selection, !box);
    if (!box) {
      keepsText(status, "");
      paintKeys();
      return;
    }
    selection.style.left = `${box.x}px`;
    selection.style.top = `${box.y}px`;
    selection.style.width = `${box.width}px`;
    selection.style.height = `${box.height}px`;
    keepsText(status, `${box.width} × ${box.height} pixels`);
    paintKeys();
  }

  function fit() {
    if (ended) return;
    if (!box) return paint();
    const { right, bottom } = layoutWindow();
    box.width = clamp(box.width, MIN_SIZE, right);
    box.height = clamp(box.height, MIN_SIZE, bottom);
    box.x = clamp(box.x, 0, right - box.width);
    box.y = clamp(box.y, 0, bottom - box.height);
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
    if (!box) {
      const { right: width, bottom: height } = layoutWindow();
      box = {
        x: Math.round(width * 0.2),
        y: Math.round(height * 0.2),
        width: Math.round(width * 0.6),
        height: Math.round(height * 0.5),
      };
      return fit();
    }
    const resizing = binding.startsWith("Shift+");
    const key = binding.split("+").at(-1);
    const dx = key === "ArrowLeft" ? -STEP : key === "ArrowRight" ? STEP : 0;
    const dy = key === "ArrowUp" ? -STEP : key === "ArrowDown" ? STEP : 0;
    if (resizing) {
      const { right, bottom } = layoutWindow();
      box.width = clamp(box.width + dx, MIN_SIZE, right - box.x);
      box.height = clamp(box.height + dy, MIN_SIZE, bottom - box.y);
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
      const { blob, warnings } = await pageImage(clip, {
        exclude: [".lf-region-capture", ".lf-floating-panel", ".lf-fp-ground"],
      });
      if (ended || ticket !== attempt) return;
      if (revision !== runtime.currentRevision)
        throw new Error("The page changed. Select the area again.");
      let adding;
      finish(() => {
        adding = openComposerWithMedia(anchor, [blob]);
      });
      await adding;
      // The attachment stands; the notice says what it may be missing.
      if (warnings.length) notice(`Captured — ${warnings.join(" ")}`);
    } catch (error) {
      if (ended || ticket !== attempt) return;
      busy = false;
      keeps(overlay, "aria-busy", null);
      const message = `Could not capture — ${describeFailure(error)}`;
      keepsText(status, message);
      raiseError(message);
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
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY, from: box };
      box = { x: drag.x, y: drag.y, width: MIN_SIZE, height: MIN_SIZE };
      fit();
      return true;
    }
    if (!drag || drag.id !== event.pointerId) return false;
    if (event.type === "pointermove") dragTo(event);
    else if (event.type === "pointerup" || event.type === "pointercancel") {
      const drew =
        event.type === "pointerup" &&
        (Math.abs(event.clientX - drag.x) >= MIN_SIZE ||
          Math.abs(event.clientY - drag.y) >= MIN_SIZE);
      if (drew) dragTo(event);
      else box = drag.from;
      drag = null;
      if (drew) capture();
      else fit();
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
      // Lifting a pointer's drag attaches the area it drew.
      touch: false,
      when: () => !ended && !busy && !drag && Boolean(box),
      run: capture,
    },
    // A pointer drags the area it wants instead.
    {
      id: "capture.region.move",
      touch: false,
      keys: ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"],
      title: "move area",
      repeat: true,
      when: () => !ended && !busy && !drag,
      run: move,
    },
    {
      id: "capture.region.resize",
      touch: false,
      keys: ["Shift+ArrowLeft", "Shift+ArrowRight", "Shift+ArrowUp", "Shift+ArrowDown"],
      title: "resize area",
      repeat: true,
      when: () => !ended && !busy && !drag,
      run: move,
    },
    {
      id: "capture.region.cancel",
      keys: ["Escape"],
      title: "Cancel capture",
      exit: true,
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
