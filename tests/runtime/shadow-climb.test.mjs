/* The climbs out of a node: its parent, then the host of the shadow tree it stands in,
   and nothing past a tree that no shadow root holds; as rendered, a slotted node's slot
   first. */

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  eachRenderedChild,
  eachRenderedElement,
  renderedParent,
  composedParentNode,
  renderedUnder,
  under,
  upFrom,
} from "/runtime/lib/shadow-tree.js";

test("a climb crosses a shadow root to its host", () => {
  const host = document.createElement("div");
  const inner = document.createElement("span");
  host.attachShadow({ mode: "open" }).append(inner);
  assert.equal(upFrom(inner), host);
});

test("a climb stops at the top of a detached subtree, a link's included", () => {
  // A link answers `host` with its URL's host name, which a climb that took it for a
  // node would then throw on.
  const link = document.createElement("a");
  link.href = "http://127.0.0.1:4000/";
  const text = document.createTextNode("words");
  link.append(text);
  assert.equal(upFrom(text), link);
  assert.equal(upFrom(link), null);
  assert.ok(!under(text, document));
});

test("containment stops at a root as well as an element", () => {
  const section = document.createElement("section");
  const host = document.createElement("div");
  const root = host.attachShadow({ mode: "open" });
  const inner = document.createElement("span");
  root.append(inner);
  section.append(host);
  document.body.append(section);
  assert.equal(composedParentNode(inner), root);
  assert.equal(composedParentNode(root), host);
  assert.ok(under(inner, root));
  assert.ok(under(inner, section));
  assert.ok(under(inner, document));
  assert.ok(!under(section, host));
  section.remove();
});

test("a slotted node is under its slot as rendered, and its host as composed", () => {
  const host = document.createElement("div");
  const frame = document.createElement("div");
  const slot = document.createElement("slot");
  frame.append(slot);
  host.attachShadow({ mode: "open" }).append(frame);
  const child = document.createElement("p");
  host.append(child);
  document.body.append(host);
  // happy-dom assigns no slots, so the child states the one a browser gives it.
  Object.defineProperty(child, "assignedSlot", { value: slot });
  assert.ok(renderedUnder(child, frame));
  assert.ok(renderedUnder(child, host.shadowRoot));
  assert.ok(!under(child, frame));
  assert.ok(under(child, host));
  host.remove();
});

/** @param {Node} node @param {Parameters<typeof eachRenderedChild>[2]} [rootOf] */
const drawnChildren = (node, rootOf) => {
  /** @type {Node[]} */
  const children = [];
  eachRenderedChild(node, (child) => void children.push(child), rootOf);
  return children;
};

// The step down is the climb up taken the other way, so a walk down from a host meets
// each node the climb from it passes: what the host's tree draws in place of its
// children, each light child through the slot that draws it, a slot forwarded into
// another among what that one draws, and a slot's own children where nothing is
// assigned to it.
test("the step down meets what the climb up passes, slots and their fallback too", () => {
  const host = document.createElement("div");
  const root = host.attachShadow({ mode: "open" });
  const named = document.createElement("slot");
  named.name = "named";
  const empty = document.createElement("slot");
  empty.name = "empty";
  const fallback = document.createElement("em");
  empty.append(fallback);
  const inner = document.createElement("div");
  const innerSlot = document.createElement("slot");
  inner.attachShadow({ mode: "open" }).append(innerSlot);
  const forwarded = document.createElement("slot");
  forwarded.name = "forwarded";
  inner.append(forwarded);
  root.append(named, empty, inner);
  const item = document.createElement("span");
  item.slot = "named";
  const deeper = document.createElement("b");
  deeper.slot = "forwarded";
  host.append(item, deeper);
  document.body.append(host);
  try {
    assert.deepEqual(drawnChildren(host), [named, empty, inner]);
    assert.deepEqual(drawnChildren(named), [item]);
    assert.deepEqual(drawnChildren(empty), [fallback]);
    assert.deepEqual(drawnChildren(inner), [innerSlot]);
    assert.deepEqual(drawnChildren(innerSlot), [forwarded]);
    assert.deepEqual(drawnChildren(forwarded), [deeper]);
    for (const parent of [host, named, empty, inner, innerSlot, forwarded])
      for (const child of drawnChildren(parent))
        assert.equal(renderedParent(child), parent);
    // A walk of elements meets the same elements, and steps over the text between them.
    named.before("words");
    for (const parent of [host, named, empty, inner, innerSlot, forwarded]) {
      /** @type {Element[]} */
      const elements = [];
      eachRenderedElement(parent, (child) => void elements.push(child));
      assert.deepEqual(
        elements,
        drawnChildren(parent).filter((child) => child.nodeType === Node.ELEMENT_NODE),
      );
    }
    // A walk of one tree enters no host's root, and reads its light children.
    assert.deepEqual(
      drawnChildren(host, () => null),
      [item, deeper],
    );
  } finally {
    host.remove();
  }
});

test("a slot outside a shadow tree draws its own children", () => {
  const slot = document.createElement("slot");
  const child = document.createElement("p");
  slot.append(child);
  document.body.append(slot);
  try {
    assert.deepEqual(drawnChildren(slot), [child]);
  } finally {
    slot.remove();
  }
});

test("a walk of elements steps over the text a slot is assigned", () => {
  const host = document.createElement("div");
  const slot = document.createElement("slot");
  host.attachShadow({ mode: "open" }).append(slot);
  const item = document.createElement("span");
  host.append("before", item, "after");
  document.body.append(host);
  try {
    assert.equal(drawnChildren(slot).length, 3);
    /** @type {Element[]} */
    const elements = [];
    eachRenderedElement(slot, (child) => void elements.push(child));
    assert.deepEqual(elements, [item]);
  } finally {
    host.remove();
  }
});
