/* A bounded area-selection interaction over the current viewport.
 *
 * Native modality owns isolation, focus and the Tab loop. Pointer drags set a rectangle;
 * arrows move it and Shift+arrows resize it, so capturing never requires a drag. The
 * selected pixels stay in viewport coordinates until confirmation, when SnapDOM takes
 * a document-coordinate crop of the live DOM, excluding the selector and its shortcut
 * bar. SnapDOM owns cloning, shadow trees, styles, fonts, SVG and rasterization;
 * Leaf owns no renderer.
 * The crop is approximate browser rendering, not privileged access to screen pixels.
 * Known missing images refuse capture instead of attaching a placeholder.
 *
 * The closest containing semantic target at the rectangle's center anchors its comment.
 * A canceled or superseded capture cannot create an attachment. Failed rasterization
 * leaves the rectangle available to retry. Image upload and draft ownership remain the
 * composition input's, including its protection against a draft changing mid-upload.
 */
import { el } from "../widget-elements.js";
import { keys, paintKeys } from "../keyboard/scopes.js";
import { transitionNativeAncestor } from "../keyboard/layer-stack.js";
import {
  focusDestination,
  focused,
  handBack,
  closeLayer,
  openLayer,
} from "../focus.js";
import { keeps, keepsText } from "../keeps.js";
import { runtime } from "../context.js";
import { nextRender } from "../rendering.js";
import { clamp } from "../rect.js";

const MIN_SIZE = 8;
const STEP = 10;

export function captureRegion({ parent, visibleTargets, openComposerWithMedia }) {
  return new Promise((settled) => {
    const origin = focused();
    const dialog = el("dialog", "lf-ui lf-region-capture");
    dialog.setAttribute("aria-label", "Capture area");
    dialog.setAttribute("aria-modal", "true");
    const selection = el("div", "lf-region-selection");
    selection.setAttribute("aria-hidden", "true");
    const toolbar = el("div", "lf-region-toolbar");
    const guide = el(
      "p",
      "",
      "Drag to select. Arrow keys move; Shift + arrows resize.",
    );
    const status = el("p", "lf-region-status");
    status.setAttribute("role", "status");
    const attach = el("button", "lf-btn primary", "Attach capture");
    attach.type = "button";
    const cancel = el("button", "lf-btn", "Cancel");
    cancel.type = "button";
    const actions = el("div", "lf-region-actions");
    actions.append(cancel, attach);
    toolbar.append(guide, status, actions);
    dialog.append(selection, toolbar);
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
      closeLayer(
        () => {
          dialog.close();
          dialog.remove();
        },
        land ?? (origin && (() => handBack(origin))),
      );
      settled();
    }

    function resize() {
      ++attempt;
      busy = false;
      keeps(dialog, "aria-busy", null);
      fit();
    }

    function move(binding) {
      const resize = binding.startsWith("Shift+");
      const key = binding.split("+").at(-1);
      const dx = key === "ArrowLeft" ? -STEP : key === "ArrowRight" ? STEP : 0;
      const dy = key === "ArrowUp" ? -STEP : key === "ArrowDown" ? STEP : 0;
      if (resize) {
        box.width = clamp(box.width + dx, MIN_SIZE, innerWidth - box.x);
        box.height = clamp(box.height + dy, MIN_SIZE, innerHeight - box.y);
      } else {
        box.x += dx;
        box.y += dy;
      }
      fit();
    }

    function anchorForBox() {
      // The selector itself covers every page target. Lift that native layer only
      // during this synchronous reading, then restore it and its focus before paint.
      // Reading now includes revisions, widget updates and viewport reflow made while
      // the user selected, rather than anchoring current pixels to an opening snapshot.
      let targets;
      transitionNativeAncestor(dialog, () => {
        dialog.close();
        targets = visibleTargets();
        dialog.showModal();
      });
      const x = box.x + box.width / 2;
      const y = box.y + box.height / 2;
      return (
        targets
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
          )[0]?.anchor ?? null
      );
    }

    async function capture() {
      if (busy) return;
      const ticket = ++attempt;
      const revision = runtime.currentRevision;
      const anchor = anchorForBox();
      const clip = { ...box, x: box.x + scrollX, y: box.y + scrollY };
      busy = true;
      keeps(dialog, "aria-busy", "true");
      keepsText(status, "Capturing…");
      paintKeys();
      try {
        const { snapdom } = await import("../../vendor/snapdom.esm.js");
        if (ended || ticket !== attempt) return;
        const image = await snapdom(document.body, {
          clip,
          dpr: window.devicePixelRatio,
          exclude: ".lf-region-capture, .lf-shortcut-bar",
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
        // Hand focus directly from the modal to the anchored comment, rather than
        // restoring its opener and moving the user twice.
        let adding;
        finish(() => {
          adding = openComposerWithMedia(anchor, [blob]);
        });
        await adding;
      } catch (error) {
        if (ended || ticket !== attempt) return;
        busy = false;
        keeps(dialog, "aria-busy", null);
        keepsText(status, `Could not capture — ${error.message}`);
        paintKeys();
      }
    }

    dialog.addEventListener("pointerdown", (event) => {
      if (
        busy ||
        !event.isPrimary ||
        event.button !== 0 ||
        toolbar.contains(event.target)
      )
        return;
      event.preventDefault();
      dialog.setPointerCapture(event.pointerId);
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY };
      box = { x: drag.x, y: drag.y, width: MIN_SIZE, height: MIN_SIZE };
      fit();
    });
    dialog.addEventListener("pointermove", (event) => {
      if (!drag || drag.id !== event.pointerId) return;
      box = {
        x: Math.round(Math.min(drag.x, event.clientX)),
        y: Math.round(Math.min(drag.y, event.clientY)),
        width: Math.max(MIN_SIZE, Math.round(Math.abs(event.clientX - drag.x))),
        height: Math.max(MIN_SIZE, Math.round(Math.abs(event.clientY - drag.y))),
      };
      fit();
    });
    const release = (event) => {
      if (drag?.id !== event.pointerId) return;
      drag = null;
      if (dialog.hasPointerCapture(event.pointerId))
        dialog.releasePointerCapture(event.pointerId);
      paintKeys();
    };
    dialog.addEventListener("pointerup", release);
    dialog.addEventListener("pointercancel", release);
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      finish();
    });
    keys(
      dialog,
      "Area capture",
      [
        {
          id: "capture.region.attach",
          keys: ["Enter"],
          title: "Attach capture",
          control: attach,
          when: () => !busy && !drag,
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
          when: () => !busy && !drag,
          run: move,
        },
        {
          id: "capture.region.cancel",
          keys: ["Escape"],
          title: "Cancel capture",
          control: cancel,
          run: () => finish(),
        },
      ],
      { when: () => dialog.open },
    );
    parent.append(dialog);
    openLayer(dialog, origin);
    dialog.showModal();
    focusDestination(attach, "move");
    window.addEventListener("resize", resize);
    nextRender(fit);
  });
}
