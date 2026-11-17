import assert from "node:assert/strict";
import test from "node:test";
import {
  obligationsByRegion,
  obligationsIn,
  obligationPlace,
  regionsAwaiting,
  subjectPlace,
} from "/runtime/obligations/place.js";
import { obligationAt, obligationHolding } from "/runtime/current-target.js";
import { applicationState } from "/runtime/semantic-state.js";
import { servedState } from "../served.mjs";

test("shared context keeps placement and containment specific to each obligation", () => {
  document.body.innerHTML =
    '<section id="context"><div id="first"><button>One</button></div><div id="second"><button>Two</button></div></section>';
  const item = (id) => ({
    id: `widget:${id}`,
    thread: null,
    message: null,
    source: { kind: "widget", id },
    prompt: { target: "context" },
  });
  const first = item("first");
  const second = item("second");
  const items = [first, second];
  try {
    assert.equal(obligationPlace(first, [first]).node.id, "context");
    for (const record of items) {
      const place = obligationPlace(record, items);
      assert.equal(place.source.id, record.source.id);
      assert.equal(place.node, place.source);
      assert.equal(place.context.id, "context");
      assert.equal(obligationHolding(items, place.source.firstElementChild), record);
    }
    assert.equal(obligationHolding(items, document.getElementById("context")), null);
  } finally {
    document.body.replaceChildren();
  }
});

test("the innermost obligation holding a node is where the user stands", () => {
  // A question inside a proposal's new text: the proposal's source holds the question's
  // enclosing widget, where arrival puts the user on the question.
  document.body.innerHTML =
    '<div id="change"><p id="text">Walk outside.</p><section id="ask"><h4>Which route?</h4><div id="route"><button>Garden</button></div></section></div>';
  const item = (source, target) => ({
    id: `widget:${source}`,
    thread: null,
    message: null,
    source: { kind: "widget", id: source },
    prompt: { target },
  });
  const change = item("change", "change");
  const route = item("route", "ask");
  const at = (id) => document.getElementById(id);
  try {
    for (const items of [
      [change, route],
      [route, change],
    ]) {
      assert.equal(obligationHolding(items, at("ask")), route);
      assert.equal(obligationHolding(items, at("ask").firstElementChild), route);
      assert.equal(obligationHolding(items, at("route").firstElementChild), route);
      assert.equal(obligationHolding(items, at("text")), change);
    }
  } finally {
    document.body.replaceChildren();
  }
});

test("the obligation at a node costs as much on a page of 64 obligations as of 8", () => {
  // A keystroke asks where the user stands many times over, so once the page's
  // inventory is published, a lookup in it reads only the places named at the node's
  // ancestors. Its work is counted in the map entries it writes.
  applicationState.identify(1);
  applicationState.captureDocument({
    ...applicationState.read().document,
    registry: { $states: {} },
    authored: new Map(),
    descriptors: new Map(),
  });
  /** @param {number} n */
  const writes = (n) => {
    const ids = Array.from({ length: n }, (_, k) => `w${k}`);
    document.body.innerHTML = ids
      .map((id) => `<section id="${id}"><button>${id}</button></section>`)
      .join("");
    const obligations = ids.map((id) => ({
      id: `widget:${id}`,
      source: { kind: "widget", id },
      thread: null,
      message: null,
      prompt: { text: `Choose ${id}.`, target: id },
      answer: null,
      status: "open",
      next_actor: "user",
    }));
    applicationState.adopt(servedState({ browser: { views: { 1: { obligations } } } }));
    const button = document.querySelector("#w3 button");
    assert.equal(obligationAt(button)?.id, "widget:w3");
    const set = Map.prototype.set;
    let count = 0;
    Map.prototype.set = function (...entry) {
      count++;
      return set.apply(this, entry);
    };
    try {
      assert.equal(obligationAt(button)?.id, "widget:w3");
    } finally {
      Map.prototype.set = set;
    }
    return count;
  };
  try {
    assert.equal(writes(64), writes(8));
  } finally {
    document.body.replaceChildren();
  }
});

test("a region holds the live widget obligations whose source is it or stands under it", () => {
  document.body.innerHTML =
    '<section id="queue"><div id="item"><div id="first"></div><div id="gone"></div></div></section><div id="outside"></div>';
  const item = (id, status = "open", kind = "widget") => ({
    id: `${kind}:${id}`,
    thread: null,
    message: null,
    status,
    source: { kind, id },
    prompt: { target: id },
  });
  const items = [
    item("first"),
    item("gone", "withdrawn"),
    item("outside", "answered"),
    item("missing"),
    item("item", "answered"),
    item("first", "open", "reply"),
  ];
  const ids = (region) =>
    obligationsIn(document.getElementById(region), items).map((held) => held.id);
  try {
    assert.deepEqual(ids("queue"), ["widget:first", "widget:item"]);
    assert.deepEqual(ids("item"), ["widget:first", "widget:item"]);
    assert.deepEqual(ids("first"), ["widget:first"]);
    assert.deepEqual(ids("outside"), ["widget:outside"]);
    const regions = ["queue", "item", "first", "outside"].map((id) =>
      document.getElementById(id),
    );
    const byRegion = obligationsByRegion(regions, items);
    for (const region of regions)
      assert.deepEqual(
        byRegion.get(region).map((held) => held.id),
        ids(region.id),
      );
  } finally {
    document.body.replaceChildren();
  }
});

test("placing an inventory in many regions reads each obligation's place once", () => {
  // A side list of tabs or a deck counts every panel or card in one render, so its
  // cost is the obligations, not the obligations times the regions. Counted in the
  // ids the placement looks up.
  /** @param {number} n */
  const lookups = (n) => {
    const ids = Array.from({ length: n }, (_, k) => `r${k}`);
    document.body.innerHTML = ids
      .map((id) => `<section id="${id}"><div id="${id}-ask"></div></section>`)
      .join("");
    const items = ids.map((id) => ({
      id: `widget:${id}-ask`,
      thread: null,
      message: null,
      status: "open",
      source: { kind: "widget", id: `${id}-ask` },
      prompt: { target: `${id}-ask` },
    }));
    const regions = ids.map((id) => document.getElementById(id));
    const lookup = document.getElementById;
    let count = 0;
    document.getElementById = function (id) {
      count++;
      return lookup.call(this, id);
    };
    try {
      const held = obligationsByRegion(regions, items);
      assert.deepEqual(
        regions.map((region) => held.get(region).map((item) => item.id)),
        items.map((item) => [item.id]),
      );
    } finally {
      document.getElementById = lookup;
    }
    return count / n;
  };
  try {
    assert.equal(lookups(64), lookups(8));
  } finally {
    document.body.replaceChildren();
  }
});

test("a subject stands at the element it names, or nowhere", () => {
  document.body.innerHTML =
    '<main><section id="notes"><h2>Notes</h2><p>Words.</p></section></main>';
  const at = (id) => document.getElementById(id);
  try {
    assert.equal(subjectPlace({ kind: "element", id: "notes" }), at("notes"));
    assert.equal(subjectPlace({ kind: "thread", id: "th-1" }), null);
    // The page as a whole names no element, so a subject on it stands nowhere.
    assert.equal(subjectPlace({ kind: "page" }), null);
  } finally {
    document.body.replaceChildren();
  }
});

test("which regions ask the user is read from the captured widgets, not the regions' elements", () => {
  // A side list keeps room on a panel's row for the answer to what its markup asks,
  // from before the first reading lists the obligation, in the page or in a message's
  // markup. A panel can hold a text document of 100,000 rows, so the answer comes from
  // the captured widgets, each climbing once, and no region is searched: rows cost
  // nothing, and a widget that asks nothing marks no region.
  /** @param {string} id @param {"page" | "thread"} kind @param {boolean} awaits */
  const descriptor = (id, kind, awaits) => [
    id,
    {
      id,
      tag: "lf-probe",
      document: kind === "page" ? { kind, revision: 1 } : { kind, thread: "t" },
      declaration: awaits
        ? {
            state: {
              awaits: { value: "choose" },
            },
          }
        : {},
      parent: null,
      ancestors: [],
      quoted: false,
    },
  ];
  applicationState.identify(1);
  const captured = {
    ...applicationState.read().document,
    registry: { $states: {} },
    authored: new Map(),
    descriptors: new Map([
      descriptor("ask", "page", true),
      descriptor("note", "page", false),
      descriptor("frozen", "thread", true),
    ]),
  };
  assert.ok(applicationState.adopt(servedState(), captured));
  const rows = Array.from({ length: 5000 }, (_, k) => `<div>Row ${k}</div>`).join("");
  document.body.innerHTML =
    '<main id="page"><section id="asks"><div><div id="ask"></div></div></section>' +
    `<section id="notes"><div id="note"></div>${rows}</section>` +
    '<section id="message"><div id="frozen"></div></section></main>';
  const regions = ["page", "asks", "notes", "message"].map((id) =>
    document.getElementById(id),
  );
  const search = Element.prototype.querySelectorAll;
  let searched = 0;
  Element.prototype.querySelectorAll = function (...selector) {
    searched++;
    return search.apply(this, selector);
  };
  try {
    assert.deepEqual([...regionsAwaiting(regions)].map((region) => region.id).sort(), [
      "asks",
      "message",
      "page",
    ]);
  } finally {
    Element.prototype.querySelectorAll = search;
    document.body.replaceChildren();
  }
  assert.equal(searched, 0);
});
