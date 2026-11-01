/* A `LeafElement` draws again for what its render read, and for nothing else.

   These drive elements the registry does not declare as widgets, so each owns a region
   of its own; a declared widget's controller path, its startup gate and its gesture
   holds, are the browser suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { signal } from "/runtime/framework.js";
import {
  html,
  LeafElement,
  nothing,
  noChange,
  shadowStage,
} from "/runtime/widget-api.js";
import { focused, focusDestination } from "/runtime/focus.js";
import { failSoftUnreported } from "/runtime/widget-upgrade.js";
import {
  applicationState,
  attachApplicationPresentation,
  applicationRegionsPresented,
  readApplicationPresentation,
  readPart,
  queueWidgetUpdate,
  applicationPresenter,
  PRESENTATION_DOM,
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

// Whatever the element owes has drawn its DOM, without the drawing its own
// `updateComplete` goes on to wait for.
const committed = async (element) => {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await Object.getPrototypeOf(LeafElement.prototype).getUpdateComplete.call(element);
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

test("reactive properties claim presentation only when Lit schedules an update", async () => {
  const tag = `lf-probe-property-${++tags}`;
  customElements.define(
    tag,
    class extends LeafElement {
      static properties = {
        name: {
          hasChanged: (value, old) => value?.toLowerCase() !== old?.toLowerCase(),
        },
      };
      constructor() {
        super();
        this.name = "same";
      }
      render() {
        return html`${this.name}`;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = tag;
  document.body.append(element);
  try {
    await settled(element);
    for (const unchanged of ["same", "SAME"]) {
      element.name = unchanged;
      assert.equal(element.isUpdatePending, false);
      assert.ok(!pending(element), "a rejected property change owes no presentation");
    }
    element.name = "different";
    assert.ok(pending(element), "an accepted change claims before its setter returns");
    await settled(element);
    assert.equal(element.textContent, "different");
    assert.ok(!pending(element));
  } finally {
    element.remove();
  }
});

test("requests consumed by the active render leave no extra presentation claim", async () => {
  const tag = `lf-probe-active-update-${++tags}`;
  customElements.define(
    tag,
    class extends LeafElement {
      static properties = { name: {}, derived: {} };
      constructor() {
        super();
        this.name = "first";
      }
      render() {
        this.derived = this.name.toUpperCase();
        this.requestUpdate();
        return html`${this.derived}`;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = tag;
  document.body.append(element);
  try {
    await settled(element);
    element.name = "second";
    await settled(element);
    assert.equal(element.textContent, "SECOND");
    assert.equal(element.isUpdatePending, false);
    assert.ok(!pending(element), "the active render fulfills its coalesced requests");
  } finally {
    element.remove();
  }
});

test("an updated callback's follow-up keeps presentation pending through its drawing", async () => {
  let finish;
  const tag = `lf-probe-follow-up-${++tags}`;
  customElements.define(
    tag,
    class extends LeafElement {
      static properties = { name: {} };
      constructor() {
        super();
        this.name = "first";
      }
      render() {
        return html`${this.name}`;
      }
      updated(changed) {
        super.updated(changed);
        if (this.name === "second") this.name = "final";
        else if (this.name === "final")
          this.work = new Promise((done) => (finish = done));
      }
      async getUpdateComplete() {
        const result = await super.getUpdateComplete();
        await this.work;
        return result;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = tag;
  document.body.append(element);
  try {
    await settled(element);
    element.name = "second";
    await committed(element);
    assert.equal(element.textContent, "final");
    assert.ok(pending(element), "the follow-up's drawing still holds presentation");
    finish();
    await settled(element);
    assert.ok(!pending(element));
  } finally {
    element.remove();
  }
});

test("mechanical focus reads do not subscribe a widget's content to focus moves", async () => {
  const { element, draws } = probe(() => {
    focused();
    return phase();
  });
  const button = document.createElement("button");
  document.body.append(element, button);
  await settled(element);
  focusDestination(button, "move");
  await settled(element);
  assert.equal(draws.length, 1);
  element.remove();
  button.remove();
});

test("readiness finishes a waiting render without claiming another presentation", async () => {
  const region = "probe:ready";
  const prerequisite = attachApplicationPresentation(region, {});
  let claim = prerequisite.present("first");
  let draws = 0;
  const tag = `lf-probe-ready-${++tags}`;
  customElements.define(
    tag,
    class extends LeafElement {
      render() {
        draws++;
        if (!this.whenReady(() => applicationRegionsPresented([region])))
          return noChange;
        return html`ready`;
      }
    },
  );
  const element = document.createElement(tag);
  document.body.append(element);
  await settled(element);
  assert.equal(element.textContent, "");
  claim.resolve();
  assert.equal(
    pending(element),
    false,
    "completion does not reopen this widget's claim",
  );
  await settled(element);
  assert.equal(element.textContent, "ready");
  assert.equal(draws, 2);
  claim = prerequisite.present("second");
  await settled(element);
  claim.resolve();
  await settled(element);
  assert.equal(draws, 2, "finished readiness has no subscription to falling proof");
  element.remove();
  prerequisite.disconnect();
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

test("an element reconnects its dependencies without replacing unchanged content", async () => {
  applicationState.setPhase("waiting");
  const { element, draws } = probe(() => phase());
  document.body.append(element);
  await settled(element);
  const content = element.firstChild;
  element.remove();
  await settled(element);
  document.body.append(element);
  await settled(element);
  assert.deepEqual(draws, ["waiting", "waiting"]);
  assert.equal(element.firstChild, content, "Lit keeps unchanged nodes on return");
  element.remove();
  await settled(element);
  applicationState.setPhase("offline");
  await settled(element);
  assert.deepEqual(draws, ["waiting", "waiting"], "it does not draw while away");
  document.body.append(element);
  await settled(element);
  assert.deepEqual(draws, ["waiting", "waiting", "offline"]);
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
  const unrelated = probe(() => phase());
  document.body.append(element, unrelated.element);
  await settled(element);
  await settled(unrelated.element);
  applicationState.setPhase("offline");
  await settled(element);
  await settled(unrelated.element);
  assert.equal(
    unrelated.element.textContent,
    "offline",
    "a failing owner leaves other signal views functional",
  );
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.match(element.textContent, /failed: cannot draw offline/);
  applicationState.setPhase("waiting");
  await settled(element);
  assert.deepEqual(draws, ["waiting", "waiting"]);
  assert.equal(element.textContent, "waiting");
  window.removeEventListener("error", report);
  element.remove();
  unrelated.element.remove();
});

test("an element gates its draws on the delivered bound value", async () => {
  const tag = `lf-probe-data-${++tags}`;
  adoptRegistry({
    [tag]: {
      "x-data": { rows: { source: "source", contract: "rows", property: "value" } },
    },
    $data: { contracts: { rows: { records: { items: "", key: "key" } } } },
  });
  const accept = (version, revision) =>
    acceptData(
      {
        version,
        sources: {
          deployments: {
            contract: "rows",
            revision,
            value: [{ key: "api", revision }],
          },
        },
      },
      1,
    );
  accept("first", "r1");
  const revisions = [];
  customElements.define(
    tag,
    class extends LeafElement {
      shouldUpdate(changed) {
        return super.shouldUpdate(changed) && this.value !== this.drawn;
      }
      render() {
        this.drawn = this.value;
        revisions.push(this.value?.[0].revision ?? null);
        return html`${this.value?.[0].key}`;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = "deployments";
  element.setAttribute("source", "deployments");
  document.body.append(element);
  await settled(element);
  element.requestUpdate();
  await settled(element);
  assert.deepEqual(revisions, ["r1"], "an unchanged value skips the draw");
  accept("second", "r2");
  await notifyDataSubscribers();
  assert.deepEqual(revisions, ["r1", "r2"]);
  assert.equal(element.textContent, "api");
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

test("a setup that throws shows its failure and the element draws nothing, a check's redraw included", async () => {
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
  element.redraw();
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
        shadowStage(this, [document.createElement("p")]);
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
    [tag]: {
      "x-data": { rows: { source: "source", contract: "rows", property: "value" } },
    },
    $data: { contracts: { rows: { records: { items: "", key: "key" } } } },
  });
  const accept = (version, revision) =>
    acceptData(
      {
        version,
        sources: {
          builds: { contract: "rows", revision, value: [{ key: "api", revision }] },
        },
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
        revisions.push(this.value?.[0].revision ?? null);
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

test("a data widget the markup binds to nothing reads its written <pre> as its input", async () => {
  const tag = `lf-probe-written-${++tags}`;
  adoptRegistry({
    [tag]: {
      "x-content": "data",
      "x-data": { text: { source: "source", contract: "text", property: "value" } },
    },
  });
  const drawn = [];
  customElements.define(
    tag,
    class extends LeafElement {
      render() {
        drawn.push(this.value);
        return nothing;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = "written";
  element.innerHTML = "<pre>**Fixed** &lt;now&gt;\n</pre>";
  document.body.append(element);
  await settled(element);
  assert.deepEqual(drawn, ["**Fixed** <now>\n"]);
  element.remove();
  // A module that makes one without a `<pre>` hosts the input itself.
  const hosted = document.createElement(tag);
  hosted.id = "hosted";
  hosted.value = "set by its host";
  document.body.append(hosted);
  await settled(hosted);
  assert.deepEqual(drawn.at(-1), "set by its host");
  hosted.remove();
});

test("a move published just before the element leaves is drawn on its return", async () => {
  applicationState.setPhase("waiting");
  const { element, draws } = probe(() => phase());
  document.body.append(element);
  await settled(element);
  applicationState.setPhase("offline");
  element.remove();
  await settled(element);
  assert.deepEqual(draws, ["waiting"], "nothing draws into a detached element");
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
        this.work =
          phase() === "offline" ? new Promise((done) => (finish = done)) : undefined;
      }
      async getUpdateComplete() {
        const result = await super.getUpdateComplete();
        await this.work;
        return result;
      }
    },
  );
  applicationState.setPhase("waiting");
  const element = document.createElement(tag);
  element.id = tag;
  document.body.append(element);
  await settled(element);
  applicationState.setPhase("offline");
  await committed(element);
  assert.ok(pending(element), "the claim waits for the drawing");
  finish();
  await settled(element);
  assert.ok(!pending(element));
  // An update the element asks for itself, as a retry is, claims the region too.
  element.requestUpdate();
  await committed(element);
  assert.ok(pending(element), "the requested update's drawing holds the region");
  finish();
  await settled(element);
  assert.ok(!pending(element));
  element.remove();
});

test("the first drawing after a skipped update holds presentation until it finishes", async () => {
  const value = signal(false);
  let finish;
  const tag = `lf-probe-signal-drawing-${++tags}`;
  customElements.define(
    tag,
    class extends LeafElement {
      shouldUpdate(changed) {
        return super.shouldUpdate(changed) && value.value;
      }
      render() {
        return html`${value.value}`;
      }
      updated(changed) {
        super.updated(changed);
        this.work = value.peek() ? new Promise((done) => (finish = done)) : undefined;
      }
      async getUpdateComplete() {
        const result = await super.getUpdateComplete();
        await this.work;
        return result;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = tag;
  document.body.append(element);
  try {
    await settled(element);
    value.value = true;
    await committed(element);
    assert.ok(pending(element), "the signal's drawing holds the region");
    finish();
    await settled(element);
    assert.ok(!pending(element));
  } finally {
    finish?.();
    element.remove();
  }
});

test("accepted data claims the element's region until its delivery draws", async () => {
  const tag = `lf-probe-claim-${++tags}`;
  adoptRegistry({
    [tag]: {
      "x-data": { rows: { source: "source", contract: "rows", property: "value" } },
    },
    $data: { contracts: { rows: { records: { items: "", key: "key" } } } },
  });
  const accept = (version, revision) =>
    acceptData(
      {
        version,
        sources: {
          jobs: { contract: "rows", revision, value: [{ key: "api", revision }] },
        },
      },
      1,
    );
  accept("j1", "r1");
  await notifyDataSubscribers();
  customElements.define(
    tag,
    class extends LeafElement {
      render() {
        return html`${this.value?.[0].revision}`;
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

test(
  "a source no longer drawn cannot hold later data delivery",
  { timeout: 2000 },
  async () => {
    const tag = `lf-probe-unused-data-${++tags}`;
    adoptRegistry({
      [tag]: {
        "x-data": { rows: { source: "source", contract: "rows", property: "value" } },
      },
      $data: { contracts: { rows: { records: { items: "", key: "key" } } } },
    });
    const accept = (version, revision) =>
      acceptData(
        {
          version,
          sources: {
            jobs: { contract: "rows", revision, value: [{ key: "api", revision }] },
          },
        },
        1,
      );
    accept("unused-d1", "r1");
    await notifyDataSubscribers();
    customElements.define(
      tag,
      class extends LeafElement {
        showData = true;
        render() {
          return html`${this.showData ? this.value?.[0].revision : "Hidden"}`;
        }
      },
    );
    const element = document.createElement(tag);
    element.id = "unused-data";
    element.setAttribute("source", "jobs");
    document.body.append(element);
    try {
      await settled(element);
      assert.equal(element.textContent, "r1");
      element.showData = false;
      element.requestUpdate();
      await settled(element);
      assert.equal(element.textContent, "Hidden");
      accept("unused-d2", "r2");
      await notifyDataSubscribers();
      assert.ok(!pending(element), "unused input leaves no presentation claim");
      assert.equal(element.textContent, "Hidden");
      assert.equal(document.body.getAttribute("data-lf-data-version"), "unused-d2");
    } finally {
      element.remove();
    }
  },
);

test("document consumers wait for native Lit follow-up DOM, not held drawing", async () => {
  const held = Promise.withResolvers();
  const tag = `lf-probe-native-completion-${++tags}`;
  customElements.define(
    tag,
    class extends LeafElement {
      static properties = { value: {} };
      constructor() {
        super();
        this.value = "initial";
      }
      scheduleUpdate() {
        return queueWidgetUpdate(
          this.id,
          () => super.scheduleUpdate(),
          () => super.getUpdateComplete(),
        );
      }
      render() {
        return html`<p>${this.value}</p>`;
      }
      updated(changed) {
        super.updated(changed);
        if (this.value === "intermediate") this.value = "final";
        if (this.value === "final") this.work = held.promise;
      }
      async getUpdateComplete() {
        const result = await super.getUpdateComplete();
        await this.work;
        return result;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = tag;
  document.body.append(element);
  await settled(element);
  const seen = [];
  const consumer = applicationPresenter({
    region: "native-completion-consumer",
    reading: () => true,
    after: PRESENTATION_DOM.widgets,
    paint: () => seen.push(element.textContent),
  });
  element.value = "intermediate";
  const ready = consumer.present();
  await ready;
  assert.deepEqual(seen, ["final"]);
  assert.ok(pending(element), "DOM completion does not certify held semantic drawing");
  held.resolve();
  await settled(element);
  assert.ok(!pending(element));
  consumer.disconnect();
  element.remove();
});
