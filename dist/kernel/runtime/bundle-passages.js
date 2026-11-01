import { PAGE_PAINT_ATTRIBUTE, isElement, isHTML, isNode, isText, pageUpgraded, renderedOrder, renderedParent, renderedUnder, shadowHost, under, upFrom } from "./bundle-portable.js";
import { COLLAPSE, SAID, TEXT_BLOCK, UI_MARKS, decisionFor, declaredRoot, inUi, overIn, pageShadowRoots, readPart, refuseShadowRoot, registry, shadowRootsIn, uiInside } from "./bundle-layer-stack.js";
import { reportPageError } from "./bundle-layer-client.js";
import { diffArrays } from "/vendor/jsdiff.esm.js";

//#region runtime/text-alignment.js
const textUnits = new Intl.Segmenter(void 0, { granularity: "word" });
const sentenceUnits = new Intl.Segmenter(void 0, { granularity: "sentence" });
const MAX_EDIT_LENGTH = 1e3;
function alignText(before, after, units = textUnits, maxEditLength = MAX_EDIT_LENGTH) {
	const left = [...units.segment(before)].map((part) => part.segment);
	const right = [...units.segment(after)].map((part) => part.segment);
	const changes = diffArrays(left, right, { maxEditLength });
	if (!changes) return [{
		kind: "delete",
		text: before
	}, {
		kind: "insert",
		text: after
	}].filter((run) => run.text);
	return changes.map((change) => ({
		kind: change.added ? "insert" : change.removed ? "delete" : "same",
		text: change.value.join("")
	})).filter((run) => run.text);
}
function alignInlineText(before, after) {
	const coarse = alignText(before, after, sentenceUnits)[Symbol.iterator]();
	const runs = [];
	const push = (run) => {
		const last = runs.at(-1);
		if (last?.kind === run.kind) last.text += run.text;
		else runs.push({ ...run });
	};
	let current = coarse.next();
	while (!current.done) {
		const run = current.value;
		const next = coarse.next();
		if (run.kind !== "delete" || next.done || next.value.kind !== "insert") {
			push(run);
			current = next;
			continue;
		}
		const replacement = next.value;
		const fine = alignText(run.text, replacement.text);
		if (fine.filter((part) => part.kind === "same").reduce((length, part) => length + part.text.length, 0) >= Math.min(run.text.length, replacement.text.length) * .6) fine.forEach(push);
		else {
			push(run);
			push(replacement);
		}
		current = coarse.next();
	}
	return runs;
}

//#endregion
//#region runtime/words.js
const labelWords = (value) => String(value ?? "").replace(COLLAPSE, " ").trim();
function excerptWords(value, cap) {
	const words = labelWords(value);
	const points = [...words];
	if (points.length <= cap) return words;
	const excerpt = points.slice(0, cap - 1);
	const boundary = excerpt.lastIndexOf(" ");
	const end = boundary >= cap / 2 ? boundary : excerpt.length;
	return `${excerpt.slice(0, end).join("")}…`;
}

//#endregion
//#region runtime/passages.js
const passageFences = /* @__PURE__ */ new WeakSet();
const verbatimOwnerIdentity = /* @__PURE__ */ new WeakMap();
const verbatimBoundaryIdentity = /* @__PURE__ */ new WeakMap();
let settledReading = null;
let settledDecisions;
let settled = null;
let settledKey = "[]";
function settlements() {
	if (settledDecisions !== registry.$decisions || !settledReading) {
		const decisions = settledDecisions = registry.$decisions;
		settledReading = readPart((root) => {
			const holders = /* @__PURE__ */ new Map();
			for (const [id, { state }] of root.effective.widgets) {
				const tag = root.document.authored.get(id)?.tag;
				const decision = tag === void 0 ? void 0 : decisions?.[tag];
				const outcome = decision && state[decision.verb]?.detail?.outcome;
				const retires = outcome ? decision.retires[outcome] : null;
				if (tag !== void 0 && retires?.length) holders.set(id, {
					tag,
					retires: [...retires]
				});
			}
			return holders;
		});
	}
	const next = settledReading();
	if (next !== settled) {
		settled = next;
		settledKey = JSON.stringify([...settled]);
	}
	return settled;
}
function retiredSlot(el) {
	const holder = upFrom(el);
	if (!holder?.id || el.ownerDocument !== document) return false;
	const settlement = settlements().get(holder.id);
	return settlement?.tag === holder.localName && settlement.retires.includes(el.localName);
}
function renderRetired(el, outcome) {
	const outcomes = decisionFor(el.localName)?.retires;
	if (!outcomes) return;
	for (const [candidate, tags] of Object.entries(outcomes)) for (const tag of tags) for (const root of [el, ...el.shadowRoot ? [el.shadowRoot] : []]) for (const slot of root.children) if (slot.localName === tag) slot.toggleAttribute(PAGE_PAINT_ATTRIBUTE.retired, candidate === outcome);
}
function settledAway(el) {
	let at = el;
	for (; at; at = at.parentElement) if (retiredSlot(at)) return true;
	const nodes = [...el.childNodes];
	return nodes.some((n) => isElement(n) && retiredSlot(n)) && nodes.every((n) => isElement(n) ? retiredSlot(n) || uiInside(n, el) : !isText(n) || !n.data.trim());
}
const GENERATED = ".lf-ui, [data-lf-gen]";
const DATUM = "[data-lf-projection][data-lf-datum]";
const inChrome = (node) => Boolean(node && closestAcross(node, ".lf-chrome"));
const showsWords = (block) => block.checkVisibility({ visibilityProperty: true });
const LEAF_SURFACE = ".lf-chrome, [data-lf-runtime]";
const leafSurface = (node) => isNode(node) ? closestAcross(node, LEAF_SURFACE) : null;
const pageWords = (node) => inPage(node) && !inUi(node);
const bareTextRefusal = (n) => {
	const host = shadowHost(n.getRootNode());
	const at = host ? `<${host.localName}${host.id ? ` id="${host.id}"` : ""}>` : "a module";
	return /* @__PURE__ */ new Error(`${at} staged bare text into a shadow root: ${JSON.stringify(n.data.trim().slice(0, 40).trim())} has no element over it, so the page holds no block, cell or fence for it. Give a module's rendered words an element to sit in.`);
};
const elementOver = (n) => {
	if (n.parentElement) return n.parentElement;
	if (isText(n)) throw bareTextRefusal(n);
	throw new Error("A passage node has no element over it");
};
function refusesBareText(root) {
	const bare = [...root.childNodes].filter(isText).find((node) => node.data.trim());
	if (!bare) return false;
	refuseShadowRoot(root);
	const refusal = bareTextRefusal(bare);
	reportPageError(refusal);
	if (!pageUpgraded()) window.dispatchEvent(new CustomEvent("lf-startup-failed", { detail: {
		reason: refusal.message,
		error: refusal,
		page: true
	} }));
	return true;
}
const frameOf = (node) => {
	for (let a = isElement(node) ? node : upFrom(node); a; a = upFrom(a)) if (a.localName?.startsWith("lf-")) return a;
	return null;
};
const NO_CONTEXT = Object.freeze({
	chrome: false,
	silenced: false,
	generated: false,
	gen: null,
	block: null,
	textBlock: null,
	island: null,
	cells: null
});
const GEN = "[data-lf-gen]";
const ISLAND = "[data-lf-markdown-words]";
const MARKS = [
	UI_MARKS,
	GENERATED,
	ISLAND
].join(", ");
const BLOCK_TAGS = new Set(TEXT_BLOCK.split(","));
const BLOCKS = `${TEXT_BLOCK}, ${DATUM}`;
const chromeMark = (el) => el.matches(".lf-ui, [data-lf-said]") ? !el.matches(SAID) : null;
const SILENT_TAGS = /* @__PURE__ */ new Set([
	"script",
	"style",
	"textarea"
]);
const silences = (el) => SILENT_TAGS.has(el.localName) || retiredSlot(el);
const unmodelled = (el) => {
	const attr = el.getAttribute("data-lf-said");
	const parent = el.parentElement;
	return !(attr && parent && registry[parent.localName]?.["x-says"]?.[attr]);
};
const fileModelsPassage = (segments) => segments.every(({ node, gen }) => !isEditing(elementOver(node)) && (!gen || !unmodelled(gen)));
const opaque = (el) => passageFences.has(el);
const editingBoundary = (el) => isEditing(el) !== isEditing(el.parentElement);
const isEditing = (el) => el !== null && isHTML(el) && el.isContentEditable;
function enter(ctx, el, inFrame = true) {
	const marked = el.hasAttributes() && el.matches(MARKS);
	const textBlock = BLOCK_TAGS.has(el.localName);
	const block = textBlock || el.matches("[data-lf-projection][data-lf-datum]");
	const editing = editingBoundary(el);
	const cell = opaque(el) || editing || marked && el.matches(GEN) && unmodelled(el);
	const silent = !ctx.silenced && silences(el);
	if (!marked && !block && !cell && !silent) return ctx;
	const chrome = (marked && inFrame ? chromeMark(el) : null) ?? ctx.chrome;
	const generated = ctx.generated || marked && inFrame && el.matches(GENERATED);
	return {
		chrome,
		silenced: ctx.silenced || silent,
		generated,
		gen: marked && el.matches(GEN) ? el : ctx.gen,
		block: block ? el : ctx.block,
		textBlock: textBlock ? el : ctx.textBlock,
		island: marked && el.matches(ISLAND) ? el : ctx.island,
		cells: cell ? {
			el,
			editing,
			up: ctx.cells
		} : ctx.cells
	};
}
const crossed = (ctx) => ({
	...ctx,
	chrome: false,
	silenced: false,
	generated: false,
	gen: null
});
function contextAt(el, frame) {
	const over = [];
	for (let a = el; a; a = upFrom(a)) over.push(a);
	let ctx = NO_CONTEXT;
	let inFrame = !frame;
	for (const a of over.reverse()) {
		if (a === frame) inFrame = true;
		if (a.parentNode?.nodeType === Node.DOCUMENT_FRAGMENT_NODE) ctx = crossed(ctx);
		ctx = enter(ctx, a, inFrame);
	}
	return ctx;
}
const segmentIn = (node, ctx) => ({
	node,
	start: 0,
	end: node.data.length,
	block: ctx.block ?? (ctx.island ? upFrom(ctx.island) : null),
	textBlock: ctx.textBlock ?? (ctx.island ? upFrom(ctx.island) : null),
	gen: ctx.gen
});
const READINGS = {
	says: (ctx) => !ctx.chrome && !ctx.silenced,
	wrote: (ctx) => !ctx.generated,
	unsilenced: (ctx) => !ctx.chrome
};
const authored = (root) => {
	const frame = frameOf(root);
	return (n) => !overIn(isElement(n) ? n : elementOver(n), GENERATED, frame);
};
function walk(root, onText, skip = null, onBreak = null, onElement = null) {
	const frame = frameOf(root);
	const passed = /* @__PURE__ */ new Map();
	const contextOver = (node) => {
		const over = elementOver(node);
		return passed.get(over) ?? contextAt(over, frame);
	};
	const visitElement = (child, ctx) => {
		if (skip?.(child)) return;
		const inner = enter(ctx, child);
		if (child.localName === "br") onBreak?.(inner);
		else if (isHTML(child, "slot")) {
			passed.set(child, inner);
			onElement?.(child, inner, true);
			for (const assigned of child.assignedNodes({ flatten: true })) isText(assigned) ? onText(assigned, contextOver(assigned)) : isElement(assigned) && visitElement(assigned, contextOver(assigned));
			onElement?.(child, inner, false);
		} else {
			const declared = declaredRoot(child);
			if (declared && !refusesBareText(declared)) {
				passed.set(child, inner);
				visit(declared, crossed(inner), child);
			} else visit(child, inner);
		}
	};
	const visit = (node, ctx, host = null) => {
		const element = host ?? (isElement(node) ? node : null);
		if (element) onElement?.(element, ctx, true);
		for (let child = node.firstChild; child; child = child.nextSibling) if (isText(child)) {
			if (node.nodeType !== Node.ELEMENT_NODE && !child.data.trim()) continue;
			if (node.nodeType !== Node.ELEMENT_NODE) elementOver(child);
			onText(child, ctx);
		} else if (isElement(child)) visitElement(child, ctx);
		if (element) onElement?.(element, ctx, false);
	};
	const host = shadowHost(root);
	visit(root, isElement(root) ? contextAt(root, frame) : host ? crossed(contextAt(host, frame)) : NO_CONTEXT);
}
function textNodesUnder(root, reading = "says", boundary = null, format = "prose") {
	const keeps = READINGS[reading];
	const segments = [];
	let breakBefore = false;
	let lineBefore = "";
	const styles = /* @__PURE__ */ new Map();
	const style = (element) => {
		let value = styles.get(element);
		if (!value) styles.set(element, value = getComputedStyle(element));
		return value;
	};
	walk(root, (node, ctx) => {
		if (keeps(ctx)) {
			segments.push({
				...segmentIn(node, ctx),
				breakBefore,
				...format === "lines" && {
					lineBefore,
					whiteSpace: style(node.assignedSlot ?? elementOver(node)).whiteSpaceCollapse
				}
			});
			breakBefore = false;
			lineBefore = "";
		}
	}, (child) => (root === document || root === root.ownerDocument?.body) && child.matches(".lf-chrome, [data-lf-runtime]") || (boundary?.(child, segments.length) ?? false), (ctx) => {
		if (keeps(ctx)) {
			breakBefore = true;
			lineBefore = "\n";
		}
	}, format === "lines" ? (element, ctx, entering) => {
		if (!keeps(ctx)) return;
		const display = style(element).display;
		if (display === "table-cell") {
			if (!entering && lineBefore !== "\n") lineBefore = "	";
		} else if (/^(block|flow-root|list-item|flex|grid|table|-webkit-box)/.test(display)) lineBefore = "\n";
	} : null);
	return segments;
}
function closestAcross(node, selector) {
	let el = isElement(node) ? node : upFrom(node);
	while (el) {
		const hit = el.closest(selector);
		if (hit) return hit;
		el = shadowHost(el.getRootNode());
	}
	return null;
}
const elementById = (id, root = document) => {
	if (id == null || root === null) return null;
	const page = root === root.ownerDocument?.body;
	const accepts = (node) => node && (!page || !leafSurface(node) && authoredScope(node) === root);
	const found = root === document ? document.getElementById(id) : [...root.querySelectorAll(`[id="${CSS.escape(id)}"]`)].find(accepts);
	if (found && accepts(found)) return found;
	for (const shadow of shadowRootsIn(root)) {
		const inside = shadow.getElementById(id);
		if (accepts(inside)) return inside;
	}
	return null;
};
const pageDocument = (doc = document) => doc.body;
const inPage = (node) => under(node, pageDocument()) && !leafSurface(node);
const isLayoutBox = (box) => getComputedStyle(box).getPropertyValue("--lf-layout-box").trim() === "1";
const layoutBox = () => {
	const main = document.querySelector("body > main");
	if (!main || isLayoutBox(main)) return main;
	const parts = main.querySelector(":scope > [data-lf-views=\"parts\"]");
	return [...main.children, ...[...parts?.children ?? []].flatMap((part) => [...part.children])].find((box) => box.checkVisibility() && isLayoutBox(box)) ?? main;
};
const authoredScope = (node) => closestAcross(node, ".lf-msg-body") ?? pageDocument(node?.ownerDocument ?? document);
const elementFromPointAcross = (x, y) => {
	let el = document.elementFromPoint(x, y);
	for (let root; el && (root = declaredRoot(el));) {
		const inner = root.elementFromPoint(x, y);
		if (!inner || inner === el) break;
		el = inner;
	}
	return el;
};
const pageQueryAll = (selector) => [document, ...pageShadowRoots()].flatMap((root) => {
	return [...root.querySelectorAll(selector)];
});
const beforePoint = (node, container, offset) => {
	if (node === container) return false;
	if (container.nodeType === Node.TEXT_NODE || offset === 0) return renderedOrder(node, container) < 0;
	const next = container.childNodes[offset];
	return next ? renderedOrder(node, next) < 0 : renderedUnder(node, container) || renderedOrder(node, container) < 0;
};
const coveredBy = (range, node) => !beforePoint(node, range.startContainer, range.startOffset) && (node === range.endContainer || beforePoint(node, range.endContainer, range.endOffset));
function segmentsIn(range) {
	const segments = [];
	for (const segment of pageText().segments) {
		const { node } = segment;
		if (!coveredBy(range, node)) continue;
		const start = node === range.startContainer ? range.startOffset : 0;
		const end = node === range.endContainer ? range.endOffset : segment.end;
		if (end > start) segments.push({
			...segment,
			start,
			end
		});
	}
	return segments;
}
const blockAt = (node) => {
	const block = closestAcross(node, BLOCKS);
	if (block) return block;
	const island = closestAcross(node, ISLAND);
	return island ? upFrom(island) : null;
};
const segmentBlock = (segment) => segment.block ?? segment.node.parentElement;
const segmentTextBlock = (segment) => segment.textBlock ?? segment.node.parentElement;
const COLLAPSIBLE = new RegExp(`^(?:${COLLAPSE.source})$`, "u");
function readSegments(segments, mapCharacters) {
	let text = "";
	const units = [];
	let pendingSpace = null;
	const push = (character, start, end) => {
		if (COLLAPSIBLE.test(character)) {
			if (text) pendingSpace = pendingSpace ? {
				start: pendingSpace.start,
				end
			} : {
				start,
				end
			};
			return;
		}
		if (pendingSpace) {
			text += " ";
			if (mapCharacters) units.push({
				text: " ",
				...pendingSpace
			});
			pendingSpace = null;
		}
		text += character;
		if (mapCharacters) units.push({
			text: character,
			start,
			end
		});
	};
	let previous;
	for (const seg of segments) {
		if (previous && (seg.breakBefore || segmentTextBlock(seg) !== segmentTextBlock(previous))) {
			const point = {
				node: seg.node,
				offset: seg.start
			};
			push(" ", point, point);
		}
		let offset = seg.start;
		for (const character of seg.node.data.slice(seg.start, seg.end)) {
			const end = offset + character.length;
			push(character, {
				node: seg.node,
				offset
			}, {
				node: seg.node,
				offset: end
			});
			offset = end;
		}
		previous = seg;
	}
	return mapCharacters ? {
		text,
		units
	} : text;
}
const quoteFrom = (segments) => readSegments(segments, false);
const readingFrom = (segments) => readSegments(segments, true);
const cut = (text, from, to) => [...text].slice(from, to).join("");
function linesFrom(segments) {
	let text = "";
	let separator = "";
	for (const segment of segments) {
		if (segment.lineBefore && text) separator = segment.lineBefore === "\n" || separator === "\n" ? "\n" : "	";
		const { whiteSpace } = segment;
		const collapses = whiteSpace === "preserve" || whiteSpace === "break-spaces" ? null : whiteSpace === "preserve-breaks" ? /[\t\r\f ]/ : /[\t\n\r\f ]/;
		for (const character of segment.node.data.slice(segment.start, segment.end)) {
			if (collapses?.test(character)) {
				if (text && !text.endsWith("\n")) separator ||= " ";
				continue;
			}
			if (whiteSpace === "preserve-breaks" && character === "\n" && separator === " ") separator = "";
			text += separator + character;
			separator = "";
		}
	}
	return text;
}
const says = (el, options = {}) => {
	const segments = textNodesUnder(el, "says", null, options.format);
	return options.format === "lines" ? linesFrom(segments) : quoteFrom(segments);
};
const wrote = (el) => quoteFrom(textNodesUnder(el, "wrote"));
function rangeOf(segments) {
	const first = segments[0];
	const last = segments.at(-1);
	if (!first || !last) throw new RangeError("A passage range needs at least one segment");
	const range = document.createRange();
	range.setStart(first.node, first.start);
	range.setEnd(last.node, last.end);
	return range;
}
const EDGE = "\0";
function segmentAt({ segments }, i) {
	let lo = 0;
	let hi = segments.length;
	while (lo < hi) {
		const mid = lo + hi >> 1;
		const segment = segments[mid];
		if (segment && segment.rawStart <= i) lo = mid + 1;
		else hi = mid;
	}
	return lo - 1;
}
function pointAt(reading, i) {
	const segment = reading.segments[segmentAt(reading, i)];
	if (!segment) return null;
	const offset = i - segment.rawStart;
	return offset < segment.end - segment.start ? {
		node: segment.node,
		offset: segment.start + offset,
		segment
	} : null;
}
function spanOf(reading, lo, hi) {
	const { segments } = reading;
	const out = [];
	let seg;
	for (let k = Math.max(0, segmentAt(reading, lo)); seg = segments[k]; k++) {
		const from = seg.rawStart;
		if (from >= hi) break;
		const a = Math.max(lo, from);
		const b = Math.min(hi, from + seg.end - seg.start);
		if (b > a) out.push({
			...seg,
			start: seg.start + a - from,
			end: seg.start + b - from,
			breakBefore: Boolean(seg.breakBefore && a === from)
		});
	}
	return out;
}
const holds = (reading, at, want, before) => {
	const there = neighbourhood(reading, at, want.length || 1, before);
	if (!want) return there === "";
	return before ? there.endsWith(want) : there.startsWith(want);
};
function neighbourhood(reading, at, want, before) {
	const { fences } = reading;
	const edge = before ? fences.filter((f) => f <= at).at(-1) ?? 0 : fences.find((f) => f >= at) ?? reading.raw.length;
	for (let raw = want * 2;; raw *= 2) {
		const lo = before ? Math.max(edge, at - raw) : at;
		const hi = before ? at : Math.min(edge, at + raw);
		const text = quoteFrom(spanOf(reading, lo, hi));
		if ([...text].length >= want || (before ? lo === edge : hi === edge)) return text;
	}
}
const WATCH_READING = {
	subtree: true,
	childList: true,
	characterData: true,
	attributes: true,
	attributeOldValue: true,
	attributeFilter: [
		"class",
		"data-lf-said",
		"data-lf-gen",
		"data-lf-projection",
		"data-lf-datum",
		"slot",
		"name",
		"contenteditable"
	]
};
let reading = null;
let elementReadings = /* @__PURE__ */ new WeakMap();
let readingVocabulary;
let readingSettled;
let watcher = null;
const pageReads = (over) => !isElement(over) || !leafSurface(over) && READINGS.says(contextAt(over, null));
const holdsSaid = (node) => isElement(node) && !leafSurface(node) && (node.matches("[data-lf-said]") || node.querySelector("[data-lf-said]") !== null);
const speaks = (node, read) => read && !(isElement(node) && chromeMark(node) === true) || holdsSaid(node);
const changesTheReading = (record) => {
	const { target } = record;
	if (record.type === "childList") {
		const read = pageReads(target);
		return [...record.addedNodes, ...record.removedNodes].some((n) => speaks(n, read));
	}
	if (record.type === "characterData") return pageReads(target.parentNode);
	if (!isElement(target)) return false;
	if (record.attributeName === "class") {
		if (/(^|\s)lf-ui(\s|$)/.test(record.oldValue ?? "") === target.classList.contains("lf-ui")) return false;
	}
	if (record.attributeName === "name" && target.localName !== "slot") return false;
	return record.attributeName === "data-lf-said" && record.oldValue !== null || holdsSaid(target) || pageReads(target.parentNode);
};
let readingVersion = 0;
const forgetReading = () => {
	reading = null;
	elementReadings = /* @__PURE__ */ new WeakMap();
	readingVersion += 1;
};
function pageReadingVersion() {
	catchUpReading();
	return readingVersion;
}
function watchReading() {
	if (watcher) return watcher;
	watcher = new MutationObserver((records) => {
		if (records.some(changesTheReading)) forgetReading();
	});
	watcher.observe(document, WATCH_READING);
	return watcher;
}
function watchPassageRoot(root) {
	watchReading().observe(root, WATCH_READING);
	forgetReading();
}
function fencePassageParts(root, children = root.children) {
	passageFences.add(root);
	for (const child of children) passageFences.add(child);
	forgetReading();
}
function pageText() {
	catchUpReading();
	return reading ??= readPage();
}
function catchUpReading() {
	const moved = watchReading().takeRecords().some(changesTheReading);
	const vocabulary = registry.$layer?.generation;
	settlements();
	if (moved || vocabulary !== readingVocabulary || settledKey !== readingSettled) forgetReading();
	readingVocabulary = vocabulary;
	readingSettled = settledKey;
}
function elementReading(element, reading = "says") {
	catchUpReading();
	let kept = elementReadings.get(element);
	if (kept?.[reading] !== void 0) return kept[reading];
	const value = quoteFrom(textNodesUnder(element, reading));
	if (element.isConnected && element.ownerDocument === document && pageReads(element)) {
		if (!kept) elementReadings.set(element, kept = {});
		kept[reading] = value;
	}
	return value;
}
function readPage() {
	const segments = [];
	const cellChains = [];
	const keeps = READINGS.says;
	let breakBefore = false;
	walk(document.body, (node, ctx) => {
		if (!keeps(ctx)) return;
		segments.push({
			...segmentIn(node, ctx),
			breakBefore
		});
		breakBefore = false;
		cellChains.push(ctx.cells);
	}, (child) => child.matches(LEAF_SURFACE), (ctx) => {
		if (keeps(ctx)) breakBefore = true;
	});
	const dynamicWords = /* @__PURE__ */ new Set();
	for (const { gen } of segments) if (gen && unmodelled(gen)) dynamicWords.add(gen);
	const cellOf = (chain) => {
		for (let at = chain; at; at = at.up) if (opaque(at.el) || at.editing || dynamicWords.has(at.el)) return at.el;
		return null;
	};
	const parts = [];
	const indexed = [];
	const positions = /* @__PURE__ */ new WeakMap();
	const fences = /* @__PURE__ */ new Set();
	let length = 0;
	let previousCell = null;
	segments.forEach((seg, k) => {
		const cell = cellOf(cellChains[k]);
		if (k === 0) {
			if (cell) fences.add(0);
		} else {
			if (cell !== previousCell && (cell || previousCell)) fences.add(length);
			parts.push(seg.breakBefore ? " " : EDGE);
			length += 1;
		}
		indexed.push({
			...seg,
			rawStart: length
		});
		positions.set(seg.node, length - seg.start);
		parts.push(seg.node.data);
		length += seg.end - seg.start;
		previousCell = cell;
	});
	if (previousCell) fences.add(length);
	return {
		raw: parts.join(""),
		positions,
		fences: [...fences].sort((a, b) => a - b),
		segments: indexed
	};
}
function pageBlocks() {
	const text = pageText();
	if (!text.blocks) {
		const seen = /* @__PURE__ */ new Set();
		text.blocks = text.segments.map(({ block }) => block).filter((block) => block !== null).filter((block) => !seen.has(block) && seen.add(block));
	}
	return text.blocks;
}
function spanIn(reading, segments) {
	const first = segments[0];
	const last = segments.at(-1);
	const position = (node) => {
		const offset = reading.positions.get(node);
		if (offset === void 0) throw new RangeError("A passage must belong to the page reading it is placed in");
		return offset;
	};
	const start = first ? position(first.node) + first.start : 0;
	return [start, last ? position(last.node) + last.end : start];
}
const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const LEAD_CAP = 400;
function confirmRest(raw, at, words) {
	let i = at;
	for (const w of words) {
		const gap = i;
		while (i < raw.length && (raw[i] === EDGE || /\s/.test(raw.charAt(i)))) i++;
		if (i === gap) return -1;
		for (const ch of w) {
			while (raw[i] === EDGE) i++;
			if (!raw.startsWith(ch, i)) return -1;
			i += ch.length;
		}
	}
	return i;
}
const withinCell = (text, from, to) => !text.fences.some((fence) => from < fence && fence < to);
function findQuote(text, quote, anchor, within) {
	const { raw } = text;
	const words = quote.trim().split(/\s+/).filter(Boolean);
	if (!words.length) return [];
	const lead = [];
	let spent = 0;
	for (const next of words) {
		if (lead.length && spent + next.length > LEAD_CAP) break;
		lead.push(next);
		spent += next.length + 1;
	}
	const rest = words.slice(lead.length);
	const pattern = new RegExp(lead.map((w) => [...w].map(escape).join(`${EDGE}*`)).join(`[\\s${EDGE}]+`), "g");
	const [pre, post] = [anchor.prefix ?? "", anchor.suffix ?? ""];
	const candidates = [];
	const exact = [];
	for (const at of raw.matchAll(pattern)) {
		const stop = confirmRest(raw, at.index + at[0].length, rest);
		if (stop === -1 || !withinCell(text, at.index, stop)) continue;
		if (within && !(under(pointAt(text, at.index)?.node, within) && under(pointAt(text, stop - 1)?.node, within))) continue;
		const hit = {
			from: at.index,
			to: stop
		};
		candidates.push(hit);
		if (holds(text, hit.from, pre, true) && holds(text, hit.to, post, false)) exact.push(hit);
	}
	const found = exact.length === 1 ? exact[0] : exact.length === 0 && candidates.length === 1 ? candidates[0] : null;
	return found ? spanOf(text, found.from, found.to) : [];
}
function searchableWords() {
	const styles = /* @__PURE__ */ new Map();
	const reachable = /* @__PURE__ */ new Map();
	const style = (el) => {
		let value = styles.get(el);
		if (!value) styles.set(el, value = getComputedStyle(el));
		return value;
	};
	const canReveal = (el) => {
		if (!el) return true;
		const kept = reachable.get(el);
		if (kept !== void 0) return kept;
		const css = style(el);
		const result = css.display !== "none" && (css.contentVisibility !== "hidden" || el.getAttribute("hidden") === "until-found") && canReveal(renderedParent(el));
		reachable.set(el, result);
		return result;
	};
	return ({ node }) => {
		const parent = renderedParent(node);
		return parent && style(parent).visibility === "visible" && canReveal(parent);
	};
}
function findText(text, query) {
	const words = query.trim().split(/\s+/u).filter(Boolean);
	if (!words.length) return [];
	const pattern = new RegExp(words.map((w) => [...w].map(escape).join(`${EDGE}*`)).join(`[\\s${EDGE}]+`), "giu");
	const out = [];
	const searchable = searchableWords();
	for (let match; match = pattern.exec(text.raw);) {
		const from = match.index;
		const to = from + match[0].length;
		const segments = spanOf(text, from, to);
		if (withinCell(text, from, to) && segments.every(searchable)) out.push(segments);
		else {
			const point = text.raw.slice(from, from + 2)[Symbol.iterator]().next();
			if (!point.done) pattern.lastIndex = from + point.value.length;
		}
	}
	return out;
}
function contextAround(text, segments, { before = 28, after = 28 } = {}) {
	const [start, end] = spanIn(text, segments);
	function side(at, length, backwards) {
		if (!length) return "";
		const budget = length * 2 + 1;
		const neighbourhoodPoints = [...neighbourhood(text, at, budget, backwards)];
		const points = backwards ? neighbourhoodPoints.slice(-budget) : neighbourhoodPoints.slice(0, budget);
		const context = points.join("");
		const boundary = backwards ? points.slice(0, Math.max(0, points.length - length)).join("").length : points.slice(0, length).join("").length;
		const word = textUnits.segment(context).containing(backwards ? boundary : boundary - 1);
		const outer = word?.isWordLike ? backwards ? word.index : word.index + word.segment.length : boundary;
		if ((backwards ? outer === 0 : outer === context.length) && points.length >= budget) {
			const excerpt = excerptWords(backwards ? points.toReversed().join("") : context, length).slice(0, -1);
			return backwards ? [...excerpt].toReversed().join("") : excerpt;
		}
		return (backwards ? context.slice(outer) : context.slice(0, outer)).trim();
	}
	return {
		before: side(start, before, true),
		after: side(end, after, false)
	};
}
function pageParts(sel) {
	return pageQueryAll(sel).filter(inPage);
}

//#endregion
export { DATUM, LEAF_SURFACE, alignInlineText, alignText, authored, authoredScope, blockAt, closestAcross, contextAround, cut, elementById, elementFromPointAcross, elementOver, elementReading, excerptWords, fencePassageParts, fileModelsPassage, findQuote, findText, inChrome, inPage, labelWords, layoutBox, leafSurface, neighbourhood, pageBlocks, pageDocument, pageParts, pageQueryAll, pageReadingVersion, pageText, pageWords, pointAt, quoteFrom, rangeOf, readingFrom, renderRetired, says, segmentBlock, segmentsIn, sentenceUnits, settledAway, showsWords, spanIn, textNodesUnder, textUnits, verbatimBoundaryIdentity, verbatimOwnerIdentity, watchPassageRoot, wrote };