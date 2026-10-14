/* A `LeafElement` draws again for what its render read, and for nothing else.

   These drive elements the registry does not declare as widgets, so each owns a region
   of its own; a declared widget's controller path, its startup gate and its gesture
   holds, are the browser suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { html, LeafElement, nothing } from "/runtime/widget-api.js";
import { failSoftUnreported } from "/runtime/widget-upgrade.js";
import {
  applicationState,
  readApplicationPresentation,
  readPart,
} from "/runtime/semantic-state.js";
import { clockValue, tickClock } from "/runtime/presence.js";
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

test("a failure keeps the nodes the render paints, and the next draw takes the box away", async () => {
  applicationState.setPhase("waiting");
  let failing = false;
  const tag = `lf-probe-retained-${++tags}`;
  customElements.define(
    tag,
    class extends LeafElement {
      setup() {
        this.shown = this.querySelector("output");
      }
      render() {
        const now = phase();
        if (failing) throw new Error("cannot paint");
        this.shown.value = now;
        return nothing;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = tag;
  element.innerHTML = "<p>Authored words</p><output></output>";
  document.body.append(element);
  await settled(element);
  failing = true;
  element.requestUpdate();
  await settled(element);
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.match(element.querySelector(".lf-error").textContent, /failed: cannot paint/);
  assert.ok(element.shown.isConnected, "the failure keeps the retained node");
  assert.equal(element.querySelector("p").textContent, "Authored words");
  failing = false;
  applicationState.setPhase("offline");
  await settled(element);
  assert.equal(element.shown.value, "offline");
  assert.equal(element.querySelector(".lf-error"), null);
  element.remove();
});

test("a failed preparation stands beside the render root, which the next draw still reaches", async () => {
  applicationState.setPhase("waiting");
  const tag = `lf-probe-prepared-${++tags}`;
  customElements.define(
    tag,
    class extends LeafElement {
      setup() {
        this.part = document.createElement("p");
        this.append(this.part);
      }
      createRenderRoot() {
        return this.part;
      }
      render() {
        return html`${phase()}`;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = tag;
  document.body.append(element);
  await settled(element);
  // The controller shows a rejected `present()` on its owner, as here.
  failSoftUnreported(element, new Error("could not prepare"));
  assert.ok(element.part.isConnected);
  assert.match(element.textContent, /failed: could not prepare/);
  applicationState.setPhase("offline");
  await settled(element);
  assert.equal(element.part.textContent, "offline");
  assert.equal(element.querySelector(".lf-error"), null);
  element.remove();
});

test("a setup that throws shows its failure and the element draws nothing", async () => {
  applicationState.setPhase("waiting");
  const errors = [];
  const original = console.error;
  console.error = (...args) => errors.push(args.join(" "));
  const draws = [];
  const tag = `lf-probe-setup-${++tags}`;
  customElements.define(
    tag,
    class extends LeafElement {
      setup() {
        throw new Error("cannot build");
      }
      render() {
        draws.push(phase());
        return html`drawn`;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = tag;
  document.body.append(element);
  await settled(element);
  applicationState.setPhase("offline");
  await settled(element);
  console.error = original;
  assert.deepEqual(draws, []);
  assert.match(element.textContent, /failed: cannot build/);
  assert.ok(!pending(element), "its region does not wait on a draw that cannot come");
  element.remove();
});

test("a setup that throws inside its own shadow root shows its failure there", async () => {
  const original = console.error;
  console.error = () => {};
  const tag = `lf-probe-shadow-setup-${++tags}`;
  customElements.define(
    tag,
    class extends LeafElement {
      setup() {
        this.attachShadow({ mode: "open" }).append(document.createElement("p"));
        throw new Error("cannot stage");
      }
      render() {
        return html`drawn`;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = tag;
  document.body.append(element);
  await settled(element);
  console.error = original;
  assert.match(element.shadowRoot.textContent, /failed: cannot stage/);
  element.remove();
});

test("bound data draws only as it is delivered", async () => {
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
  document.body.append(element);
  await settled(element);
  assert.deepEqual(revisions, ["b1"]);
  accept("d2", "b2");
  await settled(element);
  assert.deepEqual(revisions, ["b1"], "accepted is not yet delivered");
  await notifyDataSubscribers();
  assert.deepEqual(revisions, ["b1", "b2"]);
  assert.equal(document.body.getAttribute("data-lf-data-version"), "d2");
  element.remove();
});

test("a move draws at once, inside the publication, and a return redraws nothing", async () => {
  applicationState.setPhase("waiting");
  const { element, draws } = probe(() => phase());
  document.body.append(element);
  await settled(element);
  applicationState.setPhase("offline");
  assert.deepEqual(
    draws,
    ["waiting", "offline"],
    "drawn before the publication returns",
  );
  element.remove();
  await settled(element);
  document.body.append(element);
  await settled(element);
  assert.deepEqual(draws, ["waiting", "offline"]);
  element.remove();
});

test("a failure after the draw is reported and shown, not swallowed", async () => {
  const errors = [];
  const original = console.error;
  console.error = (...args) => errors.push(args.join(" "));
  const tag = `lf-probe-updated-${++tags}`;
  customElements.define(
    tag,
    class extends LeafElement {
      render() {
        return html`${phase()}`;
      }
      updated(changed) {
        super.updated(changed);
        if (phase() === "offline") throw new Error("cannot finish");
      }
    },
  );
  applicationState.setPhase("waiting");
  const element = document.createElement(tag);
  element.id = tag;
  document.body.append(element);
  await settled(element);
  applicationState.setPhase("offline");
  await settled(element);
  await new Promise((resolve) => setTimeout(resolve, 0));
  console.error = original;
  assert.match(element.textContent, /failed: cannot finish/);
  element.remove();
});

test("a failure before the render settles the claim with the failure", async () => {
  const errors = [];
  const original = console.error;
  console.error = (...args) => errors.push(args.join(" "));
  const tag = `lf-probe-will-${++tags}`;
  customElements.define(
    tag,
    class extends LeafElement {
      willUpdate() {
        if (phase() === "offline") throw new Error("cannot begin");
      }
      render() {
        return html`${phase()}`;
      }
    },
  );
  applicationState.setPhase("waiting");
  const element = document.createElement(tag);
  element.id = tag;
  document.body.append(element);
  await settled(element);
  applicationState.setPhase("offline");
  await settled(element);
  await new Promise((resolve) => setTimeout(resolve, 0));
  console.error = original;
  assert.match(element.textContent, /failed: cannot begin/);
  assert.ok(!pending(element));
  element.remove();
});

test("a check's redraw leaves the update a move queued, and its claim", async () => {
  applicationState.setPhase("waiting");
  const { element, draws } = probe(() => phase());
  document.body.append(element);
  await settled(element);
  applicationState.setPhase("offline");
  element.redraw();
  await settled(element);
  assert.deepEqual(draws, ["waiting", "offline", "offline"]);
  assert.ok(!pending(element));
  element.remove();
});

test("a draw's claim waits for the drawing it holds it for", async () => {
  let finish;
  const tag = `lf-probe-drawing-${++tags}`;
  customElements.define(
    tag,
    class extends LeafElement {
      render() {
        return html`${phase()}`;
      }
      updated(changed) {
        super.updated(changed);
        if (phase() === "offline") this.drawing(new Promise((done) => (finish = done)));
      }
    },
  );
  applicationState.setPhase("waiting");
  const element = document.createElement(tag);
  element.id = tag;
  document.body.append(element);
  await settled(element);
  applicationState.setPhase("offline");
  await settled(element);
  assert.ok(pending(element), "the claim waits for the drawing");
  finish();
  await settled(element);
  assert.ok(!pending(element));
  element.remove();
});

test("accepted data claims the element's region until its delivery draws", async () => {
  const tag = `lf-probe-claim-${++tags}`;
  adoptRegistry({
    [tag]: { "x-data": { rows: { source: "source", contract: "rows" } } },
    $data: { contracts: { rows: { records: { items: "", key: "key" } } } },
  });
  const accept = (version, revision) =>
    acceptData(
      {
        version,
        sources: { jobs: { contract: "rows", revision, value: [{ key: "api" }] } },
      },
      1,
    );
  accept("j1", "r1");
  await notifyDataSubscribers();
  customElements.define(
    tag,
    class extends LeafElement {
      render() {
        return html`${this.data("rows")?.revision}`;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = "jobs";
  element.setAttribute("source", "jobs");
  document.body.append(element);
  await settled(element);
  accept("j2", "r2");
  await settled(element);
  assert.equal(element.textContent, "r1");
  assert.ok(pending(element), "the accepted reading holds the region open");
  await notifyDataSubscribers();
  assert.equal(element.textContent, "r2");
  assert.ok(!pending(element));
  element.remove();
});
