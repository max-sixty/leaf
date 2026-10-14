/* A `LeafElement` draws again for what its render read, and for nothing else.

   These drive elements the registry does not declare as widgets, so each owns a region
   of its own; a declared widget's controller path, its startup gate and its gesture
   holds, are the browser suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { html, LeafElement } from "/runtime/widget-api.js";
import {
  applicationState,
  readApplicationPresentation,
  readPart,
} from "/runtime/semantic-state.js";
import { clockValue, tickClock } from "/runtime/presence.js";
import { dragging } from "/runtime/widget-elements.js";
import { adoptRegistry } from "/runtime/registry.js";
import { acceptData, notifyDataSubscribers } from "/runtime/data.js";

const phase = readPart((root) => root.phase);
const host = readPart((root) => root.hostAvailable);
let tags = 0;

// A fresh element class whose render records each draw and returns what it shows.
function probe(render) {
  const draws = [];
  const tag = `lf-probe-${++tags}`;
  customElements.define(
    tag,
    class extends LeafElement {
      render() {
        const shown = render.call(this);
        draws.push(shown);
        return html`${String(shown)}`;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = tag;
  return { element, draws };
}

// Whatever the element owes has drawn: its microtask update, after the arrival batch.
const settled = async (element) => {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await element.updateComplete;
};

// Whether the element's own region still waits on a draw.
const pending = (element) =>
  readApplicationPresentation().pending.some((region) =>
    region.startsWith(`element:${element.localName}#`),
  );

const tick = () =>
  tickClock((reason) => {
    throw reason;
  });

test("an element draws again when a part its render read moves, and not for another", async () => {
  applicationState.setPhase("waiting");
  const { element, draws } = probe(() => phase());
  document.body.append(element);
  await settled(element);
  assert.deepEqual(draws, ["waiting"]);
  assert.equal(element.textContent, "waiting");
  applicationState.setPhase("offline");
  await settled(element);
  assert.deepEqual(draws, ["waiting", "offline"]);
  applicationState.setHostAvailable(!host());
  await settled(element);
  assert.deepEqual(draws, ["waiting", "offline"]);
  element.remove();
});

test("an element draws again when a time it shows ages", async () => {
  let now = 0;
  const { element, draws } = probe(() => clockValue(() => now));
  document.body.append(element);
  await settled(element);
  now = 1;
  await tick();
  await settled(element);
  assert.deepEqual(draws, [0, 1]);
  element.remove();
});

test("an element away draws on its return only what moved meanwhile", async () => {
  applicationState.setPhase("waiting");
  const { element, draws } = probe(() => phase());
  document.body.append(element);
  await settled(element);
  element.remove();
  await settled(element);
  document.body.append(element);
  await settled(element);
  assert.deepEqual(draws, ["waiting"], "nothing it read moved while it was away");
  element.remove();
  await settled(element);
  applicationState.setPhase("offline");
  await settled(element);
  assert.deepEqual(draws, ["waiting"], "it does not draw while away");
  document.body.append(element);
  await settled(element);
  assert.deepEqual(draws, ["waiting", "offline"]);
  element.remove();
});

test("a drag holds an element's draws until the last hand is down", async () => {
  applicationState.setPhase("waiting");
  const { element, draws } = probe(() => phase());
  document.body.append(element);
  await settled(element);
  const hand = document.createElement("div");
  dragging(hand, true);
  applicationState.setPhase("offline");
  await settled(element);
  assert.deepEqual(draws, ["waiting"]);
  dragging(hand, false);
  await settled(element);
  assert.deepEqual(draws, ["waiting", "offline"]);
  element.remove();
});

test("a render that throws shows its failure and draws again for the next move", async () => {
  applicationState.setPhase("waiting");
  const errors = [];
  const report = (event) => errors.push(event.error ?? event.reason);
  window.addEventListener("error", report);
  const { element, draws } = probe(function () {
    const now = phase();
    if (now === "offline") throw new Error("cannot draw offline");
    return now;
  });
  document.body.append(element);
  await settled(element);
  applicationState.setPhase("offline");
  await settled(element);
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.match(element.textContent, /failed: cannot draw offline/);
  applicationState.setPhase("waiting");
  await settled(element);
  assert.deepEqual(draws, ["waiting", "waiting"]);
  assert.equal(element.textContent, "waiting");
  window.removeEventListener("error", report);
  element.remove();
});

test("an element that reads its bound data draws each accepted reading", async () => {
  const tag = `lf-probe-data-${++tags}`;
  adoptRegistry({
    [tag]: { "x-data": { rows: { source: "source", contract: "rows" } } },
    $data: { contracts: { rows: { records: { items: "", key: "key" } } } },
  });
  const accept = (version, revision) =>
    acceptData(
      {
        version,
        sources: {
          deployments: { contract: "rows", revision, value: [{ key: "api" }] },
        },
      },
      1,
    );
  accept("first", "r1");
  const revisions = [];
  customElements.define(
    tag,
    class extends LeafElement {
      render() {
        const reading = this.data("rows");
        revisions.push(reading?.revision ?? null);
        return html`${reading?.origin.source}`;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = "deployments";
  element.setAttribute("source", "deployments");
  document.body.append(element);
  await settled(element);
  accept("second", "r2");
  await notifyDataSubscribers();
  assert.deepEqual(revisions, ["r1", "r2"]);
  assert.equal(element.textContent, "deployments");
  assert.equal(document.body.getAttribute("data-lf-data-version"), "second");
  // A held reading holds the page's data version until it draws.
  const hand = document.createElement("div");
  dragging(hand, true);
  accept("third", "r3");
  const delivered = notifyDataSubscribers();
  await settled(element);
  assert.equal(document.body.getAttribute("data-lf-data-version"), "second");
  dragging(hand, false);
  await delivered;
  assert.deepEqual(revisions, ["r1", "r2", "r3"]);
  assert.equal(document.body.getAttribute("data-lf-data-version"), "third");
  element.remove();
});

test("a claim a drag held settles once the release draws it", async () => {
  applicationState.setPhase("waiting");
  const { element, draws } = probe(() => phase());
  document.body.append(element);
  await settled(element);
  applicationState.setPhase("offline");
  const hand = document.createElement("div");
  dragging(hand, true);
  applicationState.setPhase("waiting");
  await settled(element);
  assert.ok(pending(element), "the held reading leaves its region waiting");
  dragging(hand, false);
  await settled(element);
  assert.deepEqual(draws, ["waiting", "waiting"]);
  assert.ok(!pending(element));
  element.remove();
});

test("an element taken away as its reading moves draws it on its return", async () => {
  applicationState.setPhase("waiting");
  const { element, draws } = probe(() => phase());
  document.body.append(element);
  await settled(element);
  element.remove();
  applicationState.setPhase("offline");
  await settled(element);
  assert.deepEqual(draws, ["waiting"]);
  document.body.append(element);
  await settled(element);
  assert.deepEqual(draws, ["waiting", "offline"]);
  element.remove();
});

test("a failure in a part the element generated stays in that part, and the next draw replaces it", async () => {
  applicationState.setPhase("waiting");
  let failing = false;
  const tag = `lf-probe-part-${++tags}`;
  customElements.define(
    tag,
    class extends LeafElement {
      setup() {
        this.part = document.createElement("p");
        this.append(document.createElement("strong"), this.part);
      }
      createRenderRoot() {
        return this.part;
      }
      render() {
        const now = phase();
        if (failing) throw new Error("cannot draw");
        return html`${now}`;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = tag;
  document.body.append(element);
  await settled(element);
  failing = true;
  element.requestUpdate();
  await settled(element);
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.ok(element.part.isConnected, "the failure keeps the element's own part");
  assert.match(element.part.textContent, /failed: cannot draw/);
  assert.ok(element.querySelector("strong"), "the authored children stay");
  failing = false;
  applicationState.setPhase("offline");
  await settled(element);
  assert.equal(element.part.textContent, "offline");
  element.remove();
});

test("bound data draws only as it is delivered, and a held element holds the version", async () => {
  const tag = `lf-probe-delivered-${++tags}`;
  adoptRegistry({
    [tag]: { "x-data": { rows: { source: "source", contract: "rows" } } },
    $data: { contracts: { rows: { records: { items: "", key: "key" } } } },
  });
  const accept = (version, revision) =>
    acceptData(
      {
        version,
        sources: { builds: { contract: "rows", revision, value: [{ key: "api" }] } },
      },
      1,
    );
  accept("d1", "b1");
  await notifyDataSubscribers();
  const revisions = [];
  customElements.define(
    tag,
    class extends LeafElement {
      render() {
        revisions.push(this.data("rows")?.revision ?? null);
        return html`drawn`;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = "builds";
  element.setAttribute("source", "builds");
  const hand = document.createElement("div");
  dragging(hand, true);
  document.body.append(element);
  accept("d2", "b2");
  const delivered = notifyDataSubscribers();
  await settled(element);
  assert.deepEqual(revisions, [], "a drag holds even the first draw");
  assert.notEqual(document.body.getAttribute("data-lf-data-version"), "d2");
  dragging(hand, false);
  await delivered;
  assert.deepEqual(revisions, ["b2"]);
  assert.equal(document.body.getAttribute("data-lf-data-version"), "d2");
  accept("d3", "b3");
  await settled(element);
  assert.deepEqual(revisions, ["b2"], "accepted is not yet delivered");
  await notifyDataSubscribers();
  assert.deepEqual(revisions, ["b2", "b3"]);
  element.remove();
});
