import {
  pageImage
} from "./bundle-composing~page-image-2.js";
import "./bundle-sample-2.js";
import "./bundle-dress.js";
import "./bundle-widget-upgrade.js";
import "./bundle-initial-render.js";
import "./bundle-stylesheets.js";
import "./bundle-passage-facts.js";
import {
  clamp,
  el,
  layoutWindow,
  notice,
  paintKeys
} from "./bundle-page-paint.js";
import {
  runtime
} from "./bundle-semantic-state.js";
import {
  closeLayer,
  focusDestination,
  focused,
  handBack,
  keeps,
  keepsText,
  nextRender
} from "./bundle-sample-visibility.js";
import "./bundle-queued-work.js";
import "./bundle-__export.js";

// runtime/composing/region-selector.js
var MIN_SIZE = 8;
var STEP = 10;
function createRegionSelector({
  parent,
  visibleTargets,
  openComposerWithMedia,
  returnTo = null
}) {
  const { promise: done, resolve: settled } = Promise.withResolvers();
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
  const { right: width, bottom: height } = layoutWindow();
  let box = {
    x: Math.round(width * 0.2),
    y: Math.round(height * 0.2),
    width: Math.round(width * 0.6),
    height: Math.round(height * 0.5)
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
    keepsText(status, `${box.width} \xD7 ${box.height} pixels`);
    paintKeys();
  }
  function fit() {
    if (ended) return;
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
    const x = box.x + box.width / 2;
    const y = box.y + box.height / 2;
    const winner = visibleTargets().filter(({ rect }) => rect && rect.width && rect.height).map((target2) => ({
      ...target2,
      distance: Math.hypot(
        Math.max(target2.rect.left - x, 0, x - target2.rect.right),
        Math.max(target2.rect.top - y, 0, y - target2.rect.bottom)
      )
    })).sort(
      (a, b) => a.distance - b.distance || a.rect.width * a.rect.height - b.rect.width * b.rect.height
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
    keepsText(status, "Capturing\u2026");
    paintKeys();
    try {
      const { blob, warnings } = await pageImage(clip, {
        exclude: [".lf-region-capture", ".lf-shortcut-bar", ".lf-banner"]
      });
      if (ended || ticket !== attempt) return;
      if (revision !== runtime.currentRevision)
        throw new Error("The page changed. Select the area again.");
      let adding;
      finish(() => {
        adding = openComposerWithMedia(anchor, [blob]);
      });
      await adding;
      if (warnings.length) notice(`Captured \u2014 ${warnings.join(" ")}`);
    } catch (error) {
      if (ended || ticket !== attempt) return;
      busy = false;
      keeps(overlay, "aria-busy", null);
      const message = `Could not capture \u2014 ${error.message}`;
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
      height: Math.max(MIN_SIZE, Math.round(Math.abs(event.clientY - drag.y)))
    };
    fit();
  }
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
  const cancel = ({ restore = true } = {}) => finish(restore ? null : () => {
  });
  const rows = [
    {
      id: "capture.region.attach",
      keys: ["Enter"],
      title: "Attach capture",
      touch: "Attach capture",
      when: () => !ended && !busy && !drag,
      run: capture
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
        "Shift+ArrowDown"
      ],
      title: "adjust area",
      description: "Arrow keys move the area; Shift and arrow keys resize it",
      repeat: true,
      when: () => !ended && !busy && !drag,
      run: move
    },
    {
      id: "capture.region.cancel",
      keys: ["Escape"],
      title: "Cancel capture",
      touch: "Cancel capture",
      when: () => !ended,
      run: cancel
    }
  ];
  parent.append(overlay);
  focusDestination(overlay, "move");
  window.addEventListener("resize", resize);
  nextRender(fit);
  return { rows, pointer, cancel, done };
}
export {
  createRegionSelector
};
