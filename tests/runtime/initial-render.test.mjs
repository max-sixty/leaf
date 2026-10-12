/* Initial package drawing adopts one node tree and preserves the authored source
   that semantic intake and revision comparison read before behavior modules start. */
import assert from "node:assert/strict";
import test from "node:test";
import { initialRender, initialOrigin } from "/runtime/initial-render.js";
import { unmarkedCopy } from "/runtime/initial-render.js";
import { tabStore } from "/runtime/storage.js";
import { bindVocabulary } from "/runtime/widget-contexts.js";
import { addressableLabel } from "/runtime/addressable-names.js";
import { adoptRegistry, registry, stateSpecs } from "/runtime/registry.js";
import {
  rememberAuthoredParents,
  stageAuthoredStates,
} from "/runtime/projection/authored.js";
import {
  stageWidgetDescriptors,
  commitWidgetDescriptors,
  widgetDescriptor,
} from "/runtime/widget-descriptors.js";

// Execute producers as delivered classic scripts, including their native script owner.
function registerInitial(tag, render) {
  const script = document.createElement("script");
  script.dataset.lfVocabulary = "1";
  window.initialProducer = render;
  script.textContent = `document.documentElement.lfInitial.register(${JSON.stringify(tag)}, window.initialProducer)`;
  window.happyDOM.settings.enableJavaScriptEvaluation = true;
  try {
    document.head.append(script);
  } finally {
    script.remove();
    delete window.initialProducer;
    window.happyDOM.settings.enableJavaScriptEvaluation = false;
  }
  document.body.dataset.lfVocabulary = "1";
  bindVocabulary(document, { revision: 1, declarations: registry });
}

test("initial drawing and module adoption share nodes and restored tab values", () => {
  document.body.innerHTML =
    '<main><lf-early id="saved"><span>Original</span></lf-early></main>';
  const host = document.querySelector("lf-early");
  tabStore.set("initial-test", "restored");
  let calls = 0;
  registerInitial("lf-early", (node, context) => {
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
  registerInitial("lf-inner", (host, { offer }) => {
    host.replaceChildren(offer("div", "inner-face", "Drawn"));
    return { host };
  });
  registerInitial("lf-outer", (host) => {
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
  registerInitial("lf-later", (node, { offer, offerElement }) => {
    const control = offer("button", "later-button", "Run");
    offerElement(control, "later-button");
    node.append(control);
    return { control };
  });
  bindVocabulary(host, { revision: 1, declarations: registry });
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
  registerInitial("lf-arrival", (node, { offer }) => {
    node.append(offer("button", "arrival-button", "Run"));
    return { node };
  });
  bindVocabulary(arriving, { revision: 1, declarations: registry });
  initialRender(arriving);
  const after = stageWidgetDescriptors(arriving, { kind: "page", revision: 2 });
  assert.deepEqual(after.descriptors.get("arrival").parent, {
    id: "quote",
    tag: "lf-quoted-parent",
  });
  assert.equal(after.descriptors.get("arrival").quoted, true);
});

test("each publication selects its own widgets while native and widget selectors remain idioms", () => {
  const roots = [];
  for (const [revision, verb] of [
    [101, "choose"],
    [102, "pick"],
  ]) {
    const declarations = {
      $layer: { generation: `publication-${revision}` },
      "lf-publication-parent": {},
      "lf-publication-owner": { "x-state": { [verb]: { record: {} } } },
      "lf-publication-owner[checked]": {
        description: "A selected widget.",
        "x-example": "<lf-publication-owner checked></lf-publication-owner>",
        "x-space": "column",
      },
      table: {
        description: "Native table.",
        "x-example": "<table></table>",
        "x-space": "wide",
      },
    };
    const root = document.createElement("main");
    root.innerHTML =
      '<lf-publication-parent id="parent"><table id="native"><tbody><tr><td><lf-publication-owner id="owner" checked>Decision</lf-publication-owner></td></tr></tbody></table></lf-publication-parent>';
    bindVocabulary(root, { revision, declarations });
    roots.push(root);
    const descriptors = stageWidgetDescriptors(root, {
      kind: "thread",
      revision,
    }).descriptors;
    assert.deepEqual([...descriptors.keys()], ["parent", "owner"]);
    assert.deepEqual(descriptors.get("owner").ancestors, [
      { id: "parent", tag: "lf-publication-parent" },
    ]);
    assert.deepEqual(Object.keys(descriptors.get("owner").declaration["x-state"]), [
      verb,
    ]);
    assert.equal(addressableLabel(root.querySelector("table")), "Decision");
  }
  // Revisit the old publication after warming the new one's index.
  for (const [root, verb] of [
    [roots[1], "pick"],
    [roots[0], "choose"],
  ])
    assert.deepEqual(
      stateSpecs(root).map(({ tag, verb, spec }) => [tag, verb, spec.record]),
      [["lf-publication-owner", verb, {}]],
    );
});
