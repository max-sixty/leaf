import assert from "node:assert/strict";
import test from "node:test";
import { asksIn, askPlace } from "/runtime/asks/place.js";
import { askHolding } from "/runtime/standing-target.js";

test("shared context keeps placement and containment specific to each ask", () => {
  document.body.innerHTML =
    '<section id="context"><div id="first"><button>One</button></div><div id="second"><button>Two</button></div></section>';
  const ask = (id) => ({
    id: `widget:${id}`,
    thread: null,
    message: null,
    source: { kind: "widget", id },
    prompt: { target: "context" },
  });
  const first = ask("first");
  const second = ask("second");
  const asks = [first, second];
  try {
    assert.equal(askPlace(first, [first]).node.id, "context");
    for (const record of asks) {
      const place = askPlace(record, asks);
      assert.equal(place.source.id, record.source.id);
      assert.equal(place.node, place.source);
      assert.equal(place.context.id, "context");
      assert.equal(askHolding(asks, place.source.firstElementChild), record);
    }
    assert.equal(askHolding(asks, document.getElementById("context")), null);
  } finally {
    document.body.replaceChildren();
  }
});

test("a region holds the live widget asks whose source is it or stands under it", () => {
  document.body.innerHTML =
    '<section id="queue"><div id="item"><div id="first"></div><div id="gone"></div></div></section><div id="outside"></div>';
  const ask = (id, status = "open", kind = "widget") => ({
    id: `${kind}:${id}`,
    thread: null,
    message: null,
    status,
    source: { kind, id },
    prompt: { target: id },
  });
  const asks = [
    ask("first"),
    ask("gone", "withdrawn"),
    ask("outside", "answered"),
    ask("missing"),
    ask("item", "answered"),
    ask("first", "open", "reply"),
  ];
  const ids = (region) =>
    asksIn(document.getElementById(region), asks).map((held) => held.id);
  try {
    assert.deepEqual(ids("queue"), ["widget:first", "widget:item"]);
    assert.deepEqual(ids("item"), ["widget:first", "widget:item"]);
    assert.deepEqual(ids("first"), ["widget:first"]);
    assert.deepEqual(ids("outside"), ["widget:outside"]);
  } finally {
    document.body.replaceChildren();
  }
});
