/* Initial package drawing adopts one node tree and preserves the authored source
   that semantic intake and revision comparison read before behavior modules start. */
import assert from "node:assert/strict";
import test from "node:test";
import { initialRender, initialOrigin } from "/runtime/initial-render.js";
import { tabStore, unmarkedCopy } from "/runtime/storage.js";
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
    return { control };
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
    return { host };
  });
  coordinator.register("lf-outer", (host) => {
    host.setAttribute("status", "drawing");
    host.querySelector("lf-right").append(inner);
    return { host };
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
      return { control };
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
    return { node };
  });
  initialRender(arriving);
  const after = stageWidgetDescriptors(arriving, { kind: "page", revision: 2 });
  assert.deepEqual(after.descriptors.get("arrival").parent, {
    id: "quote",
    tag: "lf-quoted-parent",
  });
  assert.equal(after.descriptors.get("arrival").quoted, true);
});
