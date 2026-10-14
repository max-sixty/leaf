import {
  initialOrigin,
  initialParent,
  initialSource
} from "./bundle-initial-render.js";
import {
  shadowStage
} from "./bundle-stylesheets.js";
import {
  elementById,
  elementReading
} from "./bundle-passage-facts.js";
import {
  PAGE_PAINT_ATTRIBUTE,
  elementDeclarations,
  recordedWidgetSelector,
  reportPageError,
  stateSpecs
} from "./bundle-page-paint.js";
import {
  readPart,
  runtime
} from "./bundle-semantic-state.js";
import {
  authoredRank,
  isElementName,
  render
} from "./bundle-queued-work.js";

// runtime/widget-upgrade.js
var initialized = /* @__PURE__ */ new WeakSet();
function once(el) {
  if (initialized.has(el)) return false;
  initialized.add(el);
  if (!el.hasAttribute(PAGE_PAINT_ATTRIBUTE.done))
    el.setAttribute(PAGE_PAINT_ATTRIBUTE.done, "1");
  return true;
}
var dataBody = (el) => el.querySelector(":scope > pre").textContent;
var bodyText = (el) => dataBody(el).replace(/^\n+/, "").trimEnd();
function failSoft(el, err, source) {
  reportFailure(el, err);
  showFailure(el, `<${widgetOf(el).localName}> failed: ${err?.message || err}`, source);
}
function reportFailure(el, err) {
  const owner = widgetOf(el);
  reportPageError(
    err,
    `<${owner.localName}${owner.id ? ` id="${owner.id}"` : ""}> failed`
  );
}
function failSoftUnreported(el, err) {
  showFailure(el, `<${widgetOf(el).localName}> failed: ${err?.message || err}`);
}
var widgetOf = (el) => {
  let owner = el;
  while (owner.parentElement && !owner.localName.includes("-"))
    owner = owner.parentElement;
  return owner.localName.includes("-") ? owner : el;
};
function showFailure(el, text, source) {
  const box = document.createElement("div");
  box.className = "lf-error";
  box.textContent = text;
  if (source) {
    const pre = document.createElement("pre");
    pre.textContent = source;
    box.append(pre);
  }
  if (el.shadowRoot) {
    shadowStage(el, [box]);
    return;
  }
  releaseTemplate(el);
  el.replaceChildren();
  render(box, el);
}
function releaseTemplate(el) {
  const part = el._$litPart$;
  if (!part) return;
  part.setConnected(false);
  delete el._$litPart$;
}

// runtime/projection/authored.js
var authoredStates = readPart((root) => root.document.authored);
var authoredParents = /* @__PURE__ */ new WeakMap();
var recordedOwner = (member) => {
  const selector = recordedWidgetSelector();
  return selector ? member.closest(selector) : null;
};
var ownedRecordMembers = (widget, selector) => [...widget.querySelectorAll(selector)].filter(
  (member) => recordedOwner(member) === widget
);
function domValue(el, record) {
  if (record.kind === "attribute")
    return ownedRecordMembers(el, `[${record.attr}]`).map((o) => o.id).filter(Boolean).sort();
  if (record.kind === "value") return el.getAttribute(record.attr);
  if (record.kind === "position") return el.closest(record.within)?.id ?? null;
  return elementReading(el);
}
function rememberAuthoredParents(root = document, parent = root.parentElement) {
  if (root.nodeType === Node.ELEMENT_NODE && !authoredParents.has(root))
    authoredParents.set(root, root.parentElement ? initialParent(root) : parent);
  for (const element of root.querySelectorAll("*"))
    if (!authoredParents.has(element))
      authoredParents.set(element, initialParent(element));
}
function initialState(widget, spec) {
  const record = spec.record;
  if (spec.unit !== "widget") {
    const value2 = {};
    if (record?.kind !== "position") return { value: value2, units: {} };
    const ranks = {};
    for (const container of widget.querySelectorAll(record.within))
      if (container.id && recordedOwner(container) === widget) {
        const ids = [...container.children].filter((part) => part.id).map((part) => part.id);
        value2[container.id] = ids;
        ids.forEach((id, index) => ranks[id] = authoredRank(index));
      }
    return { value: value2, ranks, units: {} };
  }
  let value = null;
  if (record?.kind === "attribute")
    value = ownedRecordMembers(widget, `[${record.attr}]`).map((member) => member.id).filter(Boolean).sort();
  else if (record?.kind === "value") value = widget.getAttribute(record.attr);
  else if (record?.kind === "body") value = dataBody(widget);
  return { action: null, value, detail: record ? { value } : {} };
}
function stageAuthoredStates(root = document, existing = authoredStates()) {
  root = initialSource(root);
  const captured = /* @__PURE__ */ new Map();
  const byTag = /* @__PURE__ */ new Map();
  for (const { tag, verb, spec } of stateSpecs()) {
    const specs = byTag.get(tag) ?? /* @__PURE__ */ new Map();
    specs.set(verb, spec);
    byTag.set(tag, specs);
  }
  for (const [tag, specs] of byTag) {
    const widgets = [...root.querySelectorAll(tag)];
    if (root instanceof Element && root.matches(tag)) widgets.unshift(root);
    for (const widget of widgets) {
      if (!widget.id || existing.has(widget.id)) continue;
      captured.set(widget.id, {
        tag,
        specs,
        state: Object.fromEntries(
          [...specs].map(([verb, spec]) => [verb, initialState(widget, spec)])
        )
      });
    }
  }
  return captured;
}

// runtime/widget-descriptors.js
var byElement = /* @__PURE__ */ new WeakMap();
var byId = /* @__PURE__ */ new Map();
var elements = /* @__PURE__ */ new Map();
var declaredTags = () => elementDeclarations().map(([tag]) => tag);
var candidates = (root) => {
  const tags = declaredTags();
  if (!tags.length) return [];
  const selector = tags.join(",");
  const found = [...root.querySelectorAll(selector)];
  if (root.nodeType === Node.ELEMENT_NODE && root.matches(selector))
    found.unshift(root);
  return found;
};
var parentOf = (element) => {
  if (authoredParents.has(element)) return authoredParents.get(element);
  if (element.parentElement) return element.parentElement;
  const live = initialOrigin(element);
  return authoredParents.has(live) ? authoredParents.get(live) : initialParent(live);
};
var declaredAncestors = (element) => {
  const ancestors = [];
  for (let parent = parentOf(element); parent; parent = parentOf(parent))
    if (parent.id && isElementName(parent.localName) && runtime.registry[parent.localName])
      ancestors.push({ id: parent.id, tag: parent.localName });
  return ancestors;
};
var quotedBy = (element) => {
  for (let node = parentOf(element); node; node = parentOf(node))
    if (runtime.registry[node.localName]?.["x-exhibit"]) return true;
  return false;
};
function stageWidgetDescriptors(root = document, documentContext = { kind: "page", revision: runtime.currentRevision }) {
  const captured = /* @__PURE__ */ new Map();
  const bindings = [];
  for (const element of candidates(initialSource(root))) {
    if (!element.id) continue;
    const live = initialOrigin(element);
    const existing = byElement.get(live);
    if (existing && existing.document.kind === documentContext.kind && (documentContext.kind === "thread" || existing.document.revision === documentContext.revision)) {
      captured.set(element.id, existing);
      continue;
    }
    const declaration = structuredClone(runtime.registry[element.localName]);
    const ancestors = declaredAncestors(element);
    const descriptor = {
      id: element.id,
      tag: element.localName,
      document: structuredClone(documentContext),
      declaration,
      parent: ancestors[0] ?? null,
      ancestors,
      quoted: quotedBy(element)
    };
    bindings.push({ element: live, descriptor });
    captured.set(element.id, descriptor);
  }
  return Object.freeze({
    descriptors: captured,
    bindings: Object.freeze(bindings)
  });
}
function commitWidgetDescriptors(stage, retired = /* @__PURE__ */ new Set()) {
  for (const id of retired) {
    byId.delete(id);
    elements.delete(id);
  }
  for (const { element, descriptor } of stage.bindings) {
    byElement.set(element, descriptor);
    byId.set(descriptor.id, descriptor);
    elements.set(descriptor.id, element);
  }
}
var widgetElement = (id) => elementById(id) ?? elements.get(id) ?? null;
function widgetDescriptor(owner) {
  const captured = byElement.get(owner);
  if (captured) return captured;
  const replacement = byId.get(owner.id);
  if (!replacement || !descriptorStillMatches(owner, replacement)) return null;
  byElement.set(owner, replacement);
  return replacement;
}
var quoted = (element) => widgetDescriptor(element)?.quoted ?? quotedBy(element);
var descriptorStillMatches = (owner, descriptor) => owner.id === descriptor.id && owner.localName === descriptor.tag;

// runtime/abort.js
var aborted = (signal) => {
  const { promise, resolve } = Promise.withResolvers();
  if (signal.aborted) resolve();
  else signal.addEventListener("abort", () => resolve(), { once: true });
  return promise;
};

export {
  once,
  dataBody,
  bodyText,
  failSoft,
  reportFailure,
  failSoftUnreported,
  authoredStates,
  domValue,
  rememberAuthoredParents,
  stageAuthoredStates,
  stageWidgetDescriptors,
  commitWidgetDescriptors,
  widgetElement,
  widgetDescriptor,
  quoted,
  descriptorStillMatches,
  aborted
};
