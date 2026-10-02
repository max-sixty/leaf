/* Code blocks own a copy control beside their scrolling text. Document blocks read
   their current code on activation; widgets supply their source before rendering
   line numbers, annotations, or other words. CSS anchors keep the control at the
   block's right edge without wrapping authored nodes or moving them on arrival.
   Widgets connect their final styled block before requesting the control. On touch,
   entering the source focuses it and hides the overlay, leaving covered words
   available to read and select. Leaving the source restores the copy control. */
import { offer } from "./widget-elements.js";
import { watchArrivals } from "./arrivals.js";
import { anchorName } from "./anchor-names.js";
import { focusDestination } from "./focus.js";

const controls = new WeakMap();

export function copyCodeBlock(pre, source) {
  let copy = controls.get(pre);
  if (!copy) {
    copy = offer("wa-copy-button", "lf-code-copy");
    copy.copyLabel = "Copy code";
    copy.successLabel = "Code copied";
    copy.errorLabel = "Unable to copy code";
    copy.tooltip = "none";
    copy.addEventListener("click", () => (copy.value = source()), { capture: true });
    pre.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "touch" && copy.isConnected) focusDestination(pre);
    });
    controls.set(pre, copy);
  }
  const name = anchorName(pre);
  if (copy.style.positionAnchor !== name) copy.style.positionAnchor = name;
  return copy;
}

export function watchCodeBlocks() {
  // A widget's shadow stage is its renderer's notation, not an ordinary document
  // block. Its module supplies the source explicitly through copyCodeBlock.
  watchArrivals("pre:has(> code)", ["style"], {
    arrive(pre) {
      if (pre.getRootNode() !== document) return;
      const copy = copyCodeBlock(
        pre,
        () => pre.querySelector(":scope > code").textContent,
      );
      if (pre.nextSibling !== copy) pre.after(copy);
    },
    leave(pre) {
      controls.get(pre)?.remove();
    },
  });
}
