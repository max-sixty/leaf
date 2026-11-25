import assert from "node:assert/strict";
import test from "node:test";
import { createAnnotationInventory } from "/runtime/features/annotation-inventory.js";
import { contributionEntry } from "/runtime/features/contribution-controls.js";
import { registerContribution } from "/runtime/features/contributions.js";
import { resolvedElement, resolvedPassage } from "/runtime/readings/resolved-target.js";
import { resolveAnchor } from "/runtime/readings/anchor-resolution.js";
import { clearDraft, commentContext, saveDraft } from "/runtime/records/drafts.js";
import { registry } from "/runtime/state/registry.js";
import { applicationState } from "/runtime/state/semantic-state.js";
import { servedState, servedThread } from "../served.mjs";

const obligation = (id) => ({
  id,
  thread: null,
  message: null,
  source: { kind: "widget", id: "asked" },
  prompt: { target: "asked" },
});

const inventoryOf = (user = []) =>
  createAnnotationInventory({
    readObligations: () => ({ all: user, user }),
    placedAt: () => null,
    openThread() {},
    goToObligation() {},
    scrollToElement() {},
  });

const entryFor = (entries, id) => entries.find((entry) => entry.targetId === id);

test("an entry stays one object until what it is made from changes", () => {
  document.body.innerHTML =
    '<main><p id="asked">A question</p><p id="other">Other</p></main>';
  const asks = [obligation("first")];
  const inventory = inventoryOf(asks);
  const registration = registerContribution({
    key: "probe",
    target: document.getElementById("other"),
    read: () => ({
      entries: [contributionEntry({ key: "go", label: "Go", icon: "check" })],
    }),
    activate() {},
  });
  try {
    const first = inventory.collect();
    const second = inventory.collect();
    assert.notEqual(second, first, "each collection is a reading of its own");
    assert.equal(entryFor(second, "asked"), entryFor(first, "asked"));
    assert.equal(entryFor(second, "other"), entryFor(first, "other"));

    // A producer's publication is a change, whatever it says, since it can carry a
    // command the record's values don't show (features/contribution-controls.js).
    registration.update();
    const published = inventory.collect();
    assert.notEqual(entryFor(published, "other"), entryFor(second, "other"));
    assert.equal(entryFor(published, "asked"), entryFor(second, "asked"));

    // A word the entry says, read off the page.
    document.getElementById("asked").setAttribute("aria-label", "Another question");
    const named = inventory.collect();
    assert.notEqual(entryFor(named, "asked"), entryFor(published, "asked"));
    assert.equal(entryFor(named, "other"), entryFor(published, "other"));

    asks.push(obligation("second"));
    const grown = inventory.collect();
    assert.notEqual(entryFor(grown, "asked"), entryFor(named, "asked"));
    assert.equal(entryFor(grown, "asked").items.length, 2);
  } finally {
    registration.unregister();
    document.body.replaceChildren();
  }
});

test("a kept item acts through the capabilities of the latest reading", () => {
  document.body.innerHTML = '<main><p id="asked">A question</p></main>';
  const inventory = inventoryOf([obligation("first")]);
  try {
    const [entry] = inventory.collect();
    const [item] = entry.items;
    const held = inventory.sourceItem(item);
    const [kept] = inventory.collect();
    assert.equal(kept, entry);
    assert.notEqual(inventory.sourceItem(item), held);
  } finally {
    document.body.replaceChildren();
  }
});

// A passage's row is keyed from a reading of its target's words, which a change to
// another part of the page leaves as they were, as a closed tab's document drawing does:
// the collection that follows reads none of the target's elements.
test("a quoted passage is keyed once while its target's words are unchanged", () => {
  applicationState.identify(1);
  document.body.innerHTML =
    '<main><p id="other">Other words</p><div id="doc" data-lf-projection="w" ' +
    'data-lf-datum="doc"><p>Alpha <b>beta</b> gamma <b>beta</b></p></div></main>';
  const doc = document.getElementById("doc");
  const second = doc.querySelectorAll("b")[1].firstChild;
  const comment = {
    id: "c1",
    seq: 1,
    ts: "2026-09-19T12:00:00+00:00",
    author: "user",
    revision: 1,
    kind: "comment",
    text: "Which beta?",
    attention: true,
    content_version: "c1",
  };
  const thread = servedThread([comment], {
    anchor: { section: "doc", datum: "doc", quote: "beta" },
  });
  applicationState.adopt(
    servedState({ browser: { views: { 1: { thread: { threads: [thread] } } } } }),
  );
  const placement = {
    ...resolvedPassage({ place: doc, segments: [{ node: second, start: 0, end: 4 }] }),
    point: null,
  };
  const inventory = createAnnotationInventory({
    readObligations: () => ({ all: [], user: [] }),
    placedAt: () => placement,
    openThread() {},
    goToObligation() {},
    scrollToElement() {},
  });
  const { matches } = Element.prototype;
  let asked = 0;
  Element.prototype.matches = function (selector) {
    if (doc.contains(this) && this !== doc) asked += 1;
    return matches.call(this, selector);
  };
  const collected = () => {
    asked = 0;
    const entry = inventory.collect().find((each) => each.targetId === "doc");
    return { asked, key: entry.key };
  };
  try {
    const first = collected();
    assert.match(first.key, /\["beta",1\]$/, "the second copy of its words");
    document.getElementById("other").firstChild.data = "Other words edited";
    assert.deepEqual(collected(), { asked: 0, key: first.key });
    // A change to the words it stands in reads them again.
    doc.querySelector("b").firstChild.data = "delta";
    const moved = collected();
    assert.ok(moved.asked > 0);
    assert.match(moved.key, /\["beta",0\]$/, "now the first copy of its words");
  } finally {
    Element.prototype.matches = matches;
    document.body.replaceChildren();
  }
});

// A thread on a part of a picture is at the picture only where focus there stands on
// that part, as a chart's keys stand on a point, and then it is the thread there,
// above one on the whole picture; a node inside another part is about that part alone,
// which no reading of the picture's parts decides.
test("a part's thread is at its picture where focus there stands on the part", () => {
  applicationState.identify(1);
  document.body.innerHTML =
    '<main><lf-plot id="plot"><svg><circle id="p"></circle>' +
    '<g id="q"><text id="inside-q">Q</text></g></svg></lf-plot></main>';
  const plot = /** @type {Element} */ (document.getElementById("plot"));
  const part = (/** @type {string} */ id) =>
    /** @type {Element} */ (document.getElementById(id));
  const comment = (/** @type {string} */ id) => ({
    id,
    seq: 1,
    ts: "2026-11-17T12:00:00+00:00",
    author: "user",
    revision: 1,
    kind: "comment",
    text: "Why here?",
    attention: true,
    content_version: id,
  });
  const anchors = {
    whole: { section: "plot" },
    "on-p": { section: "plot", visual: "point:p" },
    "on-q": { section: "plot", visual: "point:q" },
  };
  applicationState.adopt(
    servedState({
      browser: {
        views: {
          1: {
            thread: {
              threads: Object.entries(anchors).map(([id, anchor]) =>
                servedThread([comment(id)], { anchor }),
              ),
            },
          },
        },
      },
    }),
  );
  const elements = { whole: plot, "on-p": part("p"), "on-q": part("q") };
  /** @type {string | null} */
  let standsOn = null;
  let reads = 0;
  plot.lfParts = {
    read: () => {
      reads += 1;
      return [];
    },
    at: (node) =>
      node === plot && standsOn
        ? { id: standsOn, element: part("p"), label: "a point" }
        : null,
  };
  const inventory = createAnnotationInventory({
    readObligations: () => ({ user: [] }),
    placedAt: (/** @type {keyof typeof elements} */ id) => ({
      ...resolvedElement({ element: elements[id], place: plot }),
      point: null,
    }),
    openThread() {},
    goToObligation() {},
    scrollToElement() {},
  });
  try {
    assert.deepEqual(inventory.threadIdsAt(plot), ["whole"]);
    standsOn = "point:p";
    assert.deepEqual(inventory.threadIdsAt(plot), ["on-p"]);
    reads = 0;
    assert.deepEqual(inventory.threadIdsAt(part("inside-q")), ["on-q"]);
    assert.equal(reads, 0, "no reading of the picture's parts");
  } finally {
    document.body.replaceChildren();
  }
});

// A picture, `plot`, that draws a dot `p` and a group `q` whose shape `q-shape` is the
// surface it paints on, and names a datum `gone` it hasn't drawn, as a chart names a
// datum a narrower drawing leaves out; and a list beside it. It finds each part by its
// id, as a chart finds its points.
function partsPage() {
  registry["lf-plot"] = { visual: { prefixes: ["point:"] } };
  document.body.innerHTML =
    '<main><lf-plot id="plot" aria-label="Revenue"><svg><circle id="p"></circle>' +
    '<g id="q"><rect id="q-shape"></rect><text>Q</text></g></svg></lf-plot>' +
    '<ul id="list"><li>One</li><li id="two">Two</li></ul></main>';
  const element = (/** @type {string} */ id) =>
    /** @type {Element} */ (document.getElementById(id));
  /** @type {Record<string, string>} */
  const names = {
    "point:p": "x 1, y 2",
    "point:q": "x 3, y 4",
    "point:gone": "x 5, y 6",
  };
  /** @type {Record<string, {element: Element, surface?: Element}>} */
  const drawn = {
    "point:p": { element: element("p") },
    "point:q": { element: element("q"), surface: element("q-shape") },
  };
  element("plot").lfParts = {
    read: () => [],
    find: (id) => (drawn[id] ? { id, ...drawn[id], label: names[id] } : null),
    label: (id) => names[id] ?? null,
  };
  return { element };
}

const commentOn = (/** @type {string} */ id) => ({
  id,
  seq: 1,
  ts: "2026-11-18T12:00:00+00:00",
  author: "user",
  revision: 1,
  kind: "comment",
  text: "Why here?",
  attention: true,
  content_version: id,
});
// Where a thread's anchor resolves now, as anchor placement places it.
/** @param {import("../../browser/types/domain.js").Anchor} anchor */
const placed = (anchor) => ({
  ...resolveAnchor(anchor),
  point: null,
  pointRow: null,
  pointWords: null,
});

// Threads on two parts of one picture are about different things, so each part stands a
// margin entry of its own, named by the label its visual registers, as the comment box
// names it, and pointing at the entry marks the part (`entryPart`) on the surface its
// anchor resolved to, not the picture. A part the picture draws none of yet keeps its
// entry and name, and marks the picture. A pointed row also stands apart, but its
// comment is about its whole target, so it marks none of the target's rows.
test("each part of a picture threads are about stands its own entry, named and marked by the part", () => {
  applicationState.identify(1);
  const { element } = partsPage();
  const anchors = {
    whole: { section: "plot" },
    "on-p": { section: "plot", visual: "point:p" },
    "on-q": { section: "plot", visual: "point:q" },
    "on-gone": { section: "plot", visual: "point:gone" },
    pointed: { section: "list" },
  };
  applicationState.adopt(
    servedState({
      browser: {
        views: {
          1: {
            thread: {
              threads: Object.entries(anchors).map(([id, anchor]) =>
                servedThread([commentOn(id)], { anchor }),
              ),
            },
          },
        },
      },
    }),
  );
  const inventory = createAnnotationInventory({
    readObligations: () => ({ all: [], user: [] }),
    placedAt: (/** @type {keyof typeof anchors} */ id) =>
      id === "pointed"
        ? {
            ...resolvedElement({ element: element("list") }),
            point: element("two"),
            pointRow: "pointed",
            pointWords: "Two",
          }
        : placed(anchors[id]),
    openThread() {},
    goToObligation() {},
    scrollToElement() {},
  });
  try {
    const entries = inventory.collect();
    const about = (/** @type {string} */ id) =>
      entries.find((entry) => entry.items.some((item) => item.thread?.id === id));
    const [whole, onP, onQ, onGone, pointed] = Object.keys(anchors).map(about);
    assert.equal(new Set([whole, onP, onQ, onGone]).size, 4, "an entry for each");
    assert.equal(onP.title, `${whole.title} · x 1, y 2`);
    assert.equal(onQ.title, `${whole.title} · x 3, y 4`);
    assert.equal(onGone.title, `${whole.title} · x 5, y 6`);
    assert.deepEqual(inventory.entryPart(onP), {
      element: element("p"),
      surface: element("p"),
    });
    assert.deepEqual(inventory.entryPart(onQ), {
      element: element("q"),
      surface: element("q-shape"),
    });
    assert.equal(inventory.entryPlace(onQ), element("q"), "it stands by its part");
    assert.equal(inventory.entryPart(onGone), null);
    assert.equal(inventory.entryPart(whole), null);
    assert.equal(inventory.entryPoint(pointed), element("two"));
    assert.equal(inventory.entryPart(pointed), null);
  } finally {
    delete registry["lf-plot"];
    document.body.replaceChildren();
  }
});

// A comment the user saved on a part, which anchor placement places as it places a
// thread (`savedAt`), stands its own entry too, named and marked by the part.
test("a saved draft on a part stands its own entry, named and marked by the part", () => {
  applicationState.identify(1);
  applicationState.adopt(servedState());
  const { element } = partsPage();
  const context = commentContext("on-q");
  const anchor = { section: "plot", visual: "point:q" };
  saveDraft(context, "Why here?", { anchor });
  const inventory = createAnnotationInventory({
    readObligations: () => ({ all: [], user: [] }),
    placedAt: () => null,
    savedAt: (/** @type {string} */ saved) =>
      saved === context ? placed(anchor) : null,
    openThread() {},
    goToObligation() {},
    scrollToElement() {},
  });
  try {
    const [entry] = inventory.collect();
    assert.match(entry.title, / · x 3, y 4$/);
    assert.deepEqual(inventory.entryPart(entry), {
      element: element("q"),
      surface: element("q-shape"),
    });
  } finally {
    clearDraft(context);
    delete registry["lf-plot"];
    document.body.replaceChildren();
  }
});
