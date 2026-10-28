import { PAGE_PAINT_ATTRIBUTE, pageUpgraded, renderedParent, shadowHost, under, upFrom } from "./bundle-portable.js";
import { COLLAPSE, SAID, TEXT_BLOCK, UI_MARKS, decisionFor, declaredRoot, hostIn, inUi, overIn, pageShadowRoots, readPart, refuseShadowRoot, registry, shadowRootsIn, uiInside } from "./bundle-layer-stack.js";
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
	const coarse = alignText(before, after, sentenceUnits);
	const runs = [];
	const push = (run) => {
		const last = runs.at(-1);
		if (last?.kind === run.kind) last.text += run.text;
		else runs.push({ ...run });
	};
	for (let at = 0; at < coarse.length; at++) {
		const run = coarse[at];
		if (!(run.kind === "delete" && coarse[at + 1]?.kind === "insert")) {
			push(run);
			continue;
		}
		const next = coarse[++at];
		const fine = alignText(run.text, next.text);
		if (fine.filter((part) => part.kind === "same").reduce((length, part) => length + part.text.length, 0) >= Math.min(run.text.length, next.text.length) * .6) fine.forEach(push);
		else {
			push(run);
			push(next);
		}
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
				const decision = decisions?.[tag];
				const outcome = decision && state[decision.verb]?.detail?.outcome;
				const retires = outcome ? decision.retires[outcome] : null;
				if (retires?.length) holders.set(id, {
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
	for (let at = el; at; at = at.parentElement) if (retiredSlot(at)) return true;
	const nodes = [...el.childNodes];
	return nodes.some((n) => n.nodeType === 1 && retiredSlot(n)) && nodes.every((n) => n.nodeType === 1 ? retiredSlot(n) || uiInside(n, el) : n.nodeType !== 3 || !n.data.trim());
}
const GENERATED = ".lf-ui, [data-lf-gen]";
const DATUM = "[data-lf-projection][data-lf-datum]";
const inChrome = (node) => Boolean(node && closestAcross(node, ".lf-chrome"));
const showsWords = (block) => block.checkVisibility({ visibilityProperty: true });
const LEAF_SURFACE = ".lf-chrome, [data-lf-runtime]";
const leafSurface = (node) => node ? closestAcross(node, LEAF_SURFACE) : null;
const pageWords = (node) => Boolean(node) && !inChrome(node) && !inUi(node);
const bareTextRefusal = (n) => {
	const host = shadowHost(n.getRootNode());
	const at = host ? `<${host.localName}${host.id ? ` id="${host.id}"` : ""}>` : "a module";
	return /* @__PURE__ */ new Error(`${at} staged bare text into a shadow root: ${JSON.stringify(n.data.trim().slice(0, 40).trim())} has no element over it, so the page holds no block, cell or fence for it. Give a module's rendered words an element to sit in.`);
};
const elementOver = (n) => {
	if (n.parentElement) return n.parentElement;
	throw bareTextRefusal(n);
};
function refusesBareText(root) {
	let bare = root.firstChild;
	while (bare && bare.nodeType !== Node.TEXT_NODE) bare = bare.nextSibling;
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
	for (let a = node?.nodeType === 1 ? node : upFrom(node); a; a = upFrom(a)) if (a.localName?.startsWith("lf-")) return a;
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
	return !(attr && registry[el.parentElement?.localName]?.["x-says"]?.[attr]);
};
const fileModelsPassage = (segments) => segments.every(({ node, gen }) => !node.parentElement.isContentEditable && (!gen || !unmodelled(gen)));
const opaque = (el) => passageFences.has(el);
const editingBoundary = (el) => Boolean(el.isContentEditable) !== Boolean(el.parentElement?.isContentEditable);
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
	for (let i = over.length - 1; i >= 0; i--) {
		const a = over[i];
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
	return (n) => !overIn(n.nodeType === 1 ? n : elementOver(n), GENERATED, frame);
};
function walk(root, onText, skip = null, onBreak = null) {
	const frame = frameOf(root);
	const passed = /* @__PURE__ */ new Map();
	const contextOver = (node) => {
		const over = elementOver(node);
		return passed.get(over) ?? contextAt(over, frame);
	};
	const visit = (node, ctx) => {
		if (node.nodeType === Node.ELEMENT_NODE && node.localName === "br") {
			onBreak?.(ctx);
			return;
		}
		for (let child = node.firstChild; child; child = child.nextSibling) {
			if (child.nodeType === Node.TEXT_NODE) {
				if (node.nodeType !== Node.ELEMENT_NODE) elementOver(child);
				onText(child, ctx);
				continue;
			}
			if (child.nodeType !== Node.ELEMENT_NODE || skip?.(child)) continue;
			const inner = enter(ctx, child);
			if (child.localName === "slot") {
				passed.set(child, inner);
				for (const assigned of child.assignedNodes({ flatten: true })) assigned.nodeType === Node.TEXT_NODE ? onText(assigned, contextOver(assigned)) : visit(assigned, enter(contextOver(assigned), assigned));
			} else {
				const declared = declaredRoot(child);
				if (declared && !refusesBareText(declared)) {
					passed.set(child, inner);
					visit(declared, crossed(inner));
				} else visit(child, inner);
			}
		}
	};
	const host = shadowHost(root);
	visit(root, root.nodeType === Node.ELEMENT_NODE ? contextAt(root, frame) : host ? crossed(contextAt(host, frame)) : NO_CONTEXT);
}
function textNodesUnder(root, reading = "says", boundary = null) {
	const keeps = READINGS[reading];
	const segments = [];
	let breakBefore = false;
	walk(root, (node, ctx) => {
		if (keeps(ctx)) {
			segments.push({
				...segmentIn(node, ctx),
				breakBefore
			});
			breakBefore = false;
		}
	}, boundary && ((child) => boundary(child, segments.length)), (ctx) => {
		if (keeps(ctx)) breakBefore = true;
	});
	return segments;
}
function closestAcross(node, selector) {
	let el = node?.nodeType === Node.ELEMENT_NODE ? node : upFrom(node);
	while (el) {
		const hit = el.closest(selector);
		if (hit) return hit;
		el = shadowHost(el.getRootNode());
	}
	return null;
}
const elementById = (id, root = document) => {
	const found = root === document ? document.getElementById(id) : root.querySelector(`[id="${CSS.escape(id)}"]`);
	if (found) return found;
	for (const shadow of shadowRootsIn(root)) {
		const inside = shadow.getElementById(id);
		if (inside) return inside;
	}
	return null;
};
const pageDocument = (doc = document) => doc.querySelector("body > main");
const layoutBox = () => document.documentElement.lfInitial.layoutBox();
const authoredScope = (node) => closestAcross(node, ".lf-msg-body") ?? pageDocument();
const elementFromPointAcross = (x, y) => {
	let el = document.elementFromPoint(x, y);
	while (el && declaredRoot(el)) {
		const inner = el.shadowRoot.elementFromPoint(x, y);
		if (!inner || inner === el) break;
		el = inner;
	}
	return el;
};
const pageQueryAll = (selector) => [document, ...pageShadowRoots()].flatMap((root) => [...root.querySelectorAll(selector)]);
function pageRange(sel) {
	const plain = sel.getRangeAt(0);
	const shadowRoots = pageShadowRoots();
	if (!shadowRoots.length) return plain;
	const [composed] = sel.getComposedRanges({ shadowRoots });
	const { startContainer, startOffset, endContainer, endOffset } = composed;
	if (startContainer.getRootNode() !== endContainer.getRootNode()) return plain;
	const range = document.createRange();
	range.setStart(startContainer, startOffset);
	range.setEnd(endContainer, endOffset);
	return range;
}
let writtenSelection = null;
let writtenBackward = false;
function selectEnds(anchor, focus) {
	const selection = getSelection();
	const from = document.createRange(), to = document.createRange();
	from.setStart(...anchor);
	to.setStart(...focus);
	writtenBackward = from.compareBoundaryPoints(Range.START_TO_START, to) > 0;
	selection.setBaseAndExtent(...anchor, ...focus);
	writtenSelection = selectionEnds(selection);
}
const selectionEnds = (selection) => {
	const range = selection.rangeCount ? pageRange(selection) : null;
	return [
		selection.anchorNode,
		selection.anchorOffset,
		selection.focusNode,
		selection.focusOffset,
		range?.startContainer,
		range?.startOffset,
		range?.endContainer,
		range?.endOffset
	];
};
function programmaticSelection(selection) {
	if (!writtenSelection) return false;
	if (selectionEnds(selection).every((end, i) => end === writtenSelection[i])) return true;
	writtenSelection = null;
	return false;
}
function selectionBackward(selection, range = pageRange(selection)) {
	if (selection.anchorNode.getRootNode() !== range.commonAncestorContainer.getRootNode()) return programmaticSelection(selection) ? writtenBackward : selection.direction === "backward";
	const probe = document.createRange();
	probe.setStart(selection.anchorNode, selection.anchorOffset);
	return probe.compareBoundaryPoints(Range.START_TO_START, range) > 0;
}
function coveredBy(range, node) {
	const n = hostIn(node, range.commonAncestorContainer.getRootNode());
	if (!n || !range.intersectsNode(n)) return false;
	if (n !== node) {
		if (range.endContainer === n && range.endOffset === 0) return false;
		if (range.startContainer === n && range.startOffset === n.childNodes.length) return false;
	}
	return true;
}
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
	segments.forEach((seg, i) => {
		if (i && (seg.breakBefore || segmentTextBlock(seg) !== segmentTextBlock(segments[i - 1]))) {
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
	});
	return mapCharacters ? {
		text,
		units
	} : text;
}
const quoteFrom = (segments) => readSegments(segments, false);
const readingFrom = (segments) => readSegments(segments, true);
const cut = (text, from, to) => [...text].slice(from, to).join("");
const says = (el) => quoteFrom(textNodesUnder(el));
const wrote = (el) => quoteFrom(textNodesUnder(el, "wrote"));
function rangeOf(segments) {
	const range = document.createRange();
	range.setStart(segments[0].node, segments[0].start);
	range.setEnd(segments.at(-1).node, segments.at(-1).end);
	return range;
}
const EDGE = "\0";
function segmentAt({ starts }, i) {
	let lo = 0;
	let hi = starts.length - 1;
	if (hi < 0 || i < starts[0]) return -1;
	while (lo < hi) {
		const mid = lo + hi + 1 >> 1;
		if (starts[mid] <= i) lo = mid;
		else hi = mid - 1;
	}
	return lo;
}
function pointAt(reading, i) {
	const k = segmentAt(reading, i);
	if (k === -1) return null;
	const segment = reading.segments[k];
	const offset = i - reading.starts[k];
	return offset < segment.end - segment.start ? {
		node: segment.node,
		offset: segment.start + offset,
		segment
	} : null;
}
function spanOf(reading, lo, hi) {
	const { segments, starts } = reading;
	const out = [];
	for (let k = Math.max(0, segmentAt(reading, lo)); k < segments.length; k++) {
		const seg = segments[k];
		const from = starts[k];
		if (from >= hi) break;
		const a = Math.max(lo, from);
		const b = Math.min(hi, from + seg.end - seg.start);
		if (b > a) out.push({
			...seg,
			start: seg.start + a - from,
			end: seg.start + b - from,
			breakBefore: seg.breakBefore && a === from
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
const pageReads = (over) => over?.nodeType !== 1 || READINGS.says(contextAt(over, null));
const holdsSaid = (node) => node.nodeType === 1 && (node.matches("[data-lf-said]") || node.querySelector("[data-lf-said]") !== null);
const speaks = (node, read) => read && !(node.nodeType === 1 && chromeMark(node) === true) || holdsSaid(node);
const changesTheReading = (record) => {
	const { target } = record;
	if (record.type === "childList") {
		const read = pageReads(target);
		return [...record.addedNodes, ...record.removedNodes].some((n) => speaks(n, read));
	}
	if (record.type === "characterData") return pageReads(target.parentNode);
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
	}, null, (ctx) => {
		if (keeps(ctx)) breakBefore = true;
	});
	const dynamicWords = /* @__PURE__ */ new Set();
	for (const { gen } of segments) if (gen && unmodelled(gen)) dynamicWords.add(gen);
	const cellOf = (chain) => {
		for (let at = chain; at; at = at.up) if (opaque(at.el) || at.editing || dynamicWords.has(at.el)) return at.el;
		return null;
	};
	const parts = [];
	const starts = [];
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
		starts.push(length);
		positions.set(seg.node, length - seg.start);
		parts.push(seg.node.data);
		length += seg.end - seg.start;
		previousCell = cell;
	});
	if (previousCell) fences.add(length);
	return {
		raw: parts.join(""),
		starts,
		positions,
		fences: [...fences].sort((a, b) => a - b),
		segments
	};
}
function pageBlocks() {
	const text = pageText();
	if (!text.blocks) {
		const seen = /* @__PURE__ */ new Set();
		text.blocks = text.segments.map(({ block }) => block).filter((block) => block && !seen.has(block) && seen.add(block));
	}
	return text.blocks;
}
function spanIn(reading, segments) {
	const first = segments[0];
	const last = segments.at(-1);
	const start = first ? reading.positions.get(first.node) + first.start : 0;
	return [start, last ? reading.positions.get(last.node) + last.end : start];
}
const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const LEAD_CAP = 400;
function confirmRest(raw, at, words) {
	let i = at;
	for (const w of words) {
		const gap = i;
		while (i < raw.length && (raw[i] === EDGE || /\s/.test(raw[i]))) i++;
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
	for (let spent = 0; words.length > lead.length;) {
		const next = words[lead.length];
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
		if (within && !(under(pointAt(text, at.index).node, within) && under(pointAt(text, stop - 1).node, within))) continue;
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
		if (!styles.has(el)) styles.set(el, getComputedStyle(el));
		return styles.get(el);
	};
	const canReveal = (el) => {
		if (!el) return true;
		if (reachable.has(el)) return reachable.get(el);
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
		else pattern.lastIndex = from + String.fromCodePoint(text.raw.codePointAt(from)).length;
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
	return pageQueryAll(sel).filter((el) => !inChrome(el));
}

//#endregion
export { DATUM, LEAF_SURFACE, alignInlineText, alignText, authored, authoredScope, blockAt, closestAcross, contextAround, cut, elementById, elementFromPointAcross, elementOver, elementReading, excerptWords, fencePassageParts, fileModelsPassage, findQuote, findText, inChrome, labelWords, layoutBox, leafSurface, neighbourhood, pageBlocks, pageDocument, pageParts, pageQueryAll, pageRange, pageReadingVersion, pageText, pageWords, pointAt, programmaticSelection, quoteFrom, rangeOf, readingFrom, renderRetired, says, segmentBlock, segmentsIn, selectEnds, selectionBackward, sentenceUnits, settledAway, showsWords, spanIn, textNodesUnder, textUnits, verbatimBoundaryIdentity, verbatimOwnerIdentity, watchPassageRoot, wrote };