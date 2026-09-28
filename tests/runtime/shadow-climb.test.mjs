/* The climb out of a node: its parent, then the host of the shadow tree it stands in,
   and nothing past a tree that no shadow root holds. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { upFrom } from "/runtime/shadow.js";

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
});
