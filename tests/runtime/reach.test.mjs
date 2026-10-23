/* Reach discovers declared scroll surfaces through every nested shadow stage.
   happy-dom has no layout, so this checks style discovery, not measured overflow. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { watchArrivalsIn } from "/runtime/arrivals.js";
import { watchCodeBlocks } from "/runtime/code-copy.js";
import { reachScrollers } from "/runtime/reach.js";
import { registry } from "/runtime/registry.js";

test("a sweep reaches a scroll surface in a nested declared shadow stage", () => {
  const tag = "x-reach-nested-stage";
  registry[tag] = { "x-shadow": true };
  const outer = document.createElement(tag);
  const outerRoot = outer.attachShadow({ mode: "open" });
  const inner = document.createElement(tag);
  const innerRoot = inner.attachShadow({ mode: "open" });
  const surface = document.createElement("div");
  surface.className = "scroll";
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
  authored.className = "scroll";
  authored.style.overflow = "auto";
  const native = document.createElement("pre");
  native.style.overflow = "auto";
  native.textContent = "a long native code line";
  try {
    document.body.append(authored, native);
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.ok(native.classList.contains("scroll"));
    await new Promise((resolve) => requestAnimationFrame(resolve));
    assert.equal(authored.getAttribute("data-lf-scrolls"), "");
    assert.equal(native.getAttribute("data-lf-scrolls"), "");
    authored.classList.remove("scroll");
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(authored.hasAttribute("data-lf-scrolls"), false);
  } finally {
    authored.remove();
    native.remove();
  }
});
