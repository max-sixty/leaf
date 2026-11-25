/* Data delivery and projection lifetime rules do not depend on Chrome layout.
   Native editing, syntax rendering, and reports reaching the page log stay in the
   browser journeys; these cases exercise the publisher and its real DOM owners. */
import assert from "node:assert/strict";
import test from "node:test";
import { adoptRegistry } from "/runtime/state/registry.js";
import { acceptData, notifyDataSubscribers } from "/runtime/host/data.js";
import { nothing, html } from "/vendor/lit.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import "/runtime/host/element-integration.js";

let fixtureSequence = 0;
async function scene() {
  adoptRegistry({
    "lf-feed": {
      inputs: { rows: { source: "source", contract: "rows", property: "value" } },
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
      inputs: { rows: { source: "source", contract: "rows", property: "value" } },
    },
    $data: { contracts: { rows: { records: { items: "", key: "key" } } } },
  });
  customElements.define(
    tag,
    class extends LeafElement {
      static properties = { value: { attribute: false } };
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
  const { runtime } = await import("/runtime/state/context.js");
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
  const { clockValue, tickClock } = await import("/runtime/state/presence.js");
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
    const { acceptData, notifyDataSubscribers } = await import("/runtime/host/data.js");
    const { runtime } = await import("/runtime/state/context.js");
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
  const { runtime } = await import("/runtime/state/context.js");
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
    const { notifyDataSubscribers } = await import("/runtime/host/data.js");
    const { attachApplicationPresentation } =
      await import("/runtime/state/semantic-state.js");
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

// A widget holds an output as a property and says `change`; its readers use the same
// LeafElement reader and presentation region as sources.
let outputScenes = 0;
function outputScene(draw) {
  const suffix = ++outputScenes;
  const producerTag = `lf-output-${suffix}`;
  const consumerTag = `lf-consumer-${suffix}`;
  adoptRegistry({
    [producerTag]: {
      inputs: { rows: { source: "source", contract: "rows", property: "value" } },
      outputs: { rows: { contract: "rows" } },
    },
    [consumerTag]: {
      inputs: {
        rows: { reference: "for", contract: "rows", property: "value" },
      },
    },
  });
  customElements.define(
    consumerTag,
    class extends LeafElement {
      static properties = { value: { attribute: false } };
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
const holdRows = (producer, rows) => {
  producer.rows = rows;
  producer.dispatchEvent(new Event("change"));
};

test("an output's readers follow the element under their bound id, in their own document", async () => {
  const { dataReader } = await import("/runtime/host/data.js");
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
  const pageValue = { rows: ["page"] };
  holdRows(pageProducer, pageValue);
  holdRows(messageProducer, { rows: ["message"] });
  await settleOutput();
  assert.deepEqual(readings.get("page"), [null, { rows: ["page"] }]);
  assert.deepEqual(readings.get("message").at(-1), { rows: ["message"] });
  assert.deepEqual(current().value, { rows: ["page"] });
  const equal = { rows: ["page"] };
  holdRows(pageProducer, equal);
  await settleOutput();
  assert.equal(readings.get("page").length, 2, "an equal value does not repaint");
  readings.get("page").at(-1).rows[0] = "consumer mutation";
  assert.deepEqual(
    current().value,
    { rows: ["page"] },
    "consumer copies are independent",
  );
  // A producer holds a new value to change one: the object it already held reads as
  // unchanged, whatever was done to it.
  equal.rows[0] = "edited in place";
  holdRows(pageProducer, equal);
  await settleOutput();
  assert.equal(readings.get("page").length, 2, "the same object is not read again");
  holdRows(pageProducer, { rows: ["edited"] });
  await settleOutput();
  assert.deepEqual(readings.get("page").at(-1), { rows: ["edited"] });
  // A control inside the producer says `change` for itself, not for the producer.
  const control = pageProducer.appendChild(document.createElement("input"));
  pageProducer.rows = { rows: ["unsaid"] };
  control.dispatchEvent(new Event("change", { bubbles: true }));
  await settleOutput();
  assert.deepEqual(readings.get("page").at(-1), { rows: ["edited"] });
  control.remove();
  // Markup owns the binding, captured at the first read.
  const otherProducer = document.createElement(producerTag);
  otherProducer.id = "other";
  document.querySelector("main").append(otherProducer);
  holdRows(otherProducer, { rows: ["other"] });
  pageConsumer.setAttribute("for", "other");
  holdRows(pageProducer, { rows: ["changed first"] });
  await settleOutput();
  const captured = {
    contract: "rows",
    value: { rows: ["changed first"] },
    origin: { derived: [{ widget: "feed" }] },
  };
  assert.deepEqual(readings.get("page").at(-1), captured.value);
  assert.deepEqual(current(), captured);
  // A replacement under the same id is read as it stands, with no `change` said to
  // the reader: what it holds was set before it arrived.
  const replacement = document.createElement(producerTag);
  replacement.id = "feed";
  replacement.rows = { rows: ["replacement"] };
  pageProducer.replaceWith(replacement);
  await settleOutput();
  assert.deepEqual(readings.get("page").at(-1), { rows: ["replacement"] });
  replacement.remove();
  await settleOutput();
  assert.equal(readings.get("page").at(-1), null);
  document.querySelector("main").append(replacement);
  await settleOutput();
  assert.deepEqual(readings.get("page").at(-1), { rows: ["replacement"] });
  holdRows(replacement, null);
  await settleOutput();
  assert.equal(readings.get("page").at(-1), null);
  // A reader that arrives after its producer last said `change` reads what it holds.
  holdRows(replacement, { rows: ["held"] });
  const late = document.createElement(consumerTag);
  late.id = "late";
  late.setAttribute("for", "feed");
  document.querySelector("main").append(late);
  await settleOutput();
  assert.deepEqual(readings.get("late").at(-1), { rows: ["held"] });
  document.body.replaceChildren();
  await settleOutput();
});

test("a reader that read before its producer's class was defined reads what the class holds", async () => {
  const readings = [];
  const { producerTag, consumerTag } = outputScene((element, value) =>
    readings.push(value),
  );
  document.body.innerHTML = `<main><${producerTag} id="feed"></${producerTag}><${consumerTag} for="feed"></${consumerTag}></main>`;
  await settleOutput();
  assert.deepEqual(readings, [null]);
  // The class holds a value from its construction and says no `change` for it, as a
  // form control says none for its first value.
  customElements.define(
    producerTag,
    class extends HTMLElement {
      rows = { rows: ["held"] };
    },
  );
  await settleOutput();
  assert.deepEqual(readings, [null, { rows: ["held"] }]);
  document.body.replaceChildren();
  await settleOutput();
});

test("a producer arriving or leaving under another name leaves a reader's reading alone", async () => {
  const { producerTag, consumerTag } = outputScene(() => {});
  document.body.innerHTML = `<main><${producerTag} id="feed"></${producerTag}><${consumerTag} for="feed"></${consumerTag}></main>`;
  const main = document.querySelector("main");
  const feed = document.querySelector("#feed");
  let reads = 0;
  Object.defineProperty(feed, "rows", { get: () => (reads++, { rows: ["feed"] }) });
  feed.dispatchEvent(new Event("change"));
  await settleOutput();
  const read = reads;
  assert.ok(read > 0, "the reader reads what its producer holds");
  const other = document.createElement(producerTag);
  other.id = "other";
  main.append(other);
  await settleOutput();
  other.remove();
  await settleOutput();
  assert.equal(reads, read, "another producer's arrival reaches only its own readers");
  // The same move under the reader's own name is read again.
  feed.remove();
  await settleOutput();
  main.prepend(feed);
  await settleOutput();
  assert.ok(reads > read);
  document.body.replaceChildren();
  await settleOutput();
});

test("source readiness includes asynchronous LeafElement output consumers", async () => {
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
      static properties = { value: { attribute: false } };
      render() {
        return nothing;
      }
      updated(changed) {
        super.updated(changed);
        holdRows(this, this.value ?? null);
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
