/* The world a runtime module is imported into by `pnpm run test:runtime`.

   A fold needs no browser, but the modules holding folds are written for one: they sit
   in files that also reach for `document`, `customElements`, or a DOM type at module
   scope, and an import that found none of those would fail before any test ran.
   happy-dom supplies the document object model itself — nodes, trees, selectors,
   ranges, and the geometry types — in this process.

   The runtime imports those modules by the root-absolute paths a served page answers
   (`tests/served-paths.mjs`), which Node would read as paths from the filesystem root.

   This is not Chrome, and which readings may be asked of it is `tests/AGENTS.md`'s,
   under "Put each assertion at the boundary that owns it". */

import { registerHooks } from "node:module";
import { pathToFileURL } from "node:url";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { served } from "../served-paths.mjs";

GlobalRegistrator.register({ url: "https://leaf.test/" });
// happy-dom does not implement custom element states. These tests inspect DOM
// ownership rather than :state() styling, so keep the native state's set semantics.
HTMLElement.prototype.attachInternals ??= function () {
  return { states: new Set() };
};
// happy-dom assigns a host's children to its slots, by name or by `assign()`, but
// answers no `assignedSlot`, so the runtime's climb through the rendered tree
// (`renderedParent`) would pass every slot by. A node's slot is the one in its parent's
// open shadow tree whose assignment holds it, as in a browser.
for (const { prototype } of [Element, Text])
  Object.defineProperty(prototype, "assignedSlot", {
    configurable: true,
    get() {
      const slots = this.parentElement?.shadowRoot?.querySelectorAll("slot") ?? [];
      return [...slots].find((slot) => slot.assignedNodes().includes(this)) ?? null;
    },
  });
// Its flattened assignment leaves out a slot's own children where nothing is assigned
// to it, which Chromium and Firefox put in its place, as the DOM's "find flattened
// slottables" does; a slot outside a shadow tree flattens to nothing in all three.
const { assignedNodes, assignedElements } = window.HTMLSlotElement.prototype;
/** @param {HTMLSlotElement} slot @returns {Node[]} */
const flattened = (slot) => {
  if (!(slot.getRootNode() instanceof ShadowRoot)) return [];
  const assigned = assignedNodes.call(slot);
  return (assigned.length ? assigned : [...slot.childNodes]).flatMap((node) =>
    node instanceof window.HTMLSlotElement && node.getRootNode() instanceof ShadowRoot
      ? flattened(node)
      : node.nodeType === Node.ELEMENT_NODE || node.nodeType === Node.TEXT_NODE
        ? [node]
        : [],
  );
};
window.HTMLSlotElement.prototype.assignedNodes = function (options) {
  return options?.flatten ? flattened(this) : assignedNodes.call(this);
};
window.HTMLSlotElement.prototype.assignedElements = function (options) {
  return options?.flatten
    ? flattened(this).filter((node) => node.nodeType === Node.ELEMENT_NODE)
    : assignedElements.call(this);
};
// An element laid out `display: contents` generates no box, so every engine answers
// that it is not visible, and gives it no focus unless it hands focus on; happy-dom
// reads only its ancestors.
const checkVisibility = window.Element.prototype.checkVisibility;
const boxless = (element) => window.getComputedStyle(element).display === "contents";
window.Element.prototype.checkVisibility = function (options) {
  return !boxless(this) && checkVisibility.call(this, options);
};
const focus = window.HTMLElement.prototype.focus;
window.HTMLElement.prototype.focus = function (options) {
  if (!boxless(this) || this.shadowRoot?.delegatesFocus) focus.call(this, options);
};
// happy-dom answers no composed range, which every engine ships and the runtime reads a
// selection by (`pageRange`). An end in a shadow root the caller doesn't name moves out
// to its host's edge, after the host for the range's end, as the DOM's rescoping does.
window.Selection.prototype.getComposedRanges ??= function ({ shadowRoots = [] } = {}) {
  if (!this.rangeCount) return [];
  const range = this.getRangeAt(0);
  /** @param {Node} node @param {number} offset @param {boolean} end */
  const rescoped = (node, offset, end) => {
    for (
      let root = node.getRootNode();
      root instanceof ShadowRoot && !shadowRoots.includes(root);
      root = node.getRootNode()
    ) {
      const { host } = root;
      node = /** @type {Node} */ (host.parentNode);
      offset = [...node.childNodes].indexOf(host) + (end ? 1 : 0);
    }
    return [node, offset];
  };
  const [startContainer, startOffset] = rescoped(
    range.startContainer,
    range.startOffset,
    false,
  );
  const [endContainer, endOffset] = rescoped(range.endContainer, range.endOffset, true);
  return [{ startContainer, startOffset, endContainer, endOffset }];
};
// Nor an element's `part`, the token list of its `part` attribute, which every engine
// ships and dom/focus.js marks a focused part with. As a DOMTokenList does, a change
// writes the attribute unless it is absent and stays empty, and tokens split at ASCII
// whitespace alone.
if (!("part" in Element.prototype))
  Object.defineProperty(Element.prototype, "part", {
    configurable: true,
    get() {
      const tokens = () =>
        (this.getAttribute("part") ?? "").split(/[\t\n\f\r ]+/).filter(Boolean);
      /** @param {string[]} list */
      const write = (list) => {
        if (list.length || this.hasAttribute("part"))
          this.setAttribute("part", [...new Set(list)].join(" "));
      };
      return {
        contains: (/** @type {string} */ token) => tokens().includes(token),
        add: (/** @type {string[]} */ ...added) => write([...tokens(), ...added]),
        remove: (/** @type {string[]} */ ...gone) =>
          write(tokens().filter((token) => !gone.includes(token))),
      };
    },
  });
// happy-dom has no StaticRange either, which the runtime builds for a span of the page
// it reads rather than selects (readings/passages.js, `runReading`).
globalThis.StaticRange ??= class StaticRange {
  /** @param {{startContainer: Node, startOffset: number, endContainer: Node, endOffset: number}} init */
  constructor({ startContainer, startOffset, endContainer, endOffset }) {
    Object.assign(this, { startContainer, startOffset, endContainer, endOffset });
  }
};
// Nothing is laid out here, so every box is whatever a test states. The window is the
// one box this world states itself, as a browser does: the root reports its size, and
// the visual viewport, which happy-dom lacks and dom/geometry.js reads (`shownWindow`) and
// listens to (`whenNone`), covers it unzoomed.
for (const [name, size] of [
  ["clientWidth", () => innerWidth],
  ["clientHeight", () => innerHeight],
])
  Object.defineProperty(document.documentElement, name, {
    configurable: true,
    get: size,
  });
const viewport = new window.EventTarget();
for (const [name, read] of Object.entries({
  offsetLeft: () => 0,
  offsetTop: () => 0,
  pageLeft: () => scrollX,
  pageTop: () => scrollY,
  width: () => innerWidth,
  height: () => innerHeight,
  scale: () => 1,
}))
  Object.defineProperty(viewport, name, { configurable: true, get: read });
window.visualViewport ??= viewport;
// Nor does it run animations, so none is under way.
document.getAnimations ??= () => [];
// happy-dom's computed style is the declared style: no initial values, and no
// shorthand expanded. The runtime names the values it acts on, so a property left
// unset reads as its initial value, but it reads overflow per axis, which a test may
// declare with the shorthand. So each axis computes as CSS says: from its own
// declaration or the shorthand, and `visible` (or `clip`) beside an axis that scrolls
// computes `auto` (or `hidden`).
const SCROLLING = /^(auto|scroll|hidden)$/;
const declaredStyle = window.getComputedStyle.bind(window);
window.getComputedStyle = (element, pseudo) => {
  const style = declaredStyle(element, pseudo);
  // Read at each access, as a browser's computed style is live.
  const axis = (name) => {
    const [x = "visible", y = x] = style.overflow.split(/\s+/).filter(Boolean);
    const declared = {
      overflowX: style.overflowX || x,
      overflowY: style.overflowY || y,
    };
    const other = declared[name === "overflowX" ? "overflowY" : "overflowX"];
    if (!SCROLLING.test(other)) return declared[name];
    return { visible: "auto", clip: "hidden" }[declared[name]] ?? declared[name];
  };
  return new Proxy(style, {
    get(target, key) {
      if (key === "overflowX" || key === "overflowY") return axis(key);
      const value = Reflect.get(target, key, target);
      if (value === "" && Object.hasOwn(UNTRANSFORMED, key)) return UNTRANSFORMED[key];
      return typeof value === "function" ? value.bind(target) : value;
    },
  });
};
// A box's transforms compute to their initial values where nothing declares them, which
// a scroll's axes read (dom/element-axes.js) to carry a glide's travel to the window.
const UNTRANSFORMED = { rotate: "none", scale: "none", transform: "none", zoom: "1" };
// What a delivered document's prepaint declares before any module runs
// (`runtime/prepaint.js`): the page's storage scope, "" for a page at the origin's root.
document.documentElement.dataset.lfPageScope = "";
await import("../../browser/runtime/base/document-inputs.js");
await import("../../browser/runtime/prepaint.js");
// And the runtime sheets every delivery carries (`delivery_sheets` in
// revision_delivery.py), which `runtime/base/stylesheets.js` constructs as it evaluates.
// Nothing here is laid out, so their rules are empty.
const sheets = document.createElement("script");
sheets.type = "application/json";
sheets.dataset.lfRuntime = "";
sheets.dataset.lfSheets = "";
sheets.textContent = JSON.stringify({ chrome: "", marks: "" });
document.head.append(sheets);

// A test's comparisons go through `assert.mjs`, which writes a node as its opening tag.
const ASSERT = new URL("./assert.mjs", import.meta.url).href;

registerHooks({
  resolve(specifier, context, next) {
    if (specifier === "node:assert/strict" && context.parentURL !== ASSERT)
      return { url: ASSERT, shortCircuit: true };
    // An unanswered one falls through, so it reads as the module Node could not find
    // rather than as a missing file at a path the layer would never have served it at.
    const file = served(specifier);
    if (file) return { url: pathToFileURL(file).href, shortCircuit: true };
    return next(specifier, context);
  },
});
