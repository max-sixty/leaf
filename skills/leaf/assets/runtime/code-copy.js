/* Code blocks own a copy control beside their scrolling text. Document controls
   stand in chrome so authored sibling selectors keep their meaning. Their sources read
   their current code on activation; widgets supply their source before rendering
   line numbers, annotations, or other words. CSS anchors keep the control at the
   block's right edge without wrapping authored nodes or moving them on arrival.
   Widgets connect their final styled block before requesting the control. On touch,
   entering the source focuses it and hides the overlay, leaving covered words
   available to read and select. Leaving the source restores the copy control.
   Enter on a document code block moves keyboard focus to its copy control. */
import { offer } from "./widget-elements.js";
import { watchArrivals } from "./arrivals.js";
import { anchorName } from "./anchor-names.js";
import { focusDestination } from "./focus.js";
import { chromeRoot } from "./chrome.js";
import { claimReachStop, releaseReachStop } from "./reach.js";

const controls = new WeakMap();
const wired = new WeakMap();
const routes = new WeakMap();

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
      // Keep the page's authored sibling and child selectors intact. The anchor
      // still positions this control at its source when it lives in chrome.
      if (copy.parentNode !== chromeRoot) chromeRoot.append(copy);
      copy.tabIndex = -1;
      let route = routes.get(pre);
      if (!route) routes.set(pre, (route = { keys: false }));
      claimReachStop(pre);
      if (!pre.hasAttribute("aria-keyshortcuts")) {
        pre.setAttribute("aria-keyshortcuts", "Enter");
        route.keys = true;
      }
      if (!wired.has(pre)) {
        const events = new AbortController();
        wired.set(pre, events);
        const options = { signal: events.signal };
        // Let the browser continue Tab from the source's document position,
        // rather than from this control's later position in chrome.
        copy.addEventListener(
          "keydown",
          (event) => {
            if (event.key === "Tab") focusDestination(pre);
          },
          options,
        );
        pre.addEventListener(
          "keydown",
          (event) => {
            if (
              event.target !== pre ||
              event.key !== "Enter" ||
              event.altKey ||
              event.ctrlKey ||
              event.metaKey
            )
              return;
            event.preventDefault();
            const button = copy.shadowRoot?.querySelector("button");
            if (button) focusDestination(button);
          },
          options,
        );
        pre.addEventListener(
          "pointerenter",
          () => copy.classList.add("lf-code-copy-hover"),
          options,
        );
        pre.addEventListener(
          "pointerleave",
          () => copy.classList.remove("lf-code-copy-hover"),
          options,
        );
        pre.addEventListener(
          "focus",
          () => copy.classList.add("lf-code-copy-focused"),
          options,
        );
        pre.addEventListener(
          "blur",
          () => copy.classList.remove("lf-code-copy-focused"),
          options,
        );
      }
    },
    leave(pre) {
      wired.get(pre)?.abort();
      wired.delete(pre);
      const copy = controls.get(pre);
      copy?.classList.remove("lf-code-copy-hover", "lf-code-copy-focused");
      copy?.remove();
      const route = routes.get(pre);
      releaseReachStop(pre);
      if (route?.keys && pre.getAttribute("aria-keyshortcuts") === "Enter")
        pre.removeAttribute("aria-keyshortcuts");
      routes.delete(pre);
    },
  });
}
