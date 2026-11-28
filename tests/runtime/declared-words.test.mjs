/* What Leaf sets on an element from its declaration alone, so a widget that draws
   nothing needs no module: a reading role's ARIA role and name, and a pane's region. */
import assert from "node:assert/strict";
import test from "node:test";
import { adoptRegistry } from "/runtime/state/registry.js";
import { markDeclared, watchPanes } from "/runtime/records/declared-words.js";

// Delivery paints a page's document from the same table (test_revision_delivery.py).
test("a message's element in a reading role says its ARIA role and its label", () => {
  adoptRegistry({
    $layer: { generation: "reading-role-aria" },
    "lf-zone": { "reading-role": "pane" },
    "lf-set": { "reading-role": "group" },
  });
  const message = document.createElement("template");
  message.innerHTML =
    '<lf-zone id="queue" label="Queue"><div></div></lf-zone>' +
    '<lf-zone id="log" label="Log" role="log"><div></div></lf-zone>' +
    '<lf-set id="kit" label="Kit" aria-label="Field kit"></lf-set>';
  markDeclared(message.content);
  const said = (id) => {
    const element = message.content.getElementById(id);
    return ["data-lf-reading-role", "role", "aria-label"].map((name) =>
      element.getAttribute(name),
    );
  };
  assert.deepEqual(said("queue"), ["pane", "region", "Queue"]);
  // The role and the name an author writes are the element's.
  assert.deepEqual(said("log"), ["pane", "log", "Log"]);
  assert.deepEqual(said("kit"), ["group", "group", "Field kit"]);
});

// A second observer acknowledges delivery of the same mutation batch as the watch.
async function mutate(change) {
  const observed = new Promise((resolve) => {
    const observer = new MutationObserver(() => {
      observer.disconnect();
      resolve();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  });
  change();
  await observed;
}

test("a pane's body is its reading region, and so is a body a revision brings in", async () => {
  adoptRegistry({
    $layer: { generation: "pane-regions" },
    "lf-zone": { "reading-role": "pane" },
  });
  document.body.innerHTML =
    '<lf-zone id="queue" label="Queue"><header>Queue</header><div id="first"></div>' +
    "<footer></footer></lf-zone>";
  watchPanes();
  const pane = document.getElementById("queue");
  const region = () =>
    [pane, ...pane.children].map((element) => [
      element.localName,
      element.getAttribute("data-lf-scroll-host"),
      element.getAttribute("data-lf-scroll"),
    ]);
  assert.deepEqual(region(), [
    ["lf-zone", "body", null],
    ["header", null, null],
    ["div", null, "body"],
    ["footer", null, null],
  ]);
  const body = document.createElement("section");
  await mutate(() => pane.querySelector("#first").replaceWith(body));
  assert.equal(body.getAttribute("data-lf-scroll"), "body");
  document.body.replaceChildren();
});
