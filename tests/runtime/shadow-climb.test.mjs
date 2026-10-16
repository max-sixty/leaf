/* The climbs out of a node: its parent, then the host of the shadow tree it stands in,
   and nothing past a tree that no shadow root holds; as rendered, a slotted node's slot
   first. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { composedParentNode, renderedUnder, under, upFrom } from "/runtime/shadow.js";

test("a climb crosses a shadow root to its host", () => {
  const host = document.createElement("div");
  const inner = document.createElement("span");
  host.attachShadow({ mode: "open" }).append(inner);
  assert.equal(upFrom(inner), host);
});

test("a climb stops at the top of a detached subtree, a link's included", () => {
  // A link answers `host` with its URL's host name, which the climb once took for a
  // node and then threw on.
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
