import assert from "node:assert/strict";
import test from "node:test";
import {
  obligationsByRegion,
  obligationPlace,
  readObligations,
  subjectPlace,
} from "/runtime/records/obligations/place.js";
import { obligationAt, obligationHolding } from "/runtime/records/current-target.js";
import { pageReadingVersion } from "/runtime/readings/passages.js";
import { applicationState } from "/runtime/state/semantic-state.js";
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
  // A question inside a proposal's new text: the proposal's source holds the section
  // framing the question, where arrival puts the user on the question. Nothing frames
  // the proposal, so it stands at its own source.
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
      assert.equal(obligationPlace(change, items).node, at("change"));
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
      end: null,
      next_actor: "user",
      state: "waiting",
      reason: null,
      outcome: null,
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
  // Where each stands (`standing.py`): open, withdrawn, or answered.
  const OPEN = { state: "waiting", outcome: null };
  const WITHDRAWN = { state: "done", outcome: "dropped" };
  const ANSWERED = { state: "done", outcome: "done" };
  const item = (id, standing = OPEN, kind = "widget") => ({
    id: `${kind}:${id}`,
    thread: null,
    message: null,
    ...standing,
    source: { kind, id },
    prompt: { target: id },
  });
  const items = [
    item("first"),
    item("gone", WITHDRAWN),
    item("outside", ANSWERED),
    item("missing"),
    item("item", ANSWERED),
    item("first", OPEN, "reply"),
  ];
  const regions = ["queue", "item", "first", "outside"].map((id) =>
    document.getElementById(id),
  );
  try {
    const held = obligationsByRegion(regions, items);
    assert.deepEqual(
      Object.fromEntries(
        regions.map((region) => [region.id, held.get(region).map((item) => item.id)]),
      ),
      {
        queue: ["widget:first", "widget:item"],
        item: ["widget:first", "widget:item"],
        first: ["widget:first"],
        outside: ["widget:outside"],
      },
    );
  } finally {
    document.body.replaceChildren();
  }
});

// The page's published obligations, as the server serves them.
/** @param {readonly object[]} obligations */
function publish(obligations) {
  applicationState.identify(1);
  assert.ok(
    applicationState.adopt(
      servedState({ browser: { views: { 1: { obligations } } } }),
      {
        ...applicationState.read().document,
        registry: { $states: {} },
        authored: new Map(),
        descriptors: new Map(),
      },
    ),
  );
}
// A served widget obligation waiting on `next_actor`, in a message's markup where
// `thread` names one.
const served = (
  id,
  {
    thread = null,
    next_actor = "user",
    state = "waiting",
    outcome = state === "done" ? "done" : null,
  } = {},
) => ({
  id: `widget:${id}`,
  source: { kind: "widget", id, tag: "lf-probe" },
  thread,
  message: thread && "m-1",
  prompt: { text: `Choose ${id}.`, target: id },
  answer: null,
  end: null,
  next_actor,
  state,
  reason: null,
  outcome,
});

test("a region's reading is the page's, holding what the region holds in the page's order", () => {
  // A message's widget can stand in a region too, as a thread drawn in a page's reader
  // does, and keeps its place in the inventory's order among the page's own. A
  // withdrawn one, which the page's reading still lists, stands in no region.
  document.body.innerHTML =
    '<section id="queue"><div id="a"></div><div id="sent"></div><div id="gone"></div>' +
    '<div id="c"></div></section><div id="outside"></div>';
  publish([
    served("a"),
    served("sent", { thread: "t-1" }),
    served("outside"),
    served("gone", { next_actor: null, state: "done", outcome: "dropped" }),
    served("c", { next_actor: null, state: "done" }),
  ]);
  try {
    const page = readObligations();
    const queue = readObligations(document.getElementById("queue"));
    const ids = (/** @type {readonly {id: string}[]} */ items) =>
      items.map((item) => item.id);
    assert.equal(queue.phase, page.phase);
    assert.ok(ids(page.all).includes("widget:gone"));
    assert.deepEqual(ids(queue.all), ["widget:a", "widget:sent", "widget:c"]);
    assert.deepEqual(ids(queue.user), ["widget:a", "widget:sent"]);
    assert.deepEqual(ids(queue.unanswered), ["widget:a", "widget:sent"]);
    // Each list holds the page's list's members that the region holds, in its order.
    for (const list of /** @type {const} */ (["all", "user", "unanswered"]))
      assert.deepEqual(
        ids(queue[list]),
        ids(page[list].filter((item) => queue.all.includes(item))),
      );
    assert.deepEqual(ids(readObligations(document.getElementById("sent")).all), [
      "widget:sent",
    ]);
  } finally {
    document.body.replaceChildren();
  }
});

test("a region's reading follows a widget moved to another region", () => {
  // The page's filing is kept for the inventory, which a move leaves as it is, and for
  // the page's reading, which the move changes.
  document.body.innerHTML =
    '<section id="first"><div><div id="ask"></div></div></section><section id="second"></section>';
  publish([served("ask")]);
  const held = (/** @type {string} */ region) =>
    readObligations(document.getElementById(region)).all.map((item) => item.id);
  try {
    assert.deepEqual([held("first"), held("second")], [["widget:ask"], []]);
    document
      .getElementById("second")
      .append(document.getElementById("ask").parentElement);
    assert.deepEqual([held("first"), held("second")], [[], ["widget:ask"]]);
  } finally {
    document.body.replaceChildren();
  }
});

test("reading every region of a page reads each obligation's place once", () => {
  // A side list of tabs or a deck reads every panel or card in one render, so its cost
  // is the obligations, not the obligations times the regions. Counted in the ids the
  // placement looks up.
  /** @param {number} n */
  const lookups = (n) => {
    const ids = Array.from({ length: n }, (_, k) => `r${k}`);
    document.body.innerHTML = ids
      .map((id) => `<section id="${id}"><div id="${id}-ask"></div></section>`)
      .join("");
    publish(ids.map((id) => served(`${id}-ask`)));
    const regions = ids.map((id) => document.getElementById(id));
    const lookup = document.getElementById;
    let count = 0;
    document.getElementById = function (id) {
      count++;
      return lookup.call(this, id);
    };
    try {
      assert.deepEqual(
        regions.map((region) => readObligations(region).all.map((item) => item.id)),
        ids.map((id) => [`widget:${id}-ask`]),
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

test("whether a region asks the user is read from the captured widgets, not its elements", () => {
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
            awaits: { value: "choose" },
            facts: { answered: { type: "boolean" } },
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
      descriptor("sent", "thread", true),
    ]),
  };
  assert.ok(applicationState.adopt(servedState(), captured));
  const rows = Array.from({ length: 5000 }, (_, k) => `<div>Row ${k}</div>`).join("");
  document.body.innerHTML =
    '<main id="page"><section id="asks"><div><div id="ask"></div></div></section>' +
    `<section id="notes"><div id="note"></div>${rows}</section>` +
    '<section id="message"><div id="sent"></div></section></main>';
  const regions = ["page", "asks", "notes", "message"].map((id) =>
    document.getElementById(id),
  );
  // The page's watcher reads what the rows' insertion added, once, for every reading of
  // the page; what is counted is the reading of the regions.
  pageReadingVersion();
  const search = Element.prototype.querySelectorAll;
  let searched = 0;
  Element.prototype.querySelectorAll = function (...selector) {
    searched++;
    return search.apply(this, selector);
  };
  try {
    assert.deepEqual(
      regions.filter((region) => readObligations(region).asks).map(({ id }) => id),
      ["page", "asks", "message"],
    );
  } finally {
    Element.prototype.querySelectorAll = search;
    document.body.replaceChildren();
  }
  assert.equal(searched, 0);
});
