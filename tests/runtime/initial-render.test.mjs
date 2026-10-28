/* Initial package drawing adopts one node tree and preserves the authored source
   that semantic intake and revision comparison read before behavior modules start. */
import assert from "node:assert/strict";
import test from "node:test";
import { render, nothing, html, LeafElement } from "/runtime/widget-api.js";
import { authoredBody, initialRender, initialOrigin } from "/runtime/initial-render.js";
import { unmarkedCopy } from "/runtime/initial-render.js";
import { tabStore } from "/runtime/storage.js";
import { adoptRegistry } from "/runtime/registry.js";
import {
  rememberAuthoredParents,
  stageAuthoredStates,
} from "/runtime/projection/authored.js";
import {
  stageWidgetDescriptors,
  commitWidgetDescriptors,
  widgetDescriptor,
} from "/runtime/widget-descriptors.js";

test("initial drawing and module adoption share nodes and restored tab values", () => {
  document.body.innerHTML =
    '<main><lf-early id="saved"><span>Original</span></lf-early></main>';
  const host = document.querySelector("lf-early");
  tabStore.set("initial-test", "restored");
  let calls = 0;
  document.documentElement.lfInitial.register("lf-early", (node, context) => {
    calls++;
    const control = context.offer("input", "early-input", undefined, "text");
    control.value = context.tabStore.get("initial-test");
    node.append(control);
    return { control, render: () => control };
  });
  const early = document.documentElement.lfInitial.paint(host);
  const adopted = initialRender(host);
  assert.equal(calls, 1);
  assert.equal(adopted.control, early.control);
  assert.equal(adopted.control.value, "restored");
  assert.equal(adopted.control.dataset.lfOffer, "");
  assert.equal(
    unmarkedCopy(host).outerHTML,
    '<lf-early id="saved"><span>Original</span></lf-early>',
  );
  tabStore.set("initial-test", null);
});

test("nested initial drawings retain authored member order, node routes and semantic inputs", () => {
  document.body.innerHTML =
    '<main><lf-outer id="outer" status="idle"><lf-left id="left"><lf-inner id="inner">Authored</lf-inner></lf-left><lf-right id="right"></lf-right></lf-outer><script data-lf-runtime data-lf-initial>ignored</script></main>';
  const outer = document.querySelector("lf-outer");
  const inner = document.querySelector("lf-inner");
  const authored = outer.outerHTML;
  const coordinator = document.documentElement.lfInitial;
  coordinator.register("lf-inner", (host, { offer }) => {
    host.replaceChildren(offer("div", "inner-face", "Drawn"));
    return { host, render: () => nothing };
  });
  coordinator.register("lf-outer", (host) => {
    host.setAttribute("status", "drawing");
    host.querySelector("lf-right").append(inner);
    return { host, render: () => nothing };
  });
  coordinator.paint(inner);
  coordinator.paint(outer);
  const copy = unmarkedCopy(document.querySelector("main"));
  assert.equal(copy.outerHTML, `<main>${authored}</main>`);
  assert.equal(initialOrigin(copy.querySelector("lf-inner")), inner);
  assert.equal(
    unmarkedCopy(inner).outerHTML,
    '<lf-inner id="inner">Authored</lf-inner>',
  );
  adoptRegistry({
    $layer: { generation: "initial-render" },
    "lf-outer": {
      "x-state": {
        set: {
          unit: "widget",
          record: { kind: "value", attr: "status", value: "status" },
        },
      },
    },
    "lf-left": {},
    "lf-right": {},
    "lf-inner": {},
  });
  const states = stageAuthoredStates(document.querySelector("main"), new Map());
  assert.equal(states.get("outer").state.set.value, "idle");
  const descriptors = stageWidgetDescriptors(document.querySelector("main"), {
    kind: "page",
    revision: 1,
  });
  commitWidgetDescriptors(descriptors);
  assert.deepEqual(widgetDescriptor(inner).parent, { id: "left", tag: "lf-left" });
  assert.equal(inner.parentElement.localName, "lf-right");
});

test("a runtime arrival uses the same producer and preserves the frozen source", () => {
  const holder = document.createElement("template");
  holder.innerHTML = '<lf-later id="later"><p>Later source</p></lf-later>';
  const host = holder.content.firstElementChild;
  document.documentElement.lfInitial.register(
    "lf-later",
    (node, { offer, offerElement }) => {
      const control = offer("button", "later-button", "Run");
      offerElement(control, "later-button");
      node.append(control);
      return { control, render: () => control };
    },
  );
  const drawing = initialRender(host);
  assert.equal(drawing.control.type, "button");
  assert.equal(drawing.control.dataset.lfOffer, "button");
  assert.equal(drawing.control.className, "later-button lf-ui lf-ui-face");
  assert.equal(
    unmarkedCopy(host).outerHTML,
    '<lf-later id="later"><p>Later source</p></lf-later>',
  );
});

test("native idioms never become widget descriptors or authored widget ancestors", () => {
  document.body.innerHTML =
    '<main><table id="native"><tbody><tr><td><lf-nested id="nested">Value</lf-nested></td></tr></tbody></table></main>';
  adoptRegistry({
    "lf-nested": {},
    table: { description: "A table idiom.", "x-example": "<table></table>" },
    "lf-nested.selected": {
      description: "A selected widget idiom.",
      "x-example": '<lf-nested class="selected"></lf-nested>',
    },
  });
  const staged = stageWidgetDescriptors(document.querySelector("main"), {
    kind: "page",
    revision: 2,
  });
  assert.deepEqual([...staged.descriptors.keys()], ["nested"]);
  assert.deepEqual(staged.descriptors.get("nested").ancestors, []);
});

test("an arriving source root keeps its declared parent and exhibit fence", () => {
  adoptRegistry({
    $layer: { generation: "initial-arrival" },
    "lf-quoted-parent": { "x-exhibit": true },
    "lf-arrival": {},
  });
  document.body.innerHTML =
    '<main><lf-quoted-parent id="quote"></lf-quoted-parent></main>';
  const parent = document.querySelector("lf-quoted-parent");
  const arriving = document.createElement("lf-arrival");
  arriving.id = "arrival";
  arriving.innerHTML = "<p>Source</p>";
  rememberAuthoredParents(arriving, parent);
  const before = stageWidgetDescriptors(arriving, { kind: "page", revision: 2 });
  assert.deepEqual(before.descriptors.get("arrival").parent, {
    id: "quote",
    tag: "lf-quoted-parent",
  });
  assert.equal(before.descriptors.get("arrival").quoted, true);
  document.documentElement.lfInitial.register("lf-arrival", (node, { offer }) => {
    node.append(offer("button", "arrival-button", "Run"));
    return { node, render: () => nothing };
  });
  initialRender(arriving);
  const after = stageWidgetDescriptors(arriving, { kind: "page", revision: 2 });
  assert.deepEqual(after.descriptors.get("arrival").parent, {
    id: "quote",
    tag: "lf-quoted-parent",
  });
  assert.equal(after.descriptors.get("arrival").quoted, true);
});

test("member state owns each physical slot independently across a hierarchy", () => {
  const root = document.createElement("main");
  root.innerHTML = `<lf-audit-board id="outer">
    <lf-audit-zone id="one"><lf-audit-card id="card" selected phase="idle">
      <lf-audit-board id="inner"><lf-audit-zone id="inner-zone">
        <lf-audit-card id="inner-card" selected phase="idle">Inner</lf-audit-card>
      </lf-audit-zone></lf-audit-board>
    </lf-audit-card></lf-audit-zone><lf-audit-zone id="two"></lf-audit-zone>
  </lf-audit-board>`;
  const declarations = {
    $layer: { generation: "independent-member-records" },
    "lf-audit-board": {
      "x-state": {
        move: { unit: "unit", record: { kind: "position", within: "lf-audit-zone" } },
      },
    },
    "lf-audit-zone": {
      "x-state": {
        choose: { unit: "widget", record: { kind: "attribute", attr: "selected" } },
      },
    },
    "lf-audit-card": {
      "x-state": {
        phase: { unit: "widget", record: { kind: "value", attr: "phase" } },
      },
    },
  };
  adoptRegistry(declarations);
  const states = stageAuthoredStates(root, new Map());
  assert.deepEqual(states.get("outer").state.move.value, { one: ["card"], two: [] });
  assert.deepEqual(states.get("one").state.choose.value, ["card"]);
  assert.deepEqual(states.get("inner-zone").state.choose.value, ["inner-card"]);
});

test("the contents drawing keeps its early parts through upgrade and keyed revisions", async () => {
  await import("../../packages/default/initial/lf-toc.js");
  document.body.innerHTML =
    '<main><h1>Field guide</h1><lf-toc id="contents"></lf-toc>' +
    '<h2 id="first">Take inventory</h2><h3>Save a snapshot</h3></main>';
  const host = document.querySelector("lf-toc");
  const early = document.documentElement.lfInitial.paint(host);
  const disclosure = host.querySelector("details");
  const summary = host.querySelector("summary");
  const links = [...host.querySelectorAll("a")];
  assert.deepEqual(
    links.map((link) => link.getAttribute("href")),
    [null, "#first", null],
  );
  assert.equal(document.querySelector("h3").id, "");
  disclosure.open = true;
  links[1].focus();

  const live = initialRender(host);
  const reading = {
    label: (heading) => heading.textContent,
    chrome: () => false,
    lends: true,
  };
  render(live.render(reading), host, { host });
  const sections = live.sections();
  assert.equal(live, early);
  assert.equal(host.querySelector("details"), disclosure);
  assert.equal(host.querySelector("summary"), summary);
  assert.equal(disclosure.open, true);
  assert.deepEqual(
    sections.map(({ link }) => link),
    links,
  );
  assert.equal(document.activeElement, links[1]);
  assert.equal(links[2].getAttribute("href"), "#lf-contents-section-2");

  const first = document.querySelector("h2");
  const next = document.querySelector("h3");
  first.before(next);
  first.textContent = "Read the inventory";
  render(live.render(reading), host, { host });
  const reordered = live.sections();
  assert.deepEqual(
    reordered.map(({ link }) => link),
    [links[0], links[2], links[1]],
  );
  assert.equal(links[1].textContent, "Read the inventory");
  assert.equal(disclosure.open, true);
  host.remove();
  assert.equal(live.scope(), null);
  document.querySelector("main").append(host);
  assert.equal(live.scope(), document.querySelector("main"));
  render(live.render(reading), host, { host });
  assert.equal(live.sections()[1].link, links[2]);
});

test("generated words say which kind they are, and a producer can't leave it unsaid", () => {
  document.body.innerHTML = '<main><lf-worded id="worded"></lf-worded></main>';
  const host = document.querySelector("lf-worded");
  document.documentElement.lfInitial.register(
    "lf-worded",
    (node, { generatedElement }) => {
      const heading = generatedElement(document.createElement("h2"), { says: true });
      const name = generatedElement(document.createElement("span"), { says: "echo" });
      // An x-says span keeps the attribute it names.
      const declared = document.createElement("span");
      declared.dataset.lfSaid = "label";
      generatedElement(declared, { says: true });
      node.append(heading, name, declared);
      assert.throws(() => generatedElement(document.createElement("p"), {}), TypeError);
      return { heading, name, declared, render: () => nothing };
    },
  );
  const { heading, name, declared } = document.documentElement.lfInitial.paint(host);
  const { generatedElement } = document.documentElement.lfInitial;
  const markers = (node) =>
    ["data-lf-gen", "data-lf-said", "data-lf-echo"].map((a) => node.getAttribute(a));
  assert.deepEqual(markers(heading), ["1", "", null]);
  assert.deepEqual(markers(name), ["1", null, ""]);
  assert.deepEqual(markers(declared), ["1", "label", null]);
  // A later write restates the kind, as one element can wear both over its life.
  generatedElement(name, { says: false });
  assert.deepEqual(markers(name), ["1", null, null]);
});

test("an authored body takes every child its host was written with, source intact", () => {
  document.body.innerHTML =
    '<main><lf-bodied id="bodied"><p>One</p> <p>Two</p></lf-bodied><lf-plain id="plain"></lf-plain></main>';
  const host = document.querySelector("lf-bodied");
  const authored = host.outerHTML;
  const written = [...host.childNodes];
  const coordinator = document.documentElement.lfInitial;
  coordinator.register("lf-bodied", (node, tools) => {
    const body = tools.authoredBody(document.createElement("div"));
    const frame = document.createElement("section");
    frame.append(tools.offer("span", "bodied-label", "Label"), body);
    node.append(frame);
    return { body, render: () => frame };
  });
  coordinator.register("lf-plain", () => ({ render: () => nothing }));
  const { body } = coordinator.paint(host);
  coordinator.paint(document.querySelector("lf-plain"));
  assert.deepEqual([...body.childNodes], written);
  assert.equal(authoredBody(host), body);
  assert.equal(authoredBody(document.querySelector("lf-plain")), null);
  assert.equal(unmarkedCopy(host).outerHTML, authored);
});

test("a parser template becomes the live element's same Lit root without losing native state", async () => {
  const tag = "lf-retained-lifecycle";
  const coordinator = document.documentElement.lfInitial;
  coordinator.register(tag, (host) => ({
    render: (label = "Before upgrade") => html`
      <details open>
        <summary>${label}</summary>
        <input .value=${"Authored value"} />
      </details>
    `,
  }));
  const host = document.createElement(tag);
  document.body.append(host);
  coordinator.paint(host);
  const disclosure = host.querySelector("details");
  const input = host.querySelector("input");
  disclosure.open = false;
  input.value = "Reader's draft";
  disclosure.open = true;
  input.focus();
  input.setSelectionRange(3, 7);
  disclosure.open = false;
  customElements.define(
    tag,
    class extends LeafElement {
      static properties = { label: {} };
      #view;
      setup() {
        this.#view = initialRender(this);
        this.label = "After upgrade";
      }
      render() {
        return this.#view.render(this.label);
      }
    },
  );
  await host.updateComplete;
  assert.equal(host.querySelectorAll("details").length, 1);
  assert.equal(host.querySelector("details"), disclosure);
  assert.equal(disclosure.open, false);
  assert.equal(host.querySelector("input"), input);
  assert.equal(input.value, "Reader's draft");
  assert.equal(input.selectionStart, 3);
  assert.equal(input.selectionEnd, 7);
  assert.equal(host.querySelector("summary").textContent, "After upgrade");
  host.label = "A live update";
  await host.updateComplete;
  assert.equal(host.querySelector("input"), input);
  assert.equal(input.value, "Reader's draft");
  assert.equal(disclosure.open, false);
  host.remove();
});
