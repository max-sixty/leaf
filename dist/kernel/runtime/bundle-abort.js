import { dataBody } from "./bundle-portable.js";
import { authoredRank, elementDeclarations, exhibits, isElementName, readPart, recordedWidgetSelector, runtime, stateSpecs } from "./bundle-layer-stack.js";
import { elementById, elementReading } from "./bundle-passages.js";

//#region runtime/projection/authored.js
const authoredStates = readPart((root) => root.document.authored);
const authoredParents = /* @__PURE__ */ new WeakMap();
const recordedOwner = (member, record) => {
	const selector = recordedWidgetSelector(record);
	return selector ? member.parentElement?.closest(selector) ?? null : null;
};
const ownedRecordMembers = (widget, selector, record) => [...widget.querySelectorAll(selector)].filter((member) => recordedOwner(member, record) === widget);
function domValue(el, record) {
	if (record.kind === "attribute") return ownedRecordMembers(el, `[${record.attr}]`, record).map((o) => o.id).filter(Boolean).sort();
	if (record.kind === "value") return el.getAttribute(record.attr);
	if (record.kind === "position") return el.closest(record.within)?.id ?? null;
	return elementReading(el);
}
function rememberAuthoredParents(root = document, parent = root.parentElement, original = (node) => node) {
	const remember = (element) => {
		const live = original(element);
		if (authoredParents.has(live)) return;
		authoredParents.set(live, element.parentElement ? original(element.parentElement) : parent ?? live.parentElement);
	};
	if (root.nodeType === Node.ELEMENT_NODE) remember(root);
	for (const element of root.querySelectorAll("*")) remember(element);
}
function initialState(widget, spec) {
	const record = spec.record;
	if (spec.unit !== "widget") {
		const value = {};
		if (record?.kind !== "position") return {
			value,
			units: {}
		};
		const ranks = {};
		for (const container of widget.querySelectorAll(record.within)) if (container.id && recordedOwner(container, record) === widget) {
			const ids = [...container.children].filter((part) => part.id).map((part) => part.id);
			value[container.id] = ids;
			ids.forEach((id, index) => ranks[id] = authoredRank(index));
		}
		return {
			value,
			ranks,
			units: {}
		};
	}
	let value = null;
	if (record?.kind === "attribute") value = ownedRecordMembers(widget, `[${record.attr}]`, record).map((member) => member.id).filter(Boolean).sort();
	else if (record?.kind === "value") value = widget.getAttribute(record.attr);
	else if (record?.kind === "body") value = dataBody(widget);
	return {
		action: null,
		value,
		detail: record ? { value } : {}
	};
}
function stageAuthoredStates(root = document, existing = authoredStates()) {
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
				state: Object.fromEntries([...specs].map(([verb, spec]) => [verb, initialState(widget, spec)]))
			});
		}
	}
	return captured;
}

//#endregion
//#region runtime/widget-descriptors.js
const byElement = /* @__PURE__ */ new WeakMap();
const byId = /* @__PURE__ */ new Map();
const elements = /* @__PURE__ */ new Map();
const declaredTags = () => elementDeclarations().map(([tag]) => tag);
const candidates = (root) => {
	const tags = declaredTags();
	if (!tags.length) return [];
	const selector = tags.join(",");
	const found = [...root.querySelectorAll(selector)];
	if (root.nodeType === Node.ELEMENT_NODE && root.matches(selector)) found.unshift(root);
	return found;
};
const parentOf = (element) => authoredParents.has(element) ? authoredParents.get(element) : element.parentElement;
const declaredAncestors = (element) => {
	const ancestors = [];
	for (let parent = parentOf(element); parent; parent = parentOf(parent)) if (parent.id && isElementName(parent.localName) && runtime.registry[parent.localName]) ancestors.push({
		id: parent.id,
		tag: parent.localName
	});
	return ancestors;
};
const quotedBy = (element) => {
	for (let node = parentOf(element); node; node = parentOf(node)) if (exhibits(node, runtime.registry[node.localName])) return true;
	return false;
};
function stageWidgetDescriptors(root = document, documentContext = {
	kind: "page",
	revision: runtime.currentRevision
}) {
	const captured = /* @__PURE__ */ new Map();
	const bindings = [];
	for (const element of candidates(root)) {
		if (!element.id) continue;
		const existing = byElement.get(element);
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
		bindings.push({
			element,
			descriptor
		});
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
const widgetElement = (id) => elementById(id) ?? elements.get(id) ?? null;
function widgetDescriptor(owner) {
	const captured = byElement.get(owner);
	if (captured) return captured;
	const replacement = byId.get(owner.id);
	if (!replacement || !descriptorStillMatches(owner, replacement)) return null;
	byElement.set(owner, replacement);
	return replacement;
}
const quoted = (element) => widgetDescriptor(element)?.quoted ?? quotedBy(element);
const descriptorStillMatches = (owner, descriptor) => owner.id === descriptor.id && owner.localName === descriptor.tag;

//#endregion
//#region runtime/abort.js
const aborted = (signal) => {
	const { promise, resolve } = Promise.withResolvers();
	if (signal.aborted) resolve();
	else signal.addEventListener("abort", () => resolve(), { once: true });
	return promise;
};

//#endregion
export { aborted, authoredStates, commitWidgetDescriptors, descriptorStillMatches, domValue, quoted, rememberAuthoredParents, stageAuthoredStates, stageWidgetDescriptors, widgetDescriptor, widgetElement };