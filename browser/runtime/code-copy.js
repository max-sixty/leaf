/* Blocks of source text own a copy control at their top right: every document code
   block, every block a widget declares, such as a code listing, and any widget block
   that asks with `copyBlock`, such as a draft's Markdown among its own controls.
   Document controls stand in chrome so authored sibling selectors keep their meaning.
   Runtime prose keeps its control beside the source, inside its surface's interaction
   boundary, so pressing Copy neither dismisses the surface nor falls behind it.
   A declared block carries `data-lf-copy`, naming what it holds, and its `lfCopy()`
   returns its text, the source the widget drew line numbers, annotations or other words
   over; its control stands right after it, in the widget's tree. A widget declaring
   one imports nothing from Leaf to do it, so a page without Leaf, which reads no
   declaration, shows no control. Sources read their current text on activation. CSS
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
   reveal. Shown, it is a toolbar of one mark (integration.css, `.lf-mark-bar`) just
   inside the block's top-right corner, so whatever shows the block shows it whole, and
   it covers the first line's last words only while it shows. The control takes no
   room, since room made for it would move the page's content (`../AGENTS.md`,
   "Nothing Leaf draws moves the page's content"). */
import { copyControl, copyTrigger } from "./copy-control.js";
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
import { leafSurface } from "./passages.js";
import { skipped } from "./shown-box.js";
import { nextRender, sizeObserver } from "./rendering.js";
import { focusDestination, onCurrentLocation } from "./focus.js";
import { upFrom } from "./shadow.js";
import { move } from "./dom-move.js";
import { claimReachStop, releaseReachStop } from "./reach.js";
import { commandScope, projectCommandScope } from "./keyboard/scopes.js";

/** @type {WeakMap<Element, ReturnType<typeof copyControl>>} */
const controls = new WeakMap();
/** @type {WeakMap<Element, AbortController>} */
const wired = new WeakMap();
// Observe only deferred document blocks. Opening a disclosure or a hidden panel gives
// its blocks boxes again; prepare that batch without polling hidden DOM.
const deferred = new WeakSet();
/** @type {(blocks: Element[]) => void} */
let prepareDocumentBlocks;
const revealed = sizeObserver((entries) => {
  // Preparing controls changes scroll reach and can resize other observed boxes.
  // Leave the observer's delivery loop before writing those changes.
  nextRender(() =>
    prepareDocumentBlocks(
      entries.map(({ target }) => target).filter((target) => deferred.has(target)),
    ),
  );
});
// The key this module projects its Copy scope under, beside the block's other owners.
const COPY_SCOPE = Symbol("code copy");

// Focus can reveal and scroll a source before the observer's next task. Its keyboard
// route must see the control in that same gesture, widgets included.
onCurrentLocation((node) => {
  for (let at = node; at; at = upFrom(at)) {
    if (deferred.has(at) && !skipped(at)) prepareDocumentBlocks([at]);
    const copy = controls.get(at);
    if (copy) return revealControl(copy, at);
  }
});

// `noun` names what the block holds, in the control's label and its result.
/** @param {Element} pre @param {() => string} source @param {string} noun */
function prepareCodeBlock(pre, source, noun) {
  let copy = controls.get(pre);
  if (!copy) {
    const control = copyControl("lf-code-copy", {
      role: "mark",
      label: `Copy ${noun}`,
      success: `${noun.charAt(0).toUpperCase()}${noun.slice(1)} copied`,
      error: `Unable to copy ${noun}`,
    });
    control.addEventListener(
      "click",
      (event) => {
        // A tap on a hidden control's corner reveals it; only a later press copies.
        if (pressedElsewhere(event, control)) {
          event.preventDefault();
          event.stopImmediatePropagation();
        } else control.value = source();
      },
      { capture: true },
    );
    pre.addEventListener("pointerdown", (event) => {
      if (
        event instanceof PointerEvent &&
        event.pointerType === "touch" &&
        control.isConnected
      )
        focusDestination(pre, "move");
    });
    pre.addEventListener("pointerenter", () => revealControl(control, pre));
    controls.set(pre, control);
    copy = control;
  }
  return anchorControl(copy, pre);
}

// Declared on each arrival, since leaving withdraws it. A widget renders a new block
// each time, and the register forgets one that leaves the document.
/** @param {Element} pre @param {ReturnType<typeof copyControl>} copy @param {string} noun */
function declareCopy(pre, copy, noun) {
  projectCommandScope(
    pre,
    COPY_SCOPE,
    commandScope("On a code block", [
      {
        id: "code.copy",
        keys: ["Enter"],
        title: `copy ${noun}`,
        get run() {
          const trigger = copyTrigger(copy);
          return trigger ? () => trigger.click() : undefined;
        },
      },
    ]),
  );
}

/** @param {Element} block @param {() => string} source @param {string} noun */
export function copyBlock(block, source, noun) {
  const copy = aimControl(prepareCodeBlock(block, source, noun));
  declareCopy(block, copy, noun);
  return copy;
}

// A declared block's control stands after it, in the widget's tree, until the block
// leaves or stops declaring. Standing it there is a sibling arriving beside the block,
// which asks again, so a block whose control already stands is passed by.
const DECLARED = "[data-lf-copy]";
/** @param {Element[]} blocks */
function prepareDeclaredBlocks(blocks) {
  const prepared = blocks
    .filter((block) => controls.get(block)?.previousSibling !== block)
    .map((block) => {
      const noun = block.getAttribute("data-lf-copy");
      if (noun === null) throw new Error("A declared copy block needs data-lf-copy");
      return {
        block,
        noun,
        pending: prepareCodeBlock(
          block,
          () => {
            if (!block.lfCopy) throw new Error("A declared copy block needs lfCopy()");
            return block.lfCopy();
          },
          noun,
        ),
      };
    });
  for (const { block, noun, pending } of prepared) {
    const copy = aimControl(pending);
    const parent = block.parentNode;
    if (!parent) continue;
    move(parent, copy, block.nextSibling);
    declareCopy(block, copy, noun);
  }
}

export function watchCodeBlocks() {
  watchArrivals(DECLARED, ["data-lf-copy"], {
    arriveBatch: prepareDeclaredBlocks,
    leave(block) {
      controls.get(block)?.remove();
      projectCommandScope(block, COPY_SCOPE, null);
    },
  });
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
  prepareDocumentBlocks = (blocks) => {
    // Read every source before anchor names and connected controls change layout.
    const prepared = blocks
      .filter((pre) => {
        if (pre.getRootNode() !== document) return false;
        if (skipped(pre)) {
          if (!wired.has(pre) && !deferred.has(pre)) {
            deferred.add(pre);
            revealed.observe(pre);
          }
          return false;
        }
        if (deferred.delete(pre)) revealed.unobserve(pre);
        return true;
      })
      .map((pre) => ({
        pre,
        pending: prepareCodeBlock(
          pre,
          () => {
            const code = pre.querySelector(":scope > code");
            if (!code) throw new Error("The code block no longer holds its source");
            return code.textContent;
          },
          "code",
        ),
        levels: headerLevels(pre),
      }));
    for (const { pre, pending, levels } of prepared) {
      const copy = aimControl(pending);
      // Runtime surfaces keep their controls inside their own interaction boundary;
      // a press on a control in document chrome would dismiss an open panel.
      const parent = pre.parentNode;
      if (!parent) continue;
      if (leafSurface(pre)) move(parent, copy, pre.nextSibling);
      else standInChrome(copy, pre, levels);
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
  };
  watchArrivals(`pre:has(> code):not(${DECLARED})`, ["style"], {
    arriveBatch: prepareDocumentBlocks,
    leave(pre) {
      if (deferred.delete(pre)) revealed.unobserve(pre);
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
