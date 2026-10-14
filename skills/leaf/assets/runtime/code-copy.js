/* Blocks of source text own a copy control at their top right: every document code
   block, and any widget block that asks with `copyBlock`, such as a code listing or a
   draft's Markdown. Document controls stand in chrome so authored sibling selectors
   keep their meaning. Their sources read their current text on activation; widgets
   supply their source before rendering line numbers, annotations, or other words. CSS
   anchors keep the control at the block's right edge without wrapping authored nodes
   or moving them on arrival. Widgets connect their final styled block before
   requesting the control.
   Enter on a block the user stands on copies it. That press is a register row
   projected onto the block beside any scope its owner declares, so the shortcut bar, the
   command reference and `aria-keyshortcuts` name it. A link or button inside the block
   keeps its own Enter (`nativeActivationAt`), and a document block's control stays out
   of the Tab sequence. Focus need not be on the control, so every copy's result also
   takes the status line.
   A document block's control passes under the sticky headers the page declares over its
   block, as the block's own words do, standing in the frames that cut every box
   following scrolled content (css-anchors.js, `headerLevels`), so a block scrolled
   under a stuck toolbar offers no Copy over the toolbar's controls.
   The control follows the common pattern for code copy: hidden at rest, so it covers no
   words, and shown while a pointer is over the block or the user stands on it. A finger
   has no hover, so a tap on the block stands the user on it and shows the control in
   its corner, the touch form of the same reveal. The control takes no room, since room
   made for it would move the page's content (`../AGENTS.md`, "Nothing Leaf draws moves
   the page's content"). */
import { copyControl } from "./copy-control.js";
import { watchArrivals } from "./arrivals.js";
import {
  anchorReading,
  cutFrames,
  headerLevels,
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

const controls = new WeakMap();
const wired = new WeakMap();
// The frames each document control stands in, under its block's sticky headers.
const cuts = new WeakMap();
const makeCut = () => {
  const frame = document.createElement("div");
  frame.className = "lf-code-copy-cut";
  return frame;
};
// The key this module projects its Copy scope under, beside the block's other owners.
const COPY_SCOPE = Symbol("code copy");

// A tap on a hidden control's corner stands the user on the block, which reveals the
// control before the tap's click is aimed, so the click lands on it. Only a press that
// began on the shown control copies; Enter's click carries no press (`detail` 0).
// The last press may have been on markup a revision removes before another press.
// Keep membership for the following click without keeping that markup alive.
let pressedPath = new WeakSet();
addEventListener(
  "pointerdown",
  (event) => (pressedPath = new WeakSet(event.composedPath())),
  {
    capture: true,
  },
);

// Focus can reveal and scroll a source before the observer's next task. Its keyboard
// route must see the control in that same gesture, widgets included.
onStanding((node) => {
  for (let at = node; at; at = upFrom(at)) {
    const copy = controls.get(at);
    if (copy) return refreshAnchorView(copy);
  }
});

// `noun` names what the block holds, in the control's label and its result.
function prepareCodeBlock(pre, source, noun) {
  let copy = controls.get(pre);
  if (!copy) {
    copy = copyControl("lf-code-copy", {
      label: `Copy ${noun}`,
      success: `${noun[0].toUpperCase()}${noun.slice(1)} copied`,
      error: `Unable to copy ${noun}`,
    });
    copy.addEventListener(
      "click",
      (event) => {
        if (event.detail && !pressedPath.has(copy)) {
          event.preventDefault();
          event.stopImmediatePropagation();
        } else copy.value = source();
      },
      { capture: true },
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
function declareCopy(pre, copy, noun) {
  projectCommandScope(
    pre,
    COPY_SCOPE,
    commandScope("On a code block", [
      {
        id: "code.copy",
        keys: ["Enter"],
        description: `Copy this block's ${noun} to the clipboard`,
        title: `copy ${noun}`,
        run: () => copy.shadowRoot.querySelector("button").click(),
      },
    ]),
  );
}

export function copyBlock(block, source, noun) {
  const copy = positionCodeBlock(prepareCodeBlock(block, source, noun));
  declareCopy(block, copy, noun);
  return copy;
}

export function watchCodeBlocks() {
  // A widget's shadow stage is its renderer's notation, not an ordinary document
  // block. Its module supplies the source explicitly through copyBlock.
  watchArrivals("pre:has(> code)", ["style"], {
    arriveBatch(blocks) {
      // Read every source before anchor names and connected controls change layout.
      const prepared = blocks
        .filter((pre) => pre.getRootNode() === document)
        .map(
          (pre) =>
            /** @type {[HTMLElement, ReturnType<typeof prepareCodeBlock>, any[]]} */ ([
              pre,
              prepareCodeBlock(
                pre,
                () => pre.querySelector(":scope > code").textContent,
                "code",
              ),
              headerLevels(pre),
            ]),
        );
      for (const [pre, pending, levels] of prepared) {
        const copy = positionCodeBlock(pending);
        // Keep the page's authored sibling and child selectors intact. The anchor
        // still positions this control at its source when it lives in chrome, in the
        // frames its block's headers cut.
        const frames = cutFrames(levels, cuts.get(copy) ?? [], makeCut);
        cuts.set(copy, frames);
        if (frames[0] && frames[0].parentNode !== chromeRoot)
          move(chromeRoot, frames[0], null);
        const home = frames.at(-1) ?? chromeRoot;
        if (copy.parentNode !== home) move(home, copy, null);
        copy.tabIndex = -1;
        claimReachStop(pre);
        if (!wired.has(pre)) {
          const events = new AbortController();
          wired.set(pre, events);
          declareCopy(pre, copy, "code");
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
      cuts.get(copy)?.[0]?.remove();
      cuts.delete(copy);
      releaseReachStop(pre);
      projectCommandScope(pre, COPY_SCOPE, null);
    },
  });
}
