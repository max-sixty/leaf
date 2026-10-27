import { move, watchCurrentLocationIn } from "./bundle-dom-move.js";
import { PAGE_PAINT_ATTRIBUTE, reportPageError } from "./bundle-layer-client.js";
import { SHADOW_LEADING_CSS, annotationMarkSheets, elementDeclarations, exhibits, marksSheet, recordedWidgetSelector, shadowRules, stateSpecs, watchArrivalsIn, watchLayers } from "./bundle-geometry.js";
import { authoredRank, isElementName, readPart, render, runtime } from "./bundle-context.js";
import { PRESS, paintKeysWithin, rowArrows } from "./bundle-errors.js";
import { elementById, elementReading, inChrome, watchPassageRoot } from "./bundle-passages.js";
import { initialOrigin, initialParent, initialSource } from "./bundle-initial-render.js";
import { diffArrays } from "/vendor/jsdiff.esm.js";

//#region runtime/keyboard/disclosure.js
const disclosureWatch = new MutationObserver((records) => {
	for (const r of records) if (r.target.getAttribute(r.attributeName) !== r.oldValue) paintKeysWithin(r.target);
});
const watchDisclosures = (root) => disclosureWatch.observe(root, {
	subtree: true,
	attributeFilter: ["open", "aria-expanded"],
	attributeOldValue: true
});
const DISCLOSE = (el) => {
	const open = disclosed(el);
	if (open === null) return [
		...PRESS,
		"ArrowLeft",
		"ArrowRight"
	];
	const [back, ahead] = rowArrows(el);
	return inChrome(el) ? PRESS : [...PRESS, open ? back : ahead];
};
const DISCLOSURE_SELECTOR = "details > summary, :is(button, [role=\"button\"])[aria-expanded]";
function disclosed(el) {
	return !el?.matches?.("details > summary, :is(button, [role=\"button\"])[aria-expanded]") ? null : el.matches("details > summary") ? el.parentElement.open : el.getAttribute("aria-expanded") === "true";
}

//#endregion
//#region runtime/dom-children.js
function setChildren(parent, nodes) {
	setChildLists([[parent, nodes]]);
}
function setChildLists(lists) {
	for (const [parent, nodes] of lists) orderChildren(parent, nodes);
	for (const [parent, nodes] of lists) {
		const keep = new Set(nodes);
		for (const child of [...parent.childNodes]) if (!keep.has(child)) child.remove();
	}
}
function orderChildren(parent, nodes) {
	const owned = new Set(nodes);
	order(parent, nodes, (node) => !owned.has(node));
}
function setRenderedChildren(parent, nodes) {
	const after = document.createDocumentFragment();
	after.append(...nodes);
	patchChildren(parent, parent, after, {
		pairs: new Map([...sourceNodes(parent)].map((node) => [node, node])),
		arrive: (node) => node,
		sameValue: (name, held, wanted) => held === wanted,
		touched: () => {},
		declared: () => false,
		body: () => null,
		same: (held, wanted) => held.isEqualNode(wanted),
		generated: () => false
	});
}
function order(parent, nodes, passed = () => false) {
	const list = [...nodes];
	const stay = staying(parent, list);
	let cursor = parent.firstChild;
	for (const node of list) {
		while (cursor && passed(cursor)) cursor = cursor.nextSibling;
		if (node === cursor) cursor = cursor.nextSibling;
		else if (stay.has(node)) cursor = node.nextSibling;
		else move(parent, node, cursor);
	}
}
function staying(parent, nodes) {
	const places = new Map([...parent.childNodes].map((node, at) => [node, at + 1]));
	const size = places.size;
	const best = new Array(size + 1).fill(-1);
	const weightAt = new Array(size + 1).fill(0);
	const weights = [];
	const previous = [];
	let last = -1;
	nodes.forEach((node, at) => {
		const place = places.get(node);
		if (!place) return;
		let before = -1;
		for (let i = place - 1; i > 0; i -= i & -i) if (best[i] >= 0 && (before < 0 || weightAt[i] >= weights[before])) before = best[i];
		const weight = (node.nodeType === Node.ELEMENT_NODE ? nodes.length + 1 : 1) + (before < 0 ? 0 : weights[before]);
		weights[at] = weight;
		previous[at] = before;
		for (let i = place; i <= size; i += i & -i) if (best[i] < 0 || weight >= weightAt[i]) {
			best[i] = at;
			weightAt[i] = weight;
		}
		if (last < 0 || weight >= weights[last]) last = at;
	});
	const stay = /* @__PURE__ */ new Set();
	for (let at = last; at >= 0; at = previous[at]) stay.add(nodes[at]);
	return stay;
}
function patchTree(before, after, rules) {
	const live = rules.pairs.get(before);
	patchAttributes(live, before, after, rules);
	patchChildren(holder(live, rules), tree(before), tree(after), rules);
}
function patchRetains(before, after, target, rules) {
	if (!target?.isConnected) return false;
	if (!sourceOwns(before, target, rules)) return true;
	return retainedWithin(before, after, target, rules);
}
function sourceOwns(source, target, rules) {
	const owns = (node) => rules.contains(target, rules.pairs.get(node));
	if (owns(source)) return true;
	for (const node of sourceNodes(source)) if (owns(node)) return true;
	return false;
}
function retainedWithin(before, after, target, rules) {
	const live = rules.pairs.get(before);
	if (!live || !sourceOwns(before, target, rules)) return false;
	if (kept(before, after, rules)) return true;
	if (live === target) return false;
	if (before.attributes.length !== after.attributes.length || [...before.attributes].some(({ name, value }) => !after.hasAttribute(name) || !rules.sameValue(name, value, after.getAttribute(name)))) return false;
	const children = [...tree(before).childNodes];
	const matches = new Map([...matchNodes(children, [...tree(after).childNodes])].map(([wanted, held]) => [held, wanted]));
	for (const held of children) {
		const node = rules.pairs.get(held);
		if (node?.nodeType !== Node.ELEMENT_NODE || !sourceOwns(held, target, rules)) continue;
		const wanted = matches.get(held);
		if (!wanted) return false;
		if (!(atomic(held, wanted, node, rules) ? kept(held, wanted, rules) : retainedWithin(held, wanted, target, rules))) return false;
	}
	return true;
}
const tree = (node) => node.localName === "template" ? node.content : node;
const holder = (live, rules) => rules.body(live) ?? tree(live);
function patchAttributes(live, before, after, rules) {
	let changed = false;
	for (const { name, value } of [...before.attributes]) {
		if (after.hasAttribute(name)) continue;
		if (name === "class") live.classList.remove(...tokens(value));
		else live.removeAttribute(name);
		changed = true;
	}
	for (const { name, value } of after.attributes) {
		const held = before.getAttribute(name);
		if (held !== null && rules.sameValue(name, held, value)) continue;
		if (name === "class") {
			live.classList.remove(...tokens(held ?? ""));
			live.classList.add(...tokens(value));
		} else live.setAttribute(name, value);
		changed = true;
	}
	if (changed) rules.touched(live);
}
const tokens = (value) => value.split(/\s+/).filter(Boolean);
function writeText(node, next) {
	const held = node.data;
	if (held === next) return;
	let prefix = 0;
	while (prefix < held.length && prefix < next.length && held[prefix] === next[prefix]) prefix += 1;
	let suffix = 0;
	while (suffix < held.length - prefix && suffix < next.length - prefix && held[held.length - suffix - 1] === next[next.length - suffix - 1]) suffix += 1;
	node.replaceData(prefix, held.length - prefix - suffix, next.slice(prefix, next.length - suffix));
}
function evict(before, live, rules) {
	live.remove();
	for (const inner of sourceNodes(before)) {
		const stray = rules.pairs.get(inner);
		if (!stray?.parentNode || live.contains(stray)) continue;
		stray.remove();
	}
}
function* sourceNodes(node) {
	for (const child of tree(node).childNodes) {
		yield child;
		yield* sourceNodes(child);
	}
}
function patchChildren(liveParent, beforeParent, afterParent, rules) {
	const held = [...beforeParent.childNodes];
	const wanted = [...afterParent.childNodes];
	const matches = matchNodes(held, wanted);
	const matched = new Set(matches.values());
	for (const node of held) {
		if (matched.has(node)) continue;
		evict(node, rules.pairs.get(node), rules);
	}
	const placed = [];
	for (const node of wanted) {
		const before = matches.get(node);
		const held = before && rules.pairs.get(before);
		const live = held?.parentNode ? held : null;
		if (!live) {
			placed.push(rules.arrive(node, liveParent));
			continue;
		}
		if (node.nodeType !== Node.ELEMENT_NODE) writeText(live, node.data);
		else if (!atomic(before, node, live, rules)) patchTree(before, node, rules);
		else if (!kept(before, node, rules)) {
			evict(before, live, rules);
			placed.push(rules.arrive(node, liveParent));
			continue;
		}
		rules.pairs.set(node, live);
		if (live.parentNode === liveParent) placed.push(live);
	}
	order(liveParent, placed, rules.generated);
}
const atomic = (before, after, live, rules) => before.matches("style, link[rel~=\"stylesheet\" i]") || rules.declared(before) && !rules.reaches(before, after) || [...tree(before).childNodes].some((node) => rules.pairs.get(node)?.parentNode !== holder(live, rules));
const kept = (before, after, rules) => rules.declared(before) ? rules.unchanged(before, after) : rules.same(before, after);
function matchNodes(held, wanted) {
	const matches = /* @__PURE__ */ new Map();
	const matched = /* @__PURE__ */ new Set();
	const byId = /* @__PURE__ */ new Map();
	for (const node of held) if (node.nodeType === Node.ELEMENT_NODE && node.id && !byId.has(node.id)) byId.set(node.id, node);
	for (const node of wanted) {
		if (node.nodeType !== Node.ELEMENT_NODE || !node.id) continue;
		const match = byId.get(node.id);
		if (!match || match.localName !== node.localName || matched.has(match)) continue;
		matches.set(node, match);
		matched.add(match);
	}
	alignRest(held.filter((node) => !matched.has(node)), wanted.filter((node) => !matches.has(node)), matches);
	return matches;
}
const COLLAPSE = /\s+/g;
const signature = (node) => {
	if (node.nodeType !== Node.ELEMENT_NODE) return `${node.nodeType}:${node.data}`;
	const words = (node.localName === "template" ? node.content : node).textContent;
	return `1:${node.localName}#${node.id}:${words.replace(COLLAPSE, " ").trim()}`;
};
function alignRest(held, wanted, matches) {
	let heldAt = 0;
	let wantedAt = 0;
	let gapHeld = [];
	let gapWanted = [];
	const closeGap = () => {
		pairInGap(gapHeld, gapWanted, matches);
		gapHeld = [];
		gapWanted = [];
	};
	for (const run of diffArrays(held.map(signature), wanted.map(signature))) {
		const count = run.value.length;
		if (run.added) gapWanted.push(...wanted.slice(wantedAt, wantedAt += count));
		else if (run.removed) gapHeld.push(...held.slice(heldAt, heldAt += count));
		else {
			closeGap();
			for (let at = 0; at < count; at++) matches.set(wanted[wantedAt + at], held[heldAt + at]);
			heldAt += count;
			wantedAt += count;
		}
	}
	closeGap();
}
function pairInGap(held, wanted, matches) {
	let heldAt = 0;
	let wantedAt = 0;
	for (const run of diffArrays(held, wanted, { comparator: interchangeable })) {
		const count = run.value.length;
		if (run.added) wantedAt += count;
		else if (run.removed) heldAt += count;
		else {
			for (let at = 0; at < count; at++) matches.set(wanted[wantedAt + at], held[heldAt + at]);
			heldAt += count;
			wantedAt += count;
		}
	}
}
const interchangeable = (held, wanted) => held.nodeType === wanted.nodeType && (held.nodeType !== Node.ELEMENT_NODE || held.localName === wanted.localName && !(held.id && wanted.id));

//#endregion
//#region runtime/shadow-stage.js
const stageStyles = /* @__PURE__ */ new WeakMap();
function shadowStage(host, nodes) {
	const root = host.shadowRoot ?? host.attachShadow({ mode: "open" });
	watchArrivalsIn(root);
	root.adoptedStyleSheets = [.../* @__PURE__ */ new Set([
		...root.adoptedStyleSheets,
		...annotationMarkSheets,
		marksSheet
	])];
	watchDisclosures(root);
	watchLayers(root);
	watchCurrentLocationIn(root);
	const rules = SHADOW_LEADING_CSS + shadowRules;
	let style = stageStyles.get(root);
	if (style?.textContent !== rules) {
		style = document.createElement("style");
		style.textContent = rules;
		stageStyles.set(root, style);
	}
	setChildren(root, [style, ...nodes]);
	for (const child of [...host.childNodes]) child.remove();
	watchPassageRoot(root);
	return root;
}

//#endregion
//#region runtime/widget-upgrade.js
const initialized = /* @__PURE__ */ new WeakSet();
function once(el) {
	if (initialized.has(el)) return false;
	initialized.add(el);
	if (!el.hasAttribute(PAGE_PAINT_ATTRIBUTE.done)) el.setAttribute(PAGE_PAINT_ATTRIBUTE.done, "1");
	return true;
}
const dataBody = (el) => el.querySelector(":scope > pre").textContent;
const bodyText = (el) => dataBody(el).replace(/^\n+/, "").trimEnd();
function failSoft(el, err, source) {
	reportFailure(el, err);
	showFailure(el, `<${widgetOf(el).localName}> failed: ${err?.message || err}`, source);
}
function reportFailure(el, err) {
	const owner = widgetOf(el);
	reportPageError(err, `<${owner.localName}${owner.id ? ` id="${owner.id}"` : ""}> failed`);
}
function failSoftUnreported(el, err) {
	showFailure(el, `<${widgetOf(el).localName}> failed: ${err?.message || err}`);
}
const widgetOf = (el) => {
	let owner = el;
	while (owner.parentElement && !owner.localName.includes("-")) owner = owner.parentElement;
	return owner.localName.includes("-") ? owner : el;
};
const placers = /* @__PURE__ */ new WeakMap();
const placesFailure = (el, place) => placers.set(el, place);
function showFailure(el, text, source) {
	const box = document.createElement("div");
	box.className = "lf-error";
	box.textContent = text;
	if (source) {
		const pre = document.createElement("pre");
		pre.textContent = source;
		box.append(pre);
	}
	if (placers.get(el)?.(box)) return;
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

//#endregion
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
function rememberAuthoredParents(root = document, parent = root.parentElement) {
	if (root.nodeType === Node.ELEMENT_NODE && !authoredParents.has(root)) authoredParents.set(root, root.parentElement ? initialParent(root) : parent);
	for (const element of root.querySelectorAll("*")) if (!authoredParents.has(element)) authoredParents.set(element, initialParent(element));
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
const parentOf = (element) => {
	if (authoredParents.has(element)) return authoredParents.get(element);
	if (element.parentElement) return element.parentElement;
	const live = initialOrigin(element);
	return authoredParents.has(live) ? authoredParents.get(live) : initialParent(live);
};
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
		bindings.push({
			element: live,
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
export { DISCLOSE, DISCLOSURE_SELECTOR, aborted, authoredStates, bodyText, commitWidgetDescriptors, dataBody, descriptorStillMatches, disclosed, domValue, failSoft, failSoftUnreported, once, orderChildren, patchRetains, patchTree, placesFailure, quoted, rememberAuthoredParents, reportFailure, setChildLists, setChildren, setRenderedChildren, shadowStage, stageAuthoredStates, stageWidgetDescriptors, watchDisclosures, widgetDescriptor, widgetElement };