/* Code blocks own a copy control beside their scrolling text. Document controls
   stand in chrome so authored sibling selectors keep their meaning. Their sources read
   their current code on activation; widgets supply their source before rendering
   line numbers, annotations, or other words. CSS anchors keep the control at the
   block's right edge without wrapping authored nodes or moving them on arrival.
   Widgets connect their final styled block before requesting the control.
   Enter on a code block the user stands on copies it. That press is a register row
   projected onto the block beside any scope its owner declares, so the shortcut bar, the
   command reference and `aria-keyshortcuts` name it, and its `touch` words make it the
   banner's step under a finger (keyboard/AGENTS.md, "Touch routes"). A link or button
   inside the code keeps its own Enter (`nativeActivationAt`), and a document block's
   control stays out of the Tab sequence. Focus need not be on the control, so every
   copy's result also takes the status line.
   A finger shows no intent before it lands, so on touch the control never shows: shown
   at rest it covered the ends of the first lines, and room made for it would move the
   page's content (`../AGENTS.md`, "Nothing Leaf draws moves the page's content").
   Entering the source by touch stands the user on it, and the banner offers its Copy. */
import { offer } from "./widget-elements.js";
import { watchArrivals } from "./arrivals.js";
import {
  anchorReading,
  nameAnchor,
  anchorView,
  refreshAnchorView,
} from "./css-anchors.js";
import { focusDestination, onStanding } from "./focus.js";
import { upFrom } from "./shadow.js";
import { chromeRoot } from "./chrome.js";
import { move } from "./dom-move.js";
import { claimReachStop, releaseReachStop } from "./reach.js";
import { commandScope, projectCommandScope } from "./keyboard/scopes.js";
import { notice } from "./notifications.js";

const controls = new WeakMap();
const wired = new WeakMap();
// The key this module projects its Copy scope under, beside the block's other owners.
const COPY_SCOPE = Symbol("code copy");

// Focus can reveal and scroll a source before the observer's next task. Its keyboard
// route must see the control in that same gesture, widgets included.
onStanding((node) => {
  for (let at = node; at; at = upFrom(at)) {
    const copy = controls.get(at);
    if (copy) return refreshAnchorView(copy);
  }
});

function prepareCodeBlock(pre, source) {
  let copy = controls.get(pre);
  if (!copy) {
    copy = offer("wa-copy-button", "lf-code-copy");
    copy.copyLabel = "Copy code";
    copy.successLabel = "Code copied";
    copy.errorLabel = "Unable to copy code";
    copy.tooltip = "none";
    copy.addEventListener("click", () => (copy.value = source()), { capture: true });
    // Web Awesome announces the result; Leaf puts the same words in its status line.
    copy.addEventListener("wa-copy", () =>
      notice(copy.successLabel, { announce: false }),
    );
    copy.addEventListener("wa-error", () =>
      notice(copy.errorLabel, { announce: false }),
    );
    pre.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "touch" && copy.isConnected)
        focusDestination(pre, "move");
    });
    pre.addEventListener("pointerenter", () => refreshAnchorView(copy));
    controls.set(pre, copy);
  }
  const place = () =>
    copy.classList.toggle("lf-code-copy-away", !anchorView(copy, pre, place));
  const near = anchorView(copy, pre, place);
  return { copy, near, anchor: anchorReading(pre) };
}

function positionCodeBlock({ copy, near, anchor }) {
  copy.classList.toggle("lf-code-copy-away", !near);
  const name = nameAnchor(anchor);
  if (copy.style.positionAnchor !== name) copy.style.positionAnchor = name;
  return copy;
}

// Declared on each arrival, since leaving withdraws it. A widget renders a new block
// each time, and the register forgets one that leaves the document.
function declareCopy(pre, copy) {
  projectCommandScope(
    pre,
    COPY_SCOPE,
    commandScope("On a code block", [
      {
        id: "code.copy",
        keys: ["Enter"],
        description: "Copy this block's code to the clipboard",
        title: "copy code",
        touch: "Copy code",
        run: () => copy.shadowRoot.querySelector("button").click(),
      },
    ]),
  );
}

export function copyCodeBlock(pre, source) {
  const copy = positionCodeBlock(prepareCodeBlock(pre, source));
  declareCopy(pre, copy);
  return copy;
}

export function watchCodeBlocks() {
  // A widget's shadow stage is its renderer's notation, not an ordinary document
  // block. Its module supplies the source explicitly through copyCodeBlock.
  watchArrivals("pre:has(> code)", ["style"], {
    arriveBatch(blocks) {
      // Read every source before anchor names and connected controls change layout.
      const prepared = blocks
        .filter((pre) => pre.getRootNode() === document)
        .map((pre) => [
          pre,
          prepareCodeBlock(pre, () => pre.querySelector(":scope > code").textContent),
        ]);
      for (const [pre, pending] of prepared) {
        const copy = positionCodeBlock(pending);
        // Keep the page's authored sibling and child selectors intact. The anchor
        // still positions this control at its source when it lives in chrome.
        if (copy.parentNode !== chromeRoot) move(chromeRoot, copy, null);
        copy.tabIndex = -1;
        claimReachStop(pre);
        if (!wired.has(pre)) {
          const events = new AbortController();
          wired.set(pre, events);
          declareCopy(pre, copy);
          const options = { signal: events.signal };
          // Let the browser continue Tab from the source's document position,
          // rather than from this control's later position in chrome.
          copy.addEventListener(
            "keydown",
            (event) => {
              if (event.key === "Tab") focusDestination(pre, "step");
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
      }
    },
    leave(pre) {
      wired.get(pre)?.abort();
      wired.delete(pre);
      const copy = controls.get(pre);
      if (copy?.matches(".lf-code-copy-hover, .lf-code-copy-focused"))
        copy.classList.remove("lf-code-copy-hover", "lf-code-copy-focused");
      copy?.remove();
      releaseReachStop(pre);
      projectCommandScope(pre, COPY_SCOPE, null);
    },
  });
}
