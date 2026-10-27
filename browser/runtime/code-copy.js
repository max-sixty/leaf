/* Blocks of source text own a copy control at their top right: every document code
   block, and any widget block that asks with `copyBlock`, such as a code listing or a
   draft's Markdown. Document controls stand in chrome so authored sibling selectors
   keep their meaning. Their sources read their current text on activation; widgets
   supply their source before rendering line numbers, annotations, or other words. CSS
   anchors keep the control at the block's right edge (block-controls.js). Widgets
   connect their final styled block before requesting the control.
   Enter on a block the user is on copies it. That press is a register row
   projected onto the block beside any scope its owner declares, so the hints, the
   command reference and `aria-keyshortcuts` name it. A link or button inside the block
   keeps its own Enter (`nativeActivationAt`), and a document block's control stays out
   of the Tab sequence. Focus need not be on the control, so every copy's result also
   takes the status line.
   A document block's control stands in chrome and passes under the page's sticky
   headers as block-controls.js says.
   The control follows the common pattern for code copy: hidden at rest, and shown while
   a pointer is over the block or the user is on it. A finger has no hover, so a tap on
   the block stands the user on it and shows the control, the touch form of the same
   reveal. Shown, it is a toolbar of one mark whose middle lies on the block's top
   border at its right (integration.css, `.lf-mark-bar`), the face and seat a draft's
   toolbar wears, so it covers the border and padding rather than the first line's last
   words. The control takes no room, since room made for it would move the page's
   content (`../AGENTS.md`, "Nothing Leaf draws moves the page's content"). */
import { copyControl } from "./copy-control.js";
import { watchArrivals } from "./arrivals.js";
import {
  aimControl,
  anchorControl,
  pressedElsewhere,
  releaseControl,
  revealControl,
  standInChrome,
  tabFromBlock,
} from "./block-controls.js";
import { headerLevels } from "./css-anchors.js";
import { focusDestination, onCurrentLocation } from "./focus.js";
import { upFrom } from "./shadow.js";
import { claimReachStop, releaseReachStop } from "./reach.js";
import { commandScope, projectCommandScope } from "./keyboard/scopes.js";

const controls = new WeakMap();
const wired = new WeakMap();
// The key this module projects its Copy scope under, beside the block's other owners.
const COPY_SCOPE = Symbol("code copy");

// Focus can reveal and scroll a source before the observer's next task. Its keyboard
// route must see the control in that same gesture, widgets included.
onCurrentLocation((node) => {
  for (let at = node; at; at = upFrom(at)) {
    const copy = controls.get(at);
    if (copy) return revealControl(copy, at);
  }
});

// `noun` names what the block holds, in the control's label and its result.
function prepareCodeBlock(pre, source, noun) {
  let copy = controls.get(pre);
  if (!copy) {
    copy = copyControl("lf-code-copy", {
      role: "mark",
      label: `Copy ${noun}`,
      success: `${noun[0].toUpperCase()}${noun.slice(1)} copied`,
      error: `Unable to copy ${noun}`,
    });
    copy.addEventListener(
      "click",
      (event) => {
        // A tap on a hidden control's corner reveals it; only a later press copies.
        if (pressedElsewhere(event, copy)) {
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
    pre.addEventListener("pointerenter", () => revealControl(copy, pre));
    controls.set(pre, copy);
  }
  return anchorControl(copy, pre);
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
        title: `copy ${noun}`,
        run: () => copy.shadowRoot.querySelector("button").click(),
      },
    ]),
  );
}

export function copyBlock(block, source, noun) {
  const copy = aimControl(prepareCodeBlock(block, source, noun));
  declareCopy(block, copy, noun);
  return copy;
}

export function watchCodeBlocks() {
  // Native prose blocks scroll sideways, including in rendered thread messages.
  watchArrivals(
    "pre, table:not([role='presentation']), [data-lf-content='data']:not([data-lf-verbatim])",
    [],
    {
      arrive: (block) => block.classList.toggle("scroll", true),
      leave: () => {},
    },
  );
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
        const copy = aimControl(pending);
        standInChrome(copy, pre, levels);
        copy.tabIndex = -1;
        claimReachStop(pre);
        if (!wired.has(pre)) {
          const events = new AbortController();
          wired.set(pre, events);
          declareCopy(pre, copy, "code");
          const options = { signal: events.signal };
          tabFromBlock(copy, pre, events.signal);
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
      if (copy) releaseControl(copy);
      releaseReachStop(pre);
      projectCommandScope(pre, COPY_SCOPE, null);
    },
  });
}
