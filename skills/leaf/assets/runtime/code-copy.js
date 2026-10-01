/* Code blocks own a copy control beside their scrolling text. Plain blocks read
   their current code on activation; widgets supply their source before rendering
   line numbers, annotations, or other words. CSS anchors keep the control at the
   block's right edge without wrapping authored nodes or moving them on arrival. */
import { offer } from "./widget-elements.js";
import { watchArrivals } from "./arrivals.js";

const controls = new WeakMap();
let nextAnchor = 0;

export function copyCodeBlock(pre, source) {
  let copy = controls.get(pre);
  if (!copy) {
    copy = offer("wa-copy-button", "lf-code-copy");
    copy.copyLabel = "Copy code";
    copy.successLabel = "Code copied";
    copy.errorLabel = "Unable to copy code";
    copy.tooltip = "copy";
    copy.style.positionAnchor = `--lf-code-copy-${++nextAnchor}`;
    copy.addEventListener("click", () => (copy.value = source()), { capture: true });
    controls.set(pre, copy);
  }
  if (pre.style.anchorName !== copy.style.positionAnchor)
    pre.style.anchorName = copy.style.positionAnchor;
  return copy;
}

export function watchCodeBlocks() {
  watchArrivals("pre:has(> code)", ["style"], {
    arrive(pre) {
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
