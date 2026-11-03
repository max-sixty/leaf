/* Data delivery and projection lifetime rules do not depend on Chrome layout.
   Native editing, syntax rendering, and reports reaching the page log stay in the
   browser journeys; these cases exercise the publisher and its real DOM owners. */
import assert from "node:assert/strict";
import test from "node:test";
import { adoptRegistry } from "/runtime/registry.js";
import { acceptData, notifyDataSubscribers } from "/runtime/data.js";
import { LeafElement, nothing, html } from "/runtime/widget-api.js";

let fixtureSequence = 0;
async function scene() {
  adoptRegistry({
    "lf-feed": {
      "x-data": { rows: { source: "source", contract: "rows", property: "value" } },
    },
    $data: { contracts: { rows: { records: { items: "", key: "key" } } } },
  });
  document.body.innerHTML =
    '<main><lf-feed id="deployments" source="deployments"></lf-feed></main>';
  acceptData(
    {
      version: `initial-${++fixtureSequence}`,
      sources: {
        deployments: {
          contract: "rows",
          revision: "initial-revision",
          value: [{ key: "api", value: "Running" }],
        },
      },
    },
    1,
  );
  await notifyDataSubscribers();
}

// Whatever the element owes has drawn its DOM, without the drawing its own
// `updateComplete` goes on to wait for.
const committed = (element) =>
  Object.getPrototypeOf(LeafElement.prototype).getUpdateComplete.call(element);

// A widget bound to the deployments source, as the scene's <lf-feed> is, drawing each
// delivered value through `draw(value)`; a promise it returns is the draw's drawing,
// which its `updateComplete` waits for.
let feeds = 0;
async function feed(
  draw,
  bind = (element) => element.setAttribute("source", "deployments"),
) {
  const tag = `lf-feed-${++feeds}`;
  adoptRegistry({
    [tag]: {
      "x-data": { rows: { source: "source", contract: "rows", property: "value" } },
    },
    $data: { contracts: { rows: { records: { items: "", key: "key" } } } },
  });
  customElements.define(
    tag,
    class extends LeafElement {
      constructor() {
        super();
        this.value = null;
      }
      render() {
        return nothing;
      }
      updated(changed) {
        super.updated(changed);
        this.work = draw(this.value);
      }
      async getUpdateComplete() {
        const result = await super.getUpdateComplete();
        await this.work;
        return result;
      }
    },
  );
  const element = document.createElement(tag);
  element.id = "deployments";
  bind(element);
  document.querySelector("main").append(element);
  await new Promise((resolve) => setTimeout(resolve, 0));
  await committed(element);
  return element;
}

test("a widget reads its own binding, captured at its first read", async () => {
  await scene();
  const { runtime } = await import("/runtime/context.js");
  const current = [];
  const bound = await feed((value) => current.push(value?.[0].value ?? null));
  bound.remove();
  const absent = [];
  const elsewhere = await feed(
    (value) => absent.push(value),
    (element) => element.setAttribute("source", "constructor"),
  );
  // A live attribute change does not rebind what the element reads.
  elsewhere.setAttribute("source", "deployments");
  const next = structuredClone(runtime.data);
  next.version = "next-version";
  next.sources.deployments.revision = "next-revision";
  acceptData(next, 1);
  await notifyDataSubscribers();
  elsewhere.remove();
  const unbound = [];
  const loose = await feed(
    (value) => unbound.push(value),
    () => {},
  );
  loose.remove();
  assert.deepEqual(current, ["Running"]);
  assert.deepEqual(absent, [null]);
  assert.deepEqual(unbound, [null]);
});

test("a Lit renderer follows conditional clock reads and its owner lifetime", async () => {
  await scene();
  const { clockValue, tickClock } = await import("/runtime/presence.js");
  let clock = 0;
  let calls = 0;
  let trackClock = false;
  customElements.define(
    "leaf-conditional-clock",
    class extends LeafElement {
      render() {
        calls += 1;
        if (trackClock) clockValue(() => clock);
        return html`<span>Clock</span>`;
      }
    },
  );
  const owner = document.createElement("leaf-conditional-clock");
  const settle = async () => {
    await new Promise((resolve) => setTimeout(resolve));
    if (owner.isConnected) await owner.updateComplete;
  };
  const tick = async () => {
    clock += 1;
    await tickClock((reason) => {
      throw reason;
    });
    await settle();
  };
  document.body.append(owner);
  try {
    await settle();
    assert.equal(calls, 1);
    await tick();
    assert.equal(calls, 1, "an unread clock does not repaint");
    trackClock = true;
    owner.requestUpdate();
    owner.performUpdate();
    assert.equal(calls, 2, "a mechanical redraw establishes its current dependencies");
    await tick();
    assert.equal(calls, 3);
    // Native connection callbacks redraw on a move; Lit retains the rendered nodes.
    const content = owner.querySelector("span");
    owner.remove();
    document.body.append(owner);
    await settle();
    assert.equal(calls, 4);
    assert.equal(owner.querySelector("span"), content);
    owner.remove();
    await settle();
    await tick();
    assert.equal(calls, 4, "a disconnected element does not repaint");
    document.body.append(owner);
    await settle();
    assert.equal(calls, 5, "reconnection draws the reading that aged while away");
    trackClock = false;
    owner.requestUpdate();
    owner.performUpdate();
    assert.equal(calls, 6);
    await tick();
    assert.equal(calls, 6, "a conditional read that ends releases its dependency");
  } finally {
    owner.remove();
  }
});

test("a superseded async data render cannot stamp the newer version", async () => {
  await scene();
  const result = await (async () => {
    const { acceptData, notifyDataSubscribers } = await import("/runtime/data.js");
    const { runtime } = await import("/runtime/context.js");
    const taken = 1;
    const releases = new Map();
    const widget = await feed((rows) => {
      const value = rows?.[0]?.value;
      if (!value?.startsWith("Held")) return;
      return new Promise((resolve) => releases.set(value, resolve));
    });
    const waitFor = async (value) => {
      while (!releases.has(value))
        await new Promise((resolve) => setTimeout(resolve, 0));
    };
    const dataAt = (version, value) => ({
      ...structuredClone(runtime.data),
      version,
      sources: {
        ...structuredClone(runtime.data.sources),
        deployments: {
          ...structuredClone(runtime.data.sources.deployments),
          revision: version,
          value: [{ key: "api", value }],
        },
      },
    });
    const before = document.body.getAttribute("data-lf-data-version");
    acceptData(dataAt("older", "Held older"), taken);
    const older = notifyDataSubscribers();
    await waitFor("Held older");
    acceptData(dataAt("newer", "Held newer"), taken);
    const newer = notifyDataSubscribers();
    await waitFor("Held newer");

    releases.get("Held older")();
    await older;
    const afterOlder = document.body.getAttribute("data-lf-data-version");
    releases.get("Held newer")();
    await newer;
    const afterNewer = document.body.getAttribute("data-lf-data-version");
    widget.remove();
    return { before, afterOlder, afterNewer };
  })();
  assert.equal(result.afterOlder, result.before);
  assert.equal(result.afterNewer, "newer");
});

test("an unchanged source waits for its inflight drawing", async () => {
  await scene();
  const { runtime } = await import("/runtime/context.js");
  let release;
  let calls = 0;
  const widget = await feed(() => {
    if (++calls > 1)
      return new Promise((resolve) => {
        release = resolve;
      });
  });
  const initial = document.body.dataset.lfDataVersion;
  const next = structuredClone(runtime.data);
  next.version = "next-version";
  next.sources.deployments.revision = "next-revision";
  acceptData(next, 1);
  const first = notifyDataSubscribers();
  while (!release) await new Promise((resolve) => setTimeout(resolve, 0));
  let complete = false;
  const again = notifyDataSubscribers().then(() => {
    complete = true;
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  const before = { complete, calls, ready: document.body.dataset.lfDataVersion };
  release();
  await Promise.all([first, again]);
  widget.remove();
  assert.deepEqual(before, { complete: false, calls: 2, ready: initial });
  assert.equal(document.body.dataset.lfDataVersion, next.version);
});

test("a return redraws delivered data after interrupted or completed drawing", async () => {
  await scene();
  const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
  const leaveAndReturn = async (widget) => {
    const main = widget.parentNode;
    widget.remove();
    await settle();
    main.append(widget);
    await settle();
    await committed(widget);
  };
  let draws = 0;
  let finish;
  const finished = new Promise((resolve) => (finish = resolve));
  const widget = await feed(() => {
    draws += 1;
    return finished;
  });
  await leaveAndReturn(widget);
  const interrupted = draws;
  finish();
  await finished;
  await settle();
  await leaveAndReturn(widget);
  widget.remove();
  // A newer update that draws at once replaces a drawing still pending.
  let superseding = 0;
  const superseded = await feed(() => {
    superseding += 1;
    if (superseding === 1) return new Promise(() => {});
  });
  superseded.requestUpdate();
  await superseded.updateComplete;
  await leaveAndReturn(superseded);
  superseded.remove();
  assert.deepEqual(
    { interrupted, kept: draws, superseded: superseding },
    { interrupted: 2, kept: 3, superseded: 3 },
  );
});

test("data readiness does not wait for an unrelated widget region", async () => {
  await scene();
  const result = await (async () => {
    const { notifyDataSubscribers } = await import("/runtime/data.js");
    const { attachApplicationPresentation } =
      await import("/runtime/semantic-state.js");
    const unrelated = attachApplicationPresentation("widget:unrelated:render");
    const held = unrelated.present();
    let ready = false;
    const data = notifyDataSubscribers().then(() => {
      ready = true;
    });
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
    const beforeRelease = ready;
    held.resolve();
    await Promise.all([held.ready, data]);
    unrelated.disconnect();
    return beforeRelease;
  })();
  assert.equal(result, true);
});

// Mounted outputs use the same LeafElement reader and presentation region as sources.
let outputScenes = 0;
function outputScene(draw) {
  const suffix = ++outputScenes;
  const producerTag = `lf-output-${suffix}`;
  const consumerTag = `lf-consumer-${suffix}`;
  adoptRegistry({
    [producerTag]: {
      "x-data": { rows: { source: "source", contract: "rows", property: "value" } },
      "x-output": { rows: { contract: "rows" } },
    },
    [consumerTag]: {
      "x-data": {
        rows: { reference: "for", output: "rows", contract: "rows", property: "value" },
      },
      "x-refers": { for: {} },
    },
  });
  customElements.define(
    consumerTag,
    class extends LeafElement {
      render() {
        return nothing;
      }
      updated(changed) {
        super.updated(changed);
        this.work = draw(this, this.value);
      }
      async getUpdateComplete() {
        const result = await super.getUpdateComplete();
        await this.work;
        return result;
      }
    },
  );
  return { producerTag, consumerTag };
}
const settleOutput = async () => new Promise((resolve) => setTimeout(resolve));

test("typed output readers retain authored scope and producer instance identity", async () => {
  const { dataReader } = await import("/runtime/data.js");
  const { publishOutput } = await import("/runtime/widget-output.js");
  const readings = new Map();
  const { producerTag, consumerTag } = outputScene((element, value) => {
    const history = readings.get(element.id) ?? [];
    readings.set(element.id, [...history, value]);
  });
  document.body.innerHTML =
    `<main><${producerTag} id="feed"></${producerTag}><${consumerTag} id="page" for="feed"></${consumerTag}></main>` +
    `<div class="lf-msg-body"><${producerTag} id="feed"></${producerTag}><${consumerTag} id="message" for="feed"></${consumerTag}></div>`;
  const [pageProducer, messageProducer] = document.querySelectorAll(producerTag);
  const pageConsumer = document.querySelector("#page");
  await settleOutput();
  const current = dataReader(pageConsumer, "rows");
  assert.throws(
    () => publishOutput(pageProducer, "undeclared", { rows: [] }),
    /output is not declared/,
  );
  const unnamed = document.createElement(producerTag);
  assert.throws(() => publishOutput(unnamed, "rows", null), /requires a widget id/);
  const pageValue = { rows: ["page"] };
  publishOutput(pageProducer, "rows", pageValue);
  pageValue.rows[0] = "mutated";
  publishOutput(messageProducer, "rows", { rows: ["message"] });
  await settleOutput();
  assert.deepEqual(readings.get("page"), [null, { rows: ["page"] }]);
  assert.deepEqual(readings.get("message").at(-1), { rows: ["message"] });
  assert.deepEqual(current().value, { rows: ["page"] });
  publishOutput(pageProducer, "rows", { rows: ["page"] });
  await settleOutput();
  assert.equal(readings.get("page").length, 2, "same complete value does not repaint");
  readings.get("page").at(-1).rows[0] = "consumer mutation";
  assert.deepEqual(
    current().value,
    { rows: ["page"] },
    "consumer copies are independent",
  );
  const otherProducer = document.createElement(producerTag);
  otherProducer.id = "other";
  document.querySelector("main").append(otherProducer);
  publishOutput(otherProducer, "rows", { rows: ["other"] });
  pageConsumer.setAttribute("for", "other");
  publishOutput(pageProducer, "rows", { rows: ["changed first"] });
  await settleOutput();
  const captured = {
    contract: "rows",
    value: { rows: ["changed first"] },
    origin: { derived: [{ widget: "feed" }] },
  };
  assert.deepEqual(readings.get("page").at(-1), captured.value);
  assert.deepEqual(current(), captured);
  const replacement = document.createElement(producerTag);
  replacement.id = "feed";
  pageProducer.replaceWith(replacement);
  publishOutput(replacement, "rows", { rows: ["replacement"] });
  await settleOutput();
  assert.deepEqual(readings.get("page").at(-1), { rows: ["replacement"] });
  replacement.remove();
  await settleOutput();
  assert.equal(readings.get("page").at(-1), null);
  document.querySelector("main").append(replacement);
  await settleOutput();
  assert.deepEqual(readings.get("page").at(-1), { rows: ["replacement"] });
  publishOutput(replacement, "rows", null);
  await settleOutput();
  assert.equal(readings.get("page").at(-1), null);
  document.body.replaceChildren();
  await settleOutput();
});

test("source readiness includes asynchronous LeafElement output consumers", async () => {
  const { publishOutput } = await import("/runtime/widget-output.js");
  let release;
  let started;
  const begun = new Promise((resolve) => (started = resolve));
  const rendering = new Promise((resolve) => (release = resolve));
  const { producerTag, consumerTag } = outputScene((element, value) => {
    if (value === "next") {
      started();
      return rendering;
    }
  });
  customElements.define(
    producerTag,
    class extends LeafElement {
      render() {
        return nothing;
      }
      updated(changed) {
        super.updated(changed);
        publishOutput(this, "rows", this.value ?? null);
      }
    },
  );
  document.body.innerHTML = `<main><${producerTag} id="feed" source="deployments"></${producerTag}><${consumerTag} id="consumer" for="feed"></${consumerTag}></main>`;
  await settleOutput();
  acceptData(
    {
      version: `outputs-${++fixtureSequence}`,
      sources: { deployments: { contract: "rows", revision: "next", value: "next" } },
    },
    1,
  );
  let presented = false;
  const completed = notifyDataSubscribers().then(() => (presented = true));
  await begun;
  await Promise.resolve();
  assert.equal(presented, false, "derived rendering holds source readiness");
  release();
  await completed;
  assert.equal(presented, true);
  document.body.replaceChildren();
  await settleOutput();
});
