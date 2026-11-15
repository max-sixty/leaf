/* Reach discovers declared scroll surfaces through every nested shadow stage, and lends
   a stop to each that overflows with no control of its own. happy-dom has no layout, so
   a test states each box's overflow. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { watchArrivalsIn } from "/runtime/arrivals.js";
import { watchCodeBlocks } from "/runtime/code-copy.js";
import { reachScrollers } from "/runtime/reach.js";
import { registry } from "/runtime/registry.js";
import { layoutChanged } from "/runtime/widget-upgrade.js";

test("a sweep reaches a scroll surface in a nested declared shadow stage", () => {
  const tag = "x-reach-nested-stage";
  registry[tag] = { "x-shadow": true };
  const outer = document.createElement(tag);
  const outerRoot = outer.attachShadow({ mode: "open" });
  const inner = document.createElement(tag);
  const innerRoot = inner.attachShadow({ mode: "open" });
  const surface = document.createElement("div");
  surface.className = "lf-scroll";
  surface.style.overflow = "auto";
  const contents = new Set();
  for (let index = 0; index < 32; index++) {
    const span = document.createElement("span");
    span.textContent = "ordinary content";
    contents.add(span);
    (index % 2 ? surface : outerRoot).append(span);
  }
  innerRoot.append(surface);
  outerRoot.append(inner);
  document.body.append(outer);
  watchArrivalsIn(outerRoot);
  watchArrivalsIn(innerRoot);
  const computedStyle = globalThis.getComputedStyle;
  const inspectedContents = new Set();
  globalThis.getComputedStyle = (node, ...args) => {
    if (contents.has(node)) inspectedContents.add(node);
    return computedStyle(node, ...args);
  };
  try {
    reachScrollers(document.body);
    assert.equal(inspectedContents.size, 0, "ordinary content needs no style read");
    assert.equal(surface.getAttribute("data-lf-scrolls"), "");
  } finally {
    globalThis.getComputedStyle = computedStyle;
    outer.remove();
    delete registry[tag];
  }
});

test("late authored and native scroll surfaces enter reach", async () => {
  reachScrollers(document.body);
  watchCodeBlocks();
  const authored = document.createElement("div");
  authored.className = "lf-scroll";
  authored.style.overflow = "auto";
  const native = document.createElement("pre");
  native.style.overflow = "auto";
  native.textContent = "a long native code line";
  try {
    document.body.append(authored, native);
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.ok(native.hasAttribute("data-lf-scroll"));
    await new Promise((resolve) => requestAnimationFrame(resolve));
    assert.equal(authored.getAttribute("data-lf-scrolls"), "");
    assert.equal(native.getAttribute("data-lf-scrolls"), "");
    authored.classList.remove("lf-scroll");
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(authored.hasAttribute("data-lf-scrolls"), false);
  } finally {
    authored.remove();
    native.remove();
  }
});

// A box overflows or fits as a test says, since nothing is laid out here.
/** @param {Element} box @param {number} height */
const holds = (box, height) => {
  Object.defineProperty(box, "scrollHeight", { configurable: true, get: () => height });
  Object.defineProperty(box, "clientHeight", { configurable: true, get: () => 100 });
};
const painted = () => new Promise((resolve) => setTimeout(resolve, 0));

test("a box reads what it holds once, until that changes, and counts a stop lent inside it", async () => {
  const outer = document.createElement("div");
  const inner = document.createElement("div");
  for (const box of [outer, inner]) {
    box.className = "lf-scroll";
    box.style.overflow = "auto";
  }
  /** @type {Element[]} */
  const lines = [];
  for (let at = 0; at < 40; at++) {
    const line = document.createElement("div");
    const words = document.createElement("span");
    words.textContent = `line ${at}`;
    line.append(words);
    lines.push(line, words);
    (at < 20 ? outer : inner).append(line);
  }
  outer.append(inner);
  const elsewhere = document.createElement("p");
  holds(outer, 1000);
  holds(inner, 100);
  document.body.append(outer, elsewhere);
  try {
    reachScrollers(document.body);
    await painted();
    // Only the outer box has something out of sight, and no control to stand on.
    assert.equal(outer.getAttribute("tabindex"), "0");
    assert.equal(inner.getAttribute("tabindex"), null);

    // A layout notice asks again whether each box scrolls, and reads none of its lines.
    const matches = Element.prototype.matches;
    const read = new Set();
    Element.prototype.matches = function (...selectors) {
      if (lines.includes(this)) read.add(this);
      return matches.apply(this, selectors);
    };
    try {
      layoutChanged(elsewhere);
      await painted();
    } finally {
      Element.prototype.matches = matches;
    }
    assert.equal(read.size, 0, "a paint read the lines of a box that had not changed");

    // The inner box comes to scroll and takes a stop, which the outer box then holds,
    // in the same pass, so it gives its own back.
    holds(inner, 1000);
    layoutChanged(elsewhere);
    await painted();
    assert.equal(inner.getAttribute("tabindex"), "0");
    assert.equal(outer.getAttribute("tabindex"), null);
    assert.equal(outer.hasAttribute("data-lf-lent-reach-stop"), false);

    // A control put deep in the inner box is somewhere the user can stand.
    const control = document.createElement("button");
    control.tabIndex = 0;
    lines.at(-2)?.append(control);
    layoutChanged(elsewhere);
    await painted();
    assert.equal(inner.getAttribute("tabindex"), null);
    assert.equal(inner.hasAttribute("data-lf-lent-reach-stop"), false);
  } finally {
    outer.remove();
    elsewhere.remove();
  }
});
